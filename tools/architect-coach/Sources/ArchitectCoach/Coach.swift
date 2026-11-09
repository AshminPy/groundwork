import AVFoundation
import Foundation

struct Turn: Identifiable {
    let id = UUID()
    let fromUser: Bool
    var text: String
    var sources: [(title: String, url: String)] = []
    var hadScreenshot = false
}

enum Phase: String {
    case idle = "Not in a session"
    case listening = "Listening…"
    case thinking = "Thinking…"
    case speaking = "Speaking…"
}

/// The conversation loop: listen → (end of your turn) → think → speak → listen.
/// The mic is ignored while the coach thinks or speaks, so it never hears itself.
@MainActor
final class Coach: ObservableObject {
    @Published var phase: Phase = .idle
    @Published var turns: [Turn] = []
    @Published var partial = ""
    @Published var status = ""
    @Published var muted = false
    @Published var mode: CoachMode = .advise
    @Published var screenshotNext = false

    @Published var coachName: String { didSet { save("coachName", coachName) } }
    @Published var model: String { didSet { save("model", model) } }
    @Published var effort: String { didSet { save("effort", effort) } }
    @Published var domains: String { didSet { save("domains", domains) } }
    @Published var voiceID: String { didSet { save("voiceID", voiceID); speaker.voiceIdentifier = voiceID.isEmpty ? nil : voiceID } }
    @Published var rate: Double { didSet { UserDefaults.standard.set(rate, forKey: "rate"); speaker.rate = Float(rate) } }

    static let defaultDomains = "aws.amazon.com, cloud.google.com, cloudamqp.com, rabbitmq.com, kubernetes.io, developer.hashicorp.com, registry.terraform.io"

    private let mic = Mic()
    private let listener = Listener()
    private let speaker = Speaker()
    private var messages: [[String: Any]] = []   // append-only API history
    private var systemPrompt = ""
    private var sentMode: CoachMode?
    private var requestRunning = false
    private var stopSpeakingThisReply = false
    private var sessionFile: URL?
    private var pendingDecisionRecord = false
    /// True between Start talking and End. Phase alone is not enough: typed questions
    /// outside a session also go through thinking.
    @Published private(set) var sessionActive = false

    var inSession: Bool { sessionActive }

    init() {
        let d = UserDefaults.standard
        coachName = d.string(forKey: "coachName") ?? "Coach"
        model = d.string(forKey: "model") ?? "claude-opus-5-5"
        effort = d.string(forKey: "effort") ?? "low"
        domains = d.string(forKey: "domains") ?? Self.defaultDomains
        voiceID = d.string(forKey: "voiceID") ?? ""
        rate = d.object(forKey: "rate") as? Double ?? Double(AVSpeechUtteranceDefaultSpeechRate)
        speaker.voiceIdentifier = voiceID.isEmpty ? nil : voiceID
        speaker.rate = Float(rate)

        mic.onBuffer = { [listener] in listener.append($0) }
        listener.onPartial = { [weak self] text in MainActor.assumeIsolated { self?.partial = text } }
        listener.onUtterance = { [weak self] text in MainActor.assumeIsolated { self?.userSaid(text) } }
        listener.onProblem = { [weak self] text in MainActor.assumeIsolated { self?.status = text } }
        speaker.onIdle = { [weak self] in MainActor.assumeIsolated { self?.replyFinishedSpeaking() } }
    }

    private func save(_ key: String, _ value: String) { UserDefaults.standard.set(value, forKey: key) }

    // MARK: Session

    func startSession() async {
        guard Keychain.load()?.isEmpty == false else {
            status = "Add your Anthropic API key in Settings (⌘,)."
            return
        }
        guard await Listener.requestAuthorization() else {
            status = "Allow Speech Recognition in System Settings > Privacy & Security."
            return
        }
        guard !requestRunning else { return }
        let knowledge = Storage.loadKnowledge()
        systemPrompt = CoachPrompt.system(coachName: coachName, knowledge: knowledge.text)
        messages.removeAll()
        turns.removeAll()
        sentMode = nil
        sessionFile = Storage.newSessionFile()
        Storage.append("# Session with \(coachName) — \(Date().formatted())\n\n", to: sessionFile!)
        do {
            try mic.start()
        } catch {
            status = "Microphone error: \(error.localizedDescription)"
            return
        }
        sessionActive = true
        status = "Knowledge: \(knowledge.files) file(s)\(knowledge.truncated ? " (cut to fit)" : ""). "
            + (listener.isOnDevice ? "Speech stays on this Mac." : "Speech uses Apple's servers.")
        startListening()
    }

    func endSession() {
        sessionActive = false
        stopSpeakingThisReply = true
        listener.pause()
        speaker.stop()
        mic.stop()
        phase = .idle
        partial = ""
        if let file = sessionFile { status = "Saved notes to \(file.path)" }
    }

    /// Start a fresh topic: clears the conversation history (the saved notes stay).
    func newTopic() {
        guard !requestRunning else { return }
        speaker.stop()
        messages.removeAll()
        turns.removeAll()
        sentMode = nil
        if let file = sessionFile { Storage.append("\n---\n## New topic\n\n", to: file) }
        if inSession { startListening() }
    }

    func toggleMute() {
        muted.toggle()
        if muted { listener.pause(); partial = "" }
        else if phase == .listening { listener.begin() }
    }

