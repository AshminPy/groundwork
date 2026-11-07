import AVFoundation
import CoreMedia
import ScreenCaptureKit

/// Captures the microphone ("Me") and system audio from the meeting app ("Them").
final class AudioCapture: NSObject, SCStreamOutput, SCStreamDelegate {
    private let engine = AVAudioEngine()
    private var stream: SCStream?
    private let audioQueue = DispatchQueue(label: "copilot.system-audio")

    var onMicBuffer: ((AVAudioPCMBuffer) -> Void)?
    var onSystemBuffer: ((AVAudioPCMBuffer) -> Void)?
    var onError: ((String) -> Void)?

    // MARK: Microphone

    func startMic() throws {
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            self?.onMicBuffer?(buffer)
        }
        engine.prepare()
        try engine.start()
    }

    // MARK: System audio (macOS 13+ ScreenCaptureKit audio capture)

    func startSystemAudio() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            throw NSError(domain: "AudioCapture", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "No display found"])
        }
        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.excludesCurrentProcessAudio = true
        config.sampleRate = 48_000
        config.channelCount = 1
        // Video is required by the stream but unused: keep it tiny and slow.
        config.width = 2
        config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)

        let stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: audioQueue)
        try stream.addStreamOutput(self, type: .screen, sampleHandlerQueue: audioQueue)
        try await stream.startCapture()
        self.stream = stream
    }

    func stop() async {
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        if let stream {
            try? await stream.stopCapture()
        }
        stream = nil
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .audio, sampleBuffer.isValid,
              let pcm = Self.pcmBuffer(from: sampleBuffer) else { return }
        onSystemBuffer?(pcm)
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        onError?("System audio stopped: \(error.localizedDescription)")
    }

    /// Copies a ScreenCaptureKit audio sample buffer into an AVAudioPCMBuffer.
    private static func pcmBuffer(from sampleBuffer: CMSampleBuffer) -> AVAudioPCMBuffer? {
        guard let desc = sampleBuffer.formatDescription,
              var asbd = desc.audioStreamBasicDescription,
              let format = AVAudioFormat(streamDescription: &asbd) else { return nil }
        let frames = AVAudioFrameCount(sampleBuffer.numSamples)
        guard frames > 0,
              let pcm = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames) else { return nil }
        pcm.frameLength = frames
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer, at: 0, frameCount: Int32(frames), into: pcm.mutableAudioBufferList)
        return status == noErr ? pcm : nil
    }
}
