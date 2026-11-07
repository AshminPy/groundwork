# Meeting Copilot (macOS)

A small native macOS app. It listens to a call, transcribes both sides on your Mac, and can take a screenshot when you ask. It then streams a short suggested answer from Claude.

Status: **not compiled or tested yet.** The code was written in a Linux container with no Swift toolchain. Build it on a Mac and expect to fix small compile errors on the first run.

## What it does

| Part | How | File |
|---|---|---|
| Your voice ("Me") | `AVAudioEngine` microphone tap | `AudioCapture.swift` |
| Other people ("Them") | ScreenCaptureKit system-audio capture (macOS 13+), works with Zoom, Meet, Teams and others | `AudioCapture.swift` |
| Speech to text | Apple `SFSpeechRecognizer`, on-device when the Mac supports it | `Transcriber.swift` |
| Screen | One `SCScreenshotManager` screenshot per request, with the copilot's own window left out | `ScreenGrabber.swift` |
| Answer | Claude Messages API, streamed (raw HTTP; there is no official Swift SDK) | `ClaudeClient.swift` |
| Trigger | **Answer** button, `⌘↩`, global hotkey `⌃⌥Space`, or optional auto-answer when "Them" ends a sentence with `?` | `Hotkey.swift`, `Copilot.swift` |
| API key | macOS Keychain | `Keychain.swift` |

## Data flow

```
mic ──► Transcriber("Me") ──┐
                            ├─► rolling 5-min transcript ─┐
system audio ─► Transcriber("Them") ┘                     ├─► Claude (stream) ─► answer panel
your notes (Settings) ────────────────────────────────────┤
screenshot (only when you press Answer, if enabled) ──────┘
```

- Audio and transcription stay on the Mac when on-device recognition is available. The status line shows which mode is in use.
- **What goes to Anthropic, per request:** the last 5 minutes of transcript, your notes, and one screenshot if "Include screen" is on. Turn the screenshot off when sensitive content is on screen.

## Build and run

Needs macOS 14+ and Xcode 15+ (or the matching command-line tools).

```bash
cd tools/meeting-copilot
./build-app.sh
open build/MeetingCopilot.app
```

1. On first start, allow **Microphone**, **Speech Recognition** and **Screen & System Audio Recording**. Screen Recording needs an app restart after you allow it.
2. Open Settings (`⌘,`). Paste your Anthropic API key and save it.
3. Add notes: the agenda, your background, key numbers, and anything you want answers grounded in. Answers are only as good as these notes.
4. Click **Start listening**. When a question comes, press `⌃⌥Space`.

Defaults: model `claude-opus-5-5`, effort `low` for speed. You can change both in Settings. Server-side refusal fallback (`fallbacks: "default"`) is on.

## Design choices and limits

- **Visible by design.** The window is not hidden from screen sharing. It does not try to avoid proctoring or detection tools. A "Recording" badge shows while it listens. If you need the panel off a shared screen, share one window instead of the whole screen.
- **Consent.** Recording or transcribing a call can need consent from everyone on it. The rules depend on where you and the others are; some places require all parties to agree. Tell people you are transcribing. Many interviews and exams forbid live AI help; check the rules first.
- **Honest answers.** The system prompt tells Claude to use only your notes, the transcript and the screen, never invent experience or numbers for you, and say "Not sure" when it lacks the facts.
- **Latency.** The answer usually starts after transcription catches up (about 1–2 s) plus the time until Claude's first token. Use `low` effort for live use.
- **Speaker labels** come from the audio source (mic vs system audio), not from voice recognition. If several people speak, they all show as "Them".
- **Recognizer limits.** Apple limits how long one recognition request can run, so each stream restarts about every 50 s. A word can be lost at the boundary. Apple's newer `SpeechAnalyzer` API (macOS 26) may do better; it is not used here.
- **Cost.** Each request sends up to 5 minutes of transcript plus a screenshot. Check current pricing at https://www.anthropic.com/pricing.

## About REA

[morluto/rea](https://github.com/morluto/rea) is a reverse-engineering MCP server (native binaries, Electron apps, websites). It has no audio capture, transcription or overlay code, so this app does not depend on it. It is not used to copy commercial products such as Cluely or Final Round AI; their licences usually forbid reverse engineering, and this app is built only on public Apple and Anthropic APIs.
