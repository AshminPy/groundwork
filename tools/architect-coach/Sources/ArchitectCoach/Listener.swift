import AVFoundation
import Speech

/// Microphone input. Buffers go to whoever is listening; the listener ignores them while paused,
/// so the coach never hears its own voice (half-duplex, no echo).
final class Mic {
    private let engine = AVAudioEngine()
    var onBuffer: ((AVAudioPCMBuffer) -> Void)?

    func start() throws {
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            self?.onBuffer?(buffer)
        }
        engine.prepare()
        try engine.start()
    }

    func stop() {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
    }
}

/// Turns your speech into one finished utterance at a time.
/// An utterance ends after `silenceSeconds` without new words (end-of-turn detection).
final class Listener {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let lock = NSLock()
    private var request: SFSpeechAudioBufferRecognitionRequest?   // guarded by lock
    private var task: SFSpeechRecognitionTask?
    private var token = 0
    private var latest = ""
    private var startedAt = Date()
    private var endpoint: DispatchWorkItem?

    /// Pause length that ends your turn. Longer = fewer cut-offs, slower replies.
    var silenceSeconds: TimeInterval = 1.4
    /// Recognition requests have a duration limit; a long monologue is committed before it.
    private let maxUtteranceSeconds: TimeInterval = 55

    var onPartial: ((String) -> Void)?    // main queue
    var onUtterance: ((String) -> Void)?  // main queue

    static func requestAuthorization() async -> Bool {
        await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { cont.resume(returning: $0 == .authorized) }
        }
    }

    var isOnDevice: Bool { recognizer?.supportsOnDeviceRecognition ?? false }

    /// Start listening for the next utterance. Main queue only.
    func begin() {
        dispatchPrecondition(condition: .onQueue(.main))
        guard let recognizer, recognizer.isAvailable else { return }
        cancelTask()
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.addsPunctuation = true
        if recognizer.supportsOnDeviceRecognition { req.requiresOnDeviceRecognition = true }
        token += 1
        let myToken = token
        latest = ""
        startedAt = Date()
        lock.lock(); request = req; lock.unlock()
        task = recognizer.recognitionTask(with: req) { [weak self] result, _ in
            guard let result else { return }
            let text = result.bestTranscription.formattedString
            let final = result.isFinal
            DispatchQueue.main.async {
                guard let self, self.token == myToken else { return }
                self.latest = text
                self.onPartial?(text)
                if final { self.finish() } else { self.scheduleEndpoint() }
            }
        }
    }

    /// Stop listening without producing an utterance (muted, thinking, speaking). Main queue only.
    func pause() {
        dispatchPrecondition(condition: .onQueue(.main))
        token += 1
        cancelTask()
    }

    /// Audio thread.
    func append(_ buffer: AVAudioPCMBuffer) {
        lock.lock()
        let req = request
        lock.unlock()
        guard let req else { return }
        req.append(buffer)
        if Date().timeIntervalSince(startedAt) > maxUtteranceSeconds {
            DispatchQueue.main.async { [weak self] in self?.finish() }
        }
    }

    private func scheduleEndpoint() {
        endpoint?.cancel()
        let work = DispatchWorkItem { [weak self] in self?.finish() }
        endpoint = work
        DispatchQueue.main.asyncAfter(deadline: .now() + silenceSeconds, execute: work)
    }

    private func finish() {
        let text = latest.trimmingCharacters(in: .whitespacesAndNewlines)
        token += 1
        cancelTask()
        if text.isEmpty { begin() } else { onUtterance?(text) }
    }

    private func cancelTask() {
        endpoint?.cancel()
        endpoint = nil
        lock.lock()
        request?.endAudio()
        request = nil
        lock.unlock()
        task?.cancel()
        task = nil
    }
}
