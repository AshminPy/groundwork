import AVFoundation
import Foundation

struct Segment: Identifiable {
    let id = UUID()
    let speaker: String
    let text: String
    let time: Date
}

/// Wires audio -> transcription -> transcript, and screen + transcript -> Claude -> answer.
@MainActor
final class Copilot: ObservableObject {
    @Published var isListening = false
    @Published var segments: [Segment] = []
    @Published var partials: [String: String] = [:]   // "speaker#generation" -> partial text
    @Published var answer = ""
    @Published var isAnswering = false
    @Published var status = "Idle"
    @Published var includeScreen = true
    @Published var autoAnswer = false
    @Published var notes: String {
        didSet { UserDefaults.standard.set(notes, forKey: "notes") }
    }
    @Published var model: String {
        didSet { UserDefaults.standard.set(model, forKey: "model") }
    }
    @Published var effort: String {
        didSet { UserDefaults.standard.set(effort, forKey: "effort") }
    }

    /// How much recent transcript is sent with each request.
    private let transcriptWindow: TimeInterval = 5 * 60
    private let audio = AudioCapture()
    private let me = Transcriber(speaker: "Me")
    private let them = Transcriber(speaker: "Them")
    private var answerTask: Task<Void, Never>?
    private var lastAutoAnswer = Date.distantPast

    init() {
        notes = UserDefaults.standard.string(forKey: "notes") ?? ""
        model = UserDefaults.standard.string(forKey: "model") ?? "claude-opus-5-5"
        effort = UserDefaults.standard.string(forKey: "effort") ?? "low"
        let handler: (String, Int, String, Bool) -> Void = { [weak self] speaker, gen, text, final in
            MainActor.assumeIsolated { self?.handleText(speaker: speaker, gen: gen, text: text, final: final) }
        }
        me.onText = handler
        them.onText = handler
        audio.onMicBuffer = { [me] in me.append($0) }
        audio.onSystemBuffer = { [them] in them.append($0) }
        audio.onError = { [weak self] msg in Task { @MainActor in self?.status = msg } }
    }

    // MARK: Listening

    func toggleListening() {
        if isListening { stop() } else { Task { await start() } }
    }

    func start() async {
        guard await Transcriber.requestAuthorization() else {
            status = "Speech recognition permission denied (System Settings > Privacy & Security)."
            return
        }
        me.start()
        them.start()
        do {
            try audio.startMic()
        } catch {
            status = "Microphone error: \(error.localizedDescription)"
        }
        do {
            try await audio.startSystemAudio()
        } catch {
            status = "System audio error (allow Screen Recording): \(error.localizedDescription)"
        }
        isListening = true
        if status == "Idle" || status.hasPrefix("Stopped") {
            status = me.supportsOnDevice ? "Listening (on-device transcription)" : "Listening (Apple server transcription)"
        }
    }

    func stop() {
        me.stop()
        them.stop()
        Task { await audio.stop() }
        isListening = false
        status = "Stopped"
    }

    func clear() {
        segments.removeAll()
        partials.removeAll()
        answer = ""
    }

    private func handleText(speaker: String, gen: Int, text: String, final: Bool) {
        let key = "\(speaker)#\(gen)"
        if final {
            partials[key] = nil
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { return }
            segments.append(Segment(speaker: speaker, text: trimmed, time: Date()))
        } else {
            partials[key] = text
        }
        // Optional: answer automatically when the other side finishes a question.
        if autoAnswer, speaker == "Them", text.trimmingCharacters(in: .whitespaces).hasSuffix("?"),
           !isAnswering, Date().timeIntervalSince(lastAutoAnswer) > 8 {
            lastAutoAnswer = Date()
            ask()
        }
    }

    /// Recent transcript as plain text, oldest first.
    func transcriptText() -> String {
        let cutoff = Date().addingTimeInterval(-transcriptWindow)
        var lines = segments.filter { $0.time >= cutoff }.map { "\($0.speaker): \($0.text)" }
        for (key, text) in partials.sorted(by: { $0.key < $1.key }) where !text.isEmpty {
            lines.append("\(key.split(separator: "#").first ?? ""): \(text)")
        }
        return lines.joined(separator: "\n")
    }

    // MARK: Answering

    func ask(instruction: String = "Suggest how I should answer the latest question.") {
        guard let key = Keychain.load(), !key.isEmpty else {
            status = "Add your Anthropic API key in Settings."
            return
        }
        answerTask?.cancel()
        answer = ""
        isAnswering = true
        let transcript = transcriptText()
        let notes = self.notes
        let withScreen = includeScreen
        let client = ClaudeClient(apiKey: key, model: model, effort: effort)
        answerTask = Task { [weak self] in
            var jpeg: Data?
            if withScreen {
                jpeg = try? await ScreenGrabber.captureJPEG()
            }
            do {
                try await client.streamAnswer(transcript: transcript, notes: notes,
                                              screenshotJPEG: jpeg, instruction: instruction) { chunk in
                    self?.answer += chunk
                }
            } catch is CancellationError {
            } catch {
                self?.answer += "\n\nError: \(error.localizedDescription)"
            }
            self?.isAnswering = false
        }
    }
}
