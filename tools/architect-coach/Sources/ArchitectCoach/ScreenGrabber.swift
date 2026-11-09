import AppKit
import ScreenCaptureKit

/// Takes one screenshot of the main display when the user asks for an answer.
/// The copilot's own window is excluded so it does not read its own output.
enum ScreenGrabber {
    /// Long-edge limit. Larger images are downscaled by the API anyway and cost more latency.
    static let maxEdge: CGFloat = 1568

    static func captureJPEG() async throws -> Data {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            throw NSError(domain: "ScreenGrabber", code: 1,
                          userInfo: [NSLocalizedDescriptionKey: "No display found"])
        }
        let ownApps = content.applications.filter {
            $0.processID == ProcessInfo.processInfo.processIdentifier
        }
        let filter = SCContentFilter(display: display, excludingApplications: ownApps, exceptingWindows: [])

        let scale = min(1, maxEdge / CGFloat(max(display.width, display.height)))
        let config = SCStreamConfiguration()
        config.width = Int(CGFloat(display.width) * scale)
        config.height = Int(CGFloat(display.height) * scale)
        config.showsCursor = false

        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        let rep = NSBitmapImageRep(cgImage: image)
        guard let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.7]) else {
            throw NSError(domain: "ScreenGrabber", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "JPEG encoding failed"])
        }
        return data
    }
}
