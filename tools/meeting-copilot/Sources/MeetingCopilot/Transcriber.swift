import AVFoundation
import Speech

/// One speech-to-text stream for one audio source ("Me" = microphone, "Them" = system audio).
/// Uses Apple's on-device recognizer, so audio does not leave the Mac for transcription.
final class Transcriber {
    let speaker: String
    private let recognizer: SFSpeechRecognizer?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var startedAt = Date()
    private let lock = NSLock()

    /// Recognition requests have a duration limit, so the task is rotated before it is reached.
    private let maxTaskSeconds: TimeInterval = 50

    private var generation = 0

    /// Called on the main queue with (speaker, task generation, text, isFinal).
    var onText: ((String, Int, String, Bool) -> Void)?

    init(speaker: String, locale: Locale = Locale(identifier: "en-US")) {
        self.speaker = speaker
        self.recognizer = SFSpeechRecognizer(locale: locale)
    }

    static func requestAuthorization() async -> Bool {
        await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { cont.resume(returning: $0 == .authorized) }
        }
    }

    var supportsOnDevice: Bool { recognizer?.supportsOnDeviceRecognition ?? false }

    func start() {
        lock.lock(); defer { lock.unlock() }
        startTaskLocked()
    }

    func stop() {
        lock.lock(); defer { lock.unlock() }
        request?.endAudio()
        task?.cancel()
        request = nil
        task = nil
    }

    func append(_ buffer: AVAudioPCMBuffer) {
        lock.lock(); defer { lock.unlock() }
        if Date().timeIntervalSince(startedAt) > maxTaskSeconds {
            // Finish the current segment; its final result is still delivered.
            request?.endAudio()
            startTaskLocked()
        }
        request?.append(buffer)
    }

    private func startTaskLocked() {
        guard let recognizer, recognizer.isAvailable else { return }
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.addsPunctuation = true
        if recognizer.supportsOnDeviceRecognition {
            req.requiresOnDeviceRecognition = true
        }
        request = req
        startedAt = Date()
        generation += 1
        let gen = generation
        let speaker = self.speaker
        task = recognizer.recognitionTask(with: req) { [weak self] result, error in
            if let result {
                let text = result.bestTranscription.formattedString
                let final = result.isFinal
                DispatchQueue.main.async { self?.onText?(speaker, gen, text, final) }
            }
            // Errors also fire when a rotated task ends; the next task keeps going.
            _ = error
        }
    }
}