    /// Stop the coach talking and give the floor back to you.
    func interrupt() {
        guard inSession, phase == .thinking || phase == .speaking else { return }
        stopSpeakingThisReply = true
        speaker.stop()
        if requestRunning {
            status = "Stopped speaking; the rest of the reply will appear on screen."
        } else {
            startListening()
        }
    }

    private func startListening() {
        phase = .listening
        partial = ""
        if !muted { listener.begin() }
    }

    // MARK: Turns

    private func userSaid(_ text: String) {
        partial = ""
        send(text, spoken: true)
    }

    /// Typed message or a voice utterance.
    func send(_ text: String, spoken: Bool) {
        guard !requestRunning else { return }
        guard let key = Keychain.load(), !key.isEmpty else {
            status = "Add your Anthropic API key in Settings (⌘,)."
            pendingDecisionRecord = false
            return
        }
        if systemPrompt.isEmpty {
            // Typed question before any session: build the persona on first use.
            systemPrompt = CoachPrompt.system(coachName: coachName, knowledge: Storage.loadKnowledge().text)
        }
        listener.pause()
        speaker.stop()
        phase = .thinking
        stopSpeakingThisReply = false

        let wantsScreen = screenshotNext
        screenshotNext = false
        turns.append(Turn(fromUser: true, text: text, hadScreenshot: wantsScreen))
        if let file = sessionFile { Storage.append("**You:** \(text)\n\n", to: file) }

        let client = ClaudeClient(apiKey: key, model: model, effort: effort,
                                  searchDomains: domains.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty })
        requestRunning = true
        Task {
            var content: [[String: Any]] = []
            if wantsScreen, let jpeg = try? await ScreenGrabber.captureJPEG() {
                content.append(["type": "image",
                                "source": ["type": "base64", "media_type": "image/jpeg",
                                           "data": jpeg.base64EncodedString()]])
            }
            content.append(["type": "text", "text": text])
            messages.append(["role": "user", "content": content])
            // Operator instructions go in as mid-conversation system messages, never by
            // editing earlier turns, so the cached history and thinking blocks stay valid.
            var instructions: [String] = []
            if sentMode != mode { instructions.append(mode.instruction); sentMode = mode }
            if !spoken { instructions.append(CoachPrompt.writtenTurn) }
            if !instructions.isEmpty {
                messages.append(["role": "system", "content": instructions.joined(separator: "\n\n")])
            }
            await runReply(client: client, spoken: spoken)
        }
    }

    func writeDecisionRecord() {
        guard !requestRunning else { return }
        pendingDecisionRecord = true
        send(CoachPrompt.decisionRecordRequest, spoken: false)
    }

    private func runReply(client: ClaudeClient, spoken: Bool) async {
        turns.append(Turn(fromUser: false, text: ""))
        let index = turns.count - 1
        if spoken { speaker.beginReply() }
        var assistant: [[String: Any]] = []
        var continuations = 0
        var failed = false
        do {
            while true {
                let history = assistant.isEmpty ? messages : messages + [["role": "assistant", "content": assistant]]
                let result = try await client.stream(system: systemPrompt, messages: history) { [weak self] chunk in
                    guard let self else { return }
                    self.turns[index].text += chunk
                    if spoken && self.sessionActive && !self.stopSpeakingThisReply {
                        self.phase = .speaking
                        self.speaker.feed(chunk)
                    }
                }
                // A paused server-tool loop resumes by re-sending the turn so far; the
                // continuation extends the same assistant turn.
                assistant += result.content
                if result.stopReason == "refusal" {
                    turns[index].text += "\n\n[The model declined this request.]"
                }
                if result.stopReason == "pause_turn" {
                    if continuations < 3 { continuations += 1; continue }
                    turns[index].text += "\n\n[The search ran long and stopped. Ask again to continue.]"
                }
                break
            }
            messages.append(["role": "assistant", "content": assistant])
            turns[index].sources = ClaudeClient.sources(in: assistant)
        } catch {
            // Keep history valid: drop the unanswered user turn (and its system note) so the
            // next request does not send two user turns in a row.
            while let last = messages.last, (last["role"] as? String) != "assistant" { messages.removeLast() }
            sentMode = nil
            turns[index].text += "\n\nError: \(error.localizedDescription)"
            failed = true
            stopSpeakingThisReply = true
            speaker.stop()
        }
        requestRunning = false
        let reply = turns[index]
        if let file = sessionFile {
            let links = reply.sources.map { "- [\($0.title)](\($0.url))" }.joined(separator: "\n")
            Storage.append("**\(coachName):** \(reply.text)\n\(links.isEmpty ? "" : "\nSources:\n\(links)\n")\n", to: file)
            if pendingDecisionRecord && !failed {
                let adr = file.deletingLastPathComponent()
                    .appendingPathComponent(file.deletingPathExtension().lastPathComponent + "-ADR.md")
                try? reply.text.write(to: adr, atomically: true, encoding: .utf8)
                status = "Decision record saved to \(adr.path)"
            }
        }
        pendingDecisionRecord = false
        guard inSession else { phase = .idle; return }
        if spoken && !stopSpeakingThisReply {
            speaker.endReply()   // replyFinishedSpeaking() runs when the voice is done
        } else {
            startListening()
        }
    }

    private func replyFinishedSpeaking() {
        guard inSession, !requestRunning else { return }
        startListening()
    }
}
