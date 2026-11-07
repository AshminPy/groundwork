import Foundation

/// Streaming client for the Claude Messages API (raw HTTP; there is no official Swift SDK).
///
/// It rebuilds every content block from the stream (text, thinking + signature, server tool
/// use, search results, citations) so the assistant turn can be sent back unchanged on the
/// next request. Editing or dropping blocks from history breaks thinking-block replay.
struct ClaudeClient {
    var apiKey: String
    var model: String
    var effort: String
    var searchDomains: [String]

    struct Result {
        var content: [[String: Any]]
        var stopReason: String?
    }

    private var tools: [[String: Any]] {
        guard !searchDomains.isEmpty else { return [] }
        return [
            ["type": "web_search_20260209", "name": "web_search",
             "max_uses": 3, "allowed_domains": searchDomains],
            ["type": "web_fetch_20260209", "name": "web_fetch",
             "max_uses": 2, "allowed_domains": searchDomains],
        ]
    }

    func stream(system: String, messages: [[String: Any]],
                onText: @escaping @MainActor (String) -> Void) async throws -> Result {
        var body: [String: Any] = [
            "model": model,
            "max_tokens": 8000,
            "stream": true,
            // System prompt (persona + team knowledge) is stable for the session: cache it.
            "system": [["type": "text", "text": system, "cache_control": ["type": "ephemeral"]]],
            // Automatic caching of the growing conversation prefix.
            "cache_control": ["type": "ephemeral"],
            "messages": messages,
            "output_config": ["effort": effort],
            // Server-side fallback if a safety classifier declines the request.
            "fallbacks": "default",
        ]
        if !tools.isEmpty { body["tools"] = tools }

        var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        req.httpMethod = "POST"
        req.timeoutInterval = 180
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

        var blocks: [Int: [String: Any]] = [:]
        var partialJSON: [Int: String] = [:]
        var stopReason: String?

        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else { continue }
            guard let event = try? JSONSerialization.jsonObject(with: Data(line.dropFirst(6).utf8)) as? [String: Any],
                  let type = event["type"] as? String else { continue }
            let index = event["index"] as? Int ?? 0
            switch type {
            case "content_block_start":
                blocks[index] = event["content_block"] as? [String: Any] ?? [:]
            case "content_block_delta":
                guard var block = blocks[index], let delta = event["delta"] as? [String: Any] else { continue }
                switch delta["type"] as? String {
                case "text_delta":
                    let text = delta["text"] as? String ?? ""
                    block["text"] = (block["text"] as? String ?? "") + text
                    await onText(text)
                case "thinking_delta":
                    block["thinking"] = (block["thinking"] as? String ?? "") + (delta["thinking"] as? String ?? "")
                case "signature_delta":
                    block["signature"] = delta["signature"]
                case "input_json_delta":
                    partialJSON[index, default: ""] += delta["partial_json"] as? String ?? ""
                case "citations_delta":
                    if let citation = delta["citation"] {
                        block["citations"] = (block["citations"] as? [Any] ?? []) + [citation]
                    }
                default:
                    break
                }
                blocks[index] = block
            case "content_block_stop":
                if let json = partialJSON[index], var block = blocks[index] {
                    block["input"] = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) ?? [String: Any]()
                    blocks[index] = block
                }
            case "message_delta":
                if let delta = event["delta"] as? [String: Any], let reason = delta["stop_reason"] as? String {
                    stopReason = reason
                }
            case "error":
                let msg = (event["error"] as? [String: Any])?["message"] as? String ?? "unknown error"
                throw NSError(domain: "ClaudeClient", code: -1, userInfo: [NSLocalizedDescriptionKey: msg])
            default:
                continue
            }
        }
        return Result(content: blocks.keys.sorted().compactMap { blocks[$0] }, stopReason: stopReason)
    }

    /// Source links found in an assistant turn: citations first, then search results.
    static func sources(in content: [[String: Any]]) -> [(title: String, url: String)] {
        var seen = Set<String>()
        var out: [(title: String, url: String)] = []
        func add(_ title: String?, _ url: String?) {
            guard let url, !url.isEmpty, seen.insert(url).inserted else { return }
            out.append((title: title ?? url, url: url))
        }
        for block in content {
            for c in block["citations"] as? [[String: Any]] ?? [] {
                add(c["title"] as? String, c["url"] as? String)
            }
        }
        for block in content where (block["type"] as? String) == "web_search_tool_result" {
            for r in block["content"] as? [[String: Any]] ?? [] {
                add(r["title"] as? String, r["url"] as? String)
            }
        }
        return out
    }
}
