import Foundation

/// Local files: team knowledge in, session notes and decision records out.
/// Everything lives under ~/Documents/ArchitectCoach/ so you can open and edit it yourself.
enum Storage {
    static let root = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("ArchitectCoach", isDirectory: true)
    static let knowledgeDir = root.appendingPathComponent("knowledge", isDirectory: true)
    static let sessionsDir = root.appendingPathComponent("sessions", isDirectory: true)

    /// Upper bound for knowledge sent with every request (characters). Larger folders are cut
    /// and the status line says so.
    static let maxKnowledgeChars = 150_000

    static func ensureFolders() {
        for dir in [knowledgeDir, sessionsDir] {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
    }

    /// Reads .md and .txt files from the knowledge folder (ADRs, standards, ticket notes).
    static func loadKnowledge() -> (text: String, files: Int, truncated: Bool) {
        ensureFolders()
        let files = ((try? FileManager.default.contentsOfDirectory(at: knowledgeDir, includingPropertiesForKeys: nil)) ?? [])
            .filter { ["md", "txt"].contains($0.pathExtension.lowercased()) }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
        var out = ""
        var truncated = false
        for file in files {
            guard let body = try? String(contentsOf: file, encoding: .utf8) else { continue }
            let doc = "<doc name=\"\(file.lastPathComponent)\">\n\(body)\n</doc>\n"
            if out.count + doc.count > maxKnowledgeChars { truncated = true; break }
            out += doc
        }
        return (out, files.count, truncated)
    }

    static func newSessionFile() -> URL {
        ensureFolders()
        let stamp = ISO8601DateFormatter.string(from: Date(), timeZone: .current,
                                                formatOptions: [.withFullDate, .withTime, .withColonSeparatorInTime])
            .replacingOccurrences(of: ":", with: "-")
        return sessionsDir.appendingPathComponent("session-\(stamp).md")
    }

    static func append(_ text: String, to file: URL) {
        let data = Data(text.utf8)
        if let handle = try? FileHandle(forWritingTo: file) {
            handle.seekToEndOfFile()
            handle.write(data)
            try? handle.close()
        } else {
            try? data.write(to: file)
        }
    }
}
