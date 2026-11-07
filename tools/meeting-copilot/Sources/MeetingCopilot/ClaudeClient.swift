import Foundation

/// Minimal streaming client for the Claude Messages API (raw HTTP; there is no official Swift SDK).
struct ClaudeClient {
    var apiKey: String
    var model: String = "claude-opus-5-5"
    /// "low" keeps answers fast enough for a live call. Raise it for harder questions.
    var effort: String = "low"

    static let systemPrompt = """
    You help the user answer questions during a live meeting. You get a recent transcript \
    ("Them" = other participants, "Me" = the user), optional notes the user wrote before \
    the call, and sometimes a screenshot of the user's screen.

    Rules:
    - Answer the most recent question asked by "Them" unless the user asks something else.
    - Start with a one-sentence answer the user can say out loud. Then give up to 4 short bullet points.
    - Use only facts from the transcript, the notes, the screenshot or well-established knowledge.
    - Never invent personal experience, numbers, names or results for the user. If the notes \
      do not cover it, say so and suggest an honest way to answer.
    - If you are not sure, say "Not sure" and suggest a clarifying question.
    - No preamble. Plain English. Keep it under 120 words.
    """

    /// Streams answer text. Calls `onDelta` for each text chunk.
    func streamAnswer(transcript: String, notes: String, screenshotJPEG: Data?,
                      instruction: String,
                      onDelta: @escaping @MainActor (String) -> Void) async throws {
        var content: [[String: Any]] = []
        if let jpeg = screenshotJPEG {
            content.append([
                "type": "image",
                "source": ["type": "base64", "media_type": "image/jpeg",
                           "data": jpeg.base64EncodedString()],
            ])
        }
        let text = """
        <notes>
        \(notes.isEmpty ? "(none)" : notes)
        </notes>

        <transcript>
        \(transcript.isEmpty ? "(empty)" : transcript)
        </transcript>

        \(instruction)
        """
        content.append(["type": "text", "text": text])

        let body: [String: Any] = [
            "model": model,
            "max_tokens": 4000,
            "stream": true,
            "system": Self.systemPrompt,
            "output_config": ["effort": effort],
            // Server-side fallback if a safety classifier declines the request.
            "fallbacks": "default",
            "messages": [["role": "user", "content": content]],
        ]

        var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        req.httpMethod = "POST"
        req.timeoutInterval = 120
        req.setValue("application/json", forHTTPHeaderField: "content-type")
        req.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        req.setValue("2026-10-21", forHTTPHeaderField: "anthropic-version")
        req.setValue("server-side-fallback-2026-07-01", forHTTPHeaderField: "anthropic-beta")
        req.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (bytes, response) = try await URLSession.shared.bytes(for: req)
        if let http = response as? HTTPURLResponse, http.statusCode != 200 {
            var errText = ""
            for try await line in bytes.lines { errText += line }
            throw NSError(domain: "ClaudeClient", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "HTTP \(http.statusCode): \(errText.prefix(400))"])
        }

        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else { continue }
            let json = Data(line.dropFirst(6).utf8)
            guard let event = try? JSONSerialization.jsonObject(with: json) as? [String: Any],
                  let type = event["type"] as? String else { continue }
            switch type {
            case "content_block_delta":
                if let delta = event["delta"] as? [String: Any],
                   delta["type"] as? String == "text_delta",
                   let chunk = delta["text"] as? String {
                    await onDelta(chunk)
                }
            case "message_delta":
                if let delta = event["delta"] as? [String: Any],
                   delta["stop_reason"] as? String == "refusal" {
                    await onDelta("\n\n[The model declined this request.]")
                }
            case "error":
                let msg = (event["error"] as? [String: Any])?["message"] as? String ?? "unknown error"
                throw NSError(domain: "ClaudeClient", code: -1,
                              userInfo: [NSLocalizedDescriptionKey: msg])
            default:
                continue
            }
        }
    }
}
