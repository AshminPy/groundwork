import AVFoundation

/// Speaks the coach's reply sentence by sentence while it is still streaming,
/// so the first words are heard about one sentence after Claude starts answering.
final class Speaker: NSObject, AVSpeechSynthesizerDelegate {
    private let synth = AVSpeechSynthesizer()
    private var buffer = ""
    private var active = Set<ObjectIdentifier>()
    private var inputDone = true

    var voiceIdentifier: String?
    var rate: Float = AVSpeechUtteranceDefaultSpeechRate
    /// Called on the main queue when everything queued has been spoken.
    var onIdle: (() -> Void)?

    override init() {
        super.init()
        synth.delegate = self
    }

    /// English voices, best quality first. Download Premium/Enhanced voices in
    /// System Settings > Accessibility > Spoken Content > System voice > Manage Voices.
    static func voices() -> [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix("en") }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
    }

    func beginReply() {
        buffer = ""
        inputDone = false
    }

    func feed(_ chunk: String) {
        buffer += chunk
        while let cut = Self.sentenceEnd(in: buffer) {
            say(String(buffer[..<cut]))
            buffer = String(buffer[cut...])
        }
    }

    func endReply() {
        say(buffer)
        buffer = ""
        inputDone = true
        if active.isEmpty { onIdle?() }
    }

    func stop() {
        active.removeAll()
        buffer = ""
        inputDone = true
        synth.stopSpeaking(at: .immediate)
    }

    var isSpeaking: Bool { !active.isEmpty }

    private func say(_ text: String) {
        let clean = Self.speakable(text)
        guard !clean.isEmpty else { return }
        let utterance = AVSpeechUtterance(string: clean)
        if let id = voiceIdentifier, let voice = AVSpeechSynthesisVoice(identifier: id) {
            utterance.voice = voice
        } else {
            utterance.voice = Self.voices().first
        }
        utterance.rate = rate
        active.insert(ObjectIdentifier(utterance))
        synth.speak(utterance)
    }

    private func done(_ utterance: AVSpeechUtterance) {
        DispatchQueue.main.async { [weak self] in
            guard let self, self.active.remove(ObjectIdentifier(utterance)) != nil else { return }
            if self.active.isEmpty && self.inputDone { self.onIdle?() }
        }
    }

    func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) { done(utterance) }
    func speechSynthesizer(_ s: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) { done(utterance) }

    /// End of the first complete sentence: . ! ? followed by whitespace, or a newline.
    /// "3.5" and "e.g.x" do not split because the next character is not whitespace.
    static func sentenceEnd(in text: String) -> String.Index? {
        var i = text.startIndex
        while i < text.endIndex {
            let c = text[i]
            let next = text.index(after: i)
            if c == "\n" { return next }
            if ".!?".contains(c), next < text.endIndex, text[next].isWhitespace { return next }
            i = next
        }
        return nil
    }

    /// Removes markdown and URLs so the voice does not read symbols aloud.
    static func speakable(_ text: String) -> String {
        var s = text
        s = s.replacingOccurrences(of: #"\[([^\]]+)\]\([^)]+\)"#, with: "$1", options: .regularExpression)
        s = s.replacingOccurrences(of: #"https?://\S+"#, with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: #"[*#`_>|]"#, with: "", options: .regularExpression)
        s = s.replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
        return s.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
