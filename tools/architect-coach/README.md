# Architect Coach (macOS voice app)

A voice-first cloud architect coach for AWS and Google Cloud. You talk to it like a senior colleague in a meeting: brainstorm ideas, ask for advice, or have it teach you to reason like a principal architect. It answers out loud, shows the text and source links, and saves notes and decision records.

Status: **not compiled or tested yet.** It was written in a Linux container with no Swift toolchain. Build it on a Mac and expect a few small compile fixes on the first run.

## How a conversation works

```
you speak ─► on-device speech-to-text ─► pause ≈1.4 s = your turn ends
          ─► Claude (persona + team knowledge + conversation so far, optional doc search, optional screenshot)
          ─► reply streams ─► spoken sentence by sentence ─► back to listening
```

- **Hands-free turn-taking.** Just talk; pause to hand over. The mic is ignored while the coach thinks or speaks, so it never hears itself. Press `⌃⌥Space` (or Interrupt) to cut it off and take the floor.
- **Four modes** (picker at the top), same as Groundwork's coach mode:
  - **Brainstorm**: two or three different options, then "which constraint matters most?"
  - **Advise**: one recommendation, the tradeoff, what not to build, how to prove it.
  - **Teach me**: asks for *your* proposal first, then challenges it one question at a time and names the principle.
  - **Review**: you describe or show a design; findings ordered by risk.
- **Show my screen**: attaches one screenshot to your next turn (architecture diagram, console, ticket).
- **Type instead of talking**: the text box works in or out of a session. Out of a session, answers are written, not spoken.
- **Write decision record (ADR)**: turns the conversation into an ADR saved next to the session notes.

## Grounding and evidence

| Source | How |
|---|---|
| Your team's standards, ADRs, ticket notes | `.md`/`.txt` files in `~/Documents/ArchitectCoach/knowledge/`, loaded at session start (up to 150,000 characters) and cached |
| Official docs | Claude's web search and fetch tools, limited to the domains in Settings (default: AWS, Google Cloud, CloudAMQP, RabbitMQ, Kubernetes, HashiCorp) |
| Frameworks | AWS Well-Architected and Google Cloud Well-Architected pillars are in the persona |

The persona must name the source of anything it relies on, verify limits, prices and feature availability or say it hasn't, and say "I'm not sure" when it isn't. Links appear under each reply and in the saved notes.

## Build and run

Needs macOS 14+ and Xcode 15+.

```bash
cd tools/architect-coach
./build-app.sh
open build/ArchitectCoach.app
```

1. Allow **Microphone** and **Speech Recognition**. **Screen Recording** is needed only for Show my screen.
2. Settings (`⌘,`): paste your Anthropic API key (stored in the Keychain). Pick a voice. For a natural voice, first download a Premium voice in System Settings > Accessibility > Spoken Content > System voice > Manage Voices.
3. Put a few team documents in `~/Documents/ArchitectCoach/knowledge/` (for example sanitized CloudAMQP ticket notes and your standards).
4. Press **Start talking**.

Defaults: model `claude-opus-5-5`, effort `low` (quick conversational turns; use `medium` for deeper design work). Server-side refusal fallback is on.

## Files

| File | Role |
|---|---|
| `Coach.swift` | Conversation loop, append-only history, session notes, ADR export |
| `Listener.swift` | Mic capture and end-of-turn detection on Apple's speech recognizer |
| `Speaker.swift` | Sentence-by-sentence speech while the reply streams; strips markdown/URLs |
| `ClaudeClient.swift` | Streaming Messages API; rebuilds every block (thinking, search, citations) so history replays unchanged; prompt caching |
| `CoachPrompt.swift` | Persona, modes, evidence rules, voice style (kept in step with Groundwork's `modes/coach.md`) |
| `Storage.swift` | Knowledge folder in, notes and ADRs out |
| `ScreenGrabber.swift`, `Hotkey.swift`, `Keychain.swift` | Screenshot on request, global hotkey, API key storage |

## Limits and risks

- **It can be wrong.** Treat answers as a strong first draft. Production, IAM, data-destructive or costly changes still need review by your senior architect.
- **What leaves the Mac:** each turn sends the conversation, your knowledge folder (cached), and a screenshot if you asked. Check your company's policy before putting internal tickets or designs in the knowledge folder. If direct API use is not allowed, the same design can call Claude through Amazon Bedrock or Google Vertex AI instead (not built).
- **Latency:** about 1.4 s end-of-turn pause + time to Claude's first sentence. A doc search adds a few seconds. Lower the pause in `Listener.swift` (`silenceSeconds`) if it feels slow, raise it if it cuts you off.
- **Half-duplex:** you can't talk over it; interrupt with the hotkey. Headphones are not required.
- **Long conversations** grow in cost; use More > New topic. History is never edited (required for thinking-block replay), so the only way to shrink it is a new topic.
- **Persona:** it does not imitate a real person. If you want it modelled on your principal architect's approach, ask them to contribute their rules of thumb and past decisions to the knowledge folder.
- **Voice quality** depends on the installed system voice. A neural cloud voice could be added later.
