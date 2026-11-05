# Hands-Free SRE: investigation and decision

**Status: NOT NEEDED as new code; the acceptance demonstration is BLOCKED in this environment.** Claude Code already has voice
input, listening indicators, cancel keys and permission prompts. Groundwork already has the read-only, terminal-bound context
command (`groundwork copilot explain`). A second voice layer would duplicate the first and would need a microphone permission
that this programme was told not to grant. What is missing is a trial on a machine with a microphone, which only the owner can run.

## What the task asked for

LISTEN → UNDERSTAND → REASON → EXPLAIN → REQUEST APPROVAL → EXECUTE → OBSERVE → VALIDATE, in three modes (OBSERVE read-only,
ASSIST suggestions, OPERATE authorised execution), with: correct session binding, explicit authorisation for consequential
changes, safe interruption, no cross-session routing, no hidden execution, a clear "listening / acting" indication, and no paid
speech provider as a mandatory dependency.

## What already exists

| Need | Provided by | Evidence |
|---|---|---|
| Speech to text | Claude Code `/voice` (hold or tap to record, language setting, coding vocabulary hints) | official page, read 2026-10-11: https://code.claude.com/docs/en/voice-dictation |
| "Listening" indication | the footer shows `listening…` (hold mode) or `● REC · tap to send` (tap mode); the cursor becomes a level meter | same page |
| Cancel / interruption | `Esc` or `Ctrl+C` stops the microphone, discards the transcript and restores the prompt; recording also stops after 15 s of silence or 2 minutes | same page |
| No hidden submission | by default the transcript is inserted and waits for `Enter`; `voice.autoSubmit` or tap mode submits only when the transcript is at least three words | same page |
| Approval before execution | Claude Code's own permission prompts and modes. The voice page does not say voice changes them (INFERENCE: they apply as usual; not exercised here) | Claude Code docs |
| Read-only context of one terminal | `groundwork copilot explain`: its own tmux pane only (tty + process ancestry proof), `--stdin` for any other terminal, redacted, no tools, never runs a suggestion | tests and reviews in the Copilot PR |
| Text to speech | not provided by Claude Code or Groundwork | none read |

Constraints of `/voice`, from the same page: it "streams your recorded audio to Anthropic's servers for transcription. Audio is
not processed locally." It needs a claude.ai sign-in (it is not available with an API key, Amazon Bedrock, Google Cloud or
Microsoft Foundry), a local microphone, and it does not work in cloud sessions or SSH sessions. An administrator policy can turn
it off. Transcription does not consume tokens.

## Local alternatives (only if a fully local path is required)

| Option | What was read | Status |
|---|---|---|
| whisper.cpp | README: MIT licence, "plain C/C++ implementation without dependencies", "Apple Silicon first-class citizen", a demo "fully offline, on-device"; model files from 75 MiB (tiny) to 2.9 GiB (large). The README does not state whether inference needs a network after the model download. | read 2026-10-11 (https://github.com/ggml-org/whisper.cpp) |
| Apple Speech framework (on-device recognition) | the Apple documentation page did not render for the fetch tool | UNVERIFIED |
| Vosk | its host was unreachable from the build container | UNVERIFIED |
| Text to speech: macOS `say`, Linux `espeak` | not checked; neither is installed in the build container | UNVERIFIED |

Any of these would be new code: a listener process, a microphone permission, a model download and an audio device.

## What the build container can and cannot show

Observed in the build container: no `/dev/snd`; none of `arecord`, `sox`, `ffmpeg`, `espeak`, `say` installed; no Python speech
package importable; `huggingface.co` and `alphacephei.com` unreachable. It is a cloud session, which `/voice` does not support.
So voice input, the listening indicator and cancel-by-key cannot be exercised here. **RUNTIME VALIDATION REQUIRED** on a machine
with a microphone.

## Which acceptance items are covered

| Acceptance item | State |
|---|---|
| Voice input | BLOCKED here; native `/voice` on the owner's machine is the way to test it |
| Correct terminal-context interpretation | covered by the Copilot PR (real two-pane tmux test: each pane's question is answered from that pane only) |
| A safe read-only investigation | covered by the Copilot PR (no tools, redacted, never runs a suggestion; one real model call on a genuine traceback) |
| Authorised action handling | not built, by design: Claude Code's permission prompts are the approval flow; Copilot refuses to execute |
| Interruption | covered for Copilot (Ctrl-C and SIGTERM stop the model call and leave nothing running); `/voice` cancel is native and untested here |

## Decision and the one thing that does not fit

No code is added. The one conflict is session binding: the voice session is a Claude Code prompt in one pane, while the failure is
usually in another. Copilot refuses to read another pane on purpose (no cross-session routing). The no-code way to combine them is
to bring the output to the voice session: `some_cmd 2>&1 | groundwork copilot explain --stdin --question "…"`, or paste the output
into the dictated prompt. A hands-free OPERATE mode would be Claude Code itself, in the failing terminal's project, under its own
permission mode; Groundwork would add policy text only.

## What would have to be true before building anything

1. The owner tries `/voice` with `groundwork copilot explain` on a real machine and names a gap that native features leave open.
2. The gap needs a microphone outside Claude Code, in which case the microphone permission, the model source and the audio retention
   are decided by the owner first, and the build starts as an isolated proof of concept.
3. Execution stays with Claude Code's permission prompts; nothing is run from transcribed speech without a typed confirmation.
