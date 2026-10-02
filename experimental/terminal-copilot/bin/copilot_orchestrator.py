#!/usr/bin/env python3
"""Terminal Copilot — orchestrator (EXPERIMENTAL, LOCAL ONLY).

NOT a Groundwork feature. See ../README.md and ../docs/DECISIONS.md.

Invoked by the Hammerspoon module with a single argument: the TTY path of
the terminal the user activated from (captured at activation time — see
docs/DECISIONS.md #1). Does exactly five things, in order:

  1. Load the sanitized context file that shell/context-hook.sh writes for
     that TTY (if present).
  2. Record a short, BOUNDED audio clip from the default microphone — never
     continuous (see docs/DECISIONS.md and the task's security requirements).
  3. Transcribe it locally with faster-whisper (reused, not reimplemented).
  4. Call the user's own installed `claude` CLI, headless, in
     --permission-mode plan (suggest-only — see docs/DECISIONS.md #4).
  5. Print exactly one line of JSON to stdout: either
     {"cwd": ..., "explanation": ..., "suggested_command": ...} or
     {"error": "..."}.

Nothing is executed automatically. No credentials are read, stored, or
passed through this script — `claude` uses whatever auth it already has
configured. All diagnostic/debug output goes to stderr, never stdout, so
stdout stays valid JSON for the Hammerspoon side to parse.

Dependencies (install separately, see ../install-local.sh):
  - faster-whisper (MIT)   — pip install faster-whisper
  - sounddevice (BSD)      — pip install sounddevice
  - numpy (BSD)            — pip install numpy
  - the `claude` CLI already installed and authenticated.

NOT runtime-tested from this session (no microphone, no audio hardware
available in this environment). See ../tests/MANUAL_TEST_PROCEDURE.md.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

GROUNDWORK_COPILOT_DIR = Path(
    os.environ.get("GROUNDWORK_COPILOT_DIR", str(Path.home() / ".groundwork-copilot"))
)
SESSIONS_DIR = GROUNDWORK_COPILOT_DIR / "sessions"

MAX_RECORD_SECONDS = float(os.environ.get("GROUNDWORK_COPILOT_MAX_RECORD_SECONDS", "10"))
SAMPLE_RATE = 16000  # what faster-whisper/whisper expect
WHISPER_MODEL_SIZE = os.environ.get("GROUNDWORK_COPILOT_WHISPER_MODEL", "base")
CLAUDE_TIMEOUT_SECONDS = float(os.environ.get("GROUNDWORK_COPILOT_CLAUDE_TIMEOUT", "25"))

# A TTY path looks like /dev/ttys003 or /dev/pts/3. Reject anything else
# before using it to build a filesystem path (defense in depth, even though
# the Hammerspoon side only ever sends what AppleScript returns).
_TTY_PATTERN = re.compile(r"^/dev/(ttys\d+|pts/\d+|tty[a-zA-Z0-9]+)$")


def emit_error(message: str) -> None:
    print(json.dumps({"error": message}))


def validate_tty(tty: str) -> str | None:
    if _TTY_PATTERN.match(tty):
        return tty
    return None


def tty_to_filename(tty: str) -> str:
    return tty.replace("/", "_")


def load_context(tty: str) -> dict:
    """Returns the sanitized context dict, or a minimal stand-in if the
    context file doesn't exist yet (e.g. the shell hook isn't installed in
    that particular shell session)."""
    context_file = SESSIONS_DIR / f"{tty_to_filename(tty)}.json"
    if not context_file.exists():
        return {
            "tty": tty,
            "cwd": None,
            "repo_root": None,
            "git_branch": None,
            "shell": None,
            "last_command": None,
            "last_exit_code": None,
            "_context_available": False,
        }
    try:
        data = json.loads(context_file.read_text())
        data["_context_available"] = True
        return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: could not read context file: {exc}", file=sys.stderr)
        return {
            "tty": tty, "cwd": None, "repo_root": None, "git_branch": None,
            "shell": None, "last_command": None, "last_exit_code": None,
            "_context_available": False,
        }


def record_audio_bounded(max_seconds: float) -> str:
    """Records from the default microphone for up to max_seconds, stopping
    early once speech has started and then gone quiet for a short window.
    Writes a temporary WAV file and returns its path. The caller is
    responsible for deleting it. Never records longer than max_seconds
    regardless of audio content — this is the hard bound that keeps the
    microphone from ever being effectively 'continuous'.
    """
    import numpy as np
    import sounddevice as sd
    import wave

    chunk_seconds = 0.5
    chunk_frames = int(SAMPLE_RATE * chunk_seconds)
    max_chunks = int(max_seconds / chunk_seconds)

    # Simple energy-based auto-stop: once we've seen at least one "loud"
    # chunk (speech started), stop after `quiet_chunks_to_stop` consecutive
    # quiet chunks. This is a minimal, dependency-free heuristic — not a
    # real VAD library — adequate for an MVP, not claimed to be robust.
    quiet_chunks_to_stop = 3
    loud_threshold = 0.01  # RMS threshold on float32 [-1, 1] samples; UNVERIFIED
    # against a real microphone — may need tuning once this runs on real
    # hardware (see tests/MANUAL_TEST_PROCEDURE.md).

    frames = []
    speech_started = False
    quiet_run = 0

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    with stream:
        for _ in range(max_chunks):
            chunk, _overflow = stream.read(chunk_frames)
            frames.append(chunk.copy())
            rms = float(np.sqrt(np.mean(np.square(chunk))))
            if rms >= loud_threshold:
                speech_started = True
                quiet_run = 0
            elif speech_started:
                quiet_run += 1
                if quiet_run >= quiet_chunks_to_stop:
                    break

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype="float32")

    fd, path = tempfile.mkstemp(suffix=".wav", prefix="groundwork-copilot-")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(SAMPLE_RATE)
        pcm16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wf.writeframes(pcm16.tobytes())

    return path


def transcribe_audio(wav_path: str) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(wav_path, language="en")
    return " ".join(segment.text.strip() for segment in segments).strip()


def build_prompt(user_request: str, context: dict) -> str:
    lines = [
        "You are a terminal command assistant. Respond in EXACTLY this format:",
        "",
        "<one short paragraph explanation, plain text, no markdown headers>",
        "COMMAND: <a single shell command, only if one is genuinely appropriate>",
        "",
        "If no specific command applies, omit the COMMAND: line entirely. "
        "Never include more than one COMMAND: line. Never include any other "
        "formatting, code fences, or extra commentary.",
        "",
        f"User's spoken request: {user_request}",
        "",
        "Terminal context (sanitized; command output was NOT captured — rely "
        "on the user's request above for any error details):",
    ]
    if context.get("_context_available"):
        lines.append(f"- Working directory: {context.get('cwd') or 'unknown'}")
        if context.get("repo_root"):
            lines.append(f"- Git repository root: {context['repo_root']}")
        if context.get("git_branch"):
            lines.append(f"- Git branch: {context['git_branch']}")
        if context.get("shell"):
            lines.append(f"- Shell: {context['shell']}")
        if context.get("last_command"):
            lines.append(
                f"- Last command run: {context['last_command']} "
                f"(exit code {context.get('last_exit_code')})"
            )
    else:
        lines.append(
            "- (No context available for this terminal — the shell context "
            "hook may not be installed in this shell session.)"
        )
    return "\n".join(lines)


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--permission-mode", "plan"],
        capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def parse_claude_response(raw: str) -> tuple[str, str | None]:
    command_match = re.search(r"^COMMAND:\s*(.+)$", raw, flags=re.MULTILINE)
    if command_match:
        explanation = raw[: command_match.start()].strip()
        command = command_match.group(1).strip()
        return explanation, (command or None)
    return raw.strip(), None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tty", required=True)
    args = parser.parse_args()

    tty = validate_tty(args.tty)
    if tty is None:
        emit_error(f"Invalid TTY argument: {args.tty!r}")
        return 1

    context = load_context(tty)

    wav_path = None
    try:
        wav_path = record_audio_bounded(MAX_RECORD_SECONDS)
        user_request = transcribe_audio(wav_path)
    except Exception as exc:  # noqa: BLE001 - must always emit valid JSON, never a traceback on stdout
        print(f"error during recording/transcription: {exc}", file=sys.stderr)
        emit_error(f"Could not record or transcribe audio: {exc}")
        return 1
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)  # never persist audio beyond this single request

    if not user_request:
        emit_error("No speech was detected. Try again and speak right after the hotkey.")
        return 1

    prompt = build_prompt(user_request, context)

    try:
        raw_response = call_claude(prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"error calling claude: {exc}", file=sys.stderr)
        emit_error(f"Claude call failed: {exc}")
        return 1

    explanation, suggested_command = parse_claude_response(raw_response)

    print(json.dumps({
        "cwd": context.get("cwd"),
        "explanation": explanation,
        "suggested_command": suggested_command,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
