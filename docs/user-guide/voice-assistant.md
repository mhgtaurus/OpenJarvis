# Voice Assistant

`jarvis assistant` runs OpenJarvis hands-free. It listens continuously, reacts when
you address it with a wake word, sends your request to the agent, and speaks the
answer. For push-to-talk in a normal chat session, use `jarvis chat --voice` instead.

## Setup

```bash
pip install 'OpenJarvis[speech]'   # speech-to-text and text-to-speech backends
jarvis assistant
```

You need a working microphone and speakers, and a running inference engine
(for example Ollama). Speech backends are picked from your `[speech]` config, the
same way as for `jarvis chat --voice`.

## Usage

| You say | What happens |
|---|---|
| "Jarvis, what's on my calendar today?" | Jarvis answers the request out loud |
| "Hey Jarvis" / "Jarvis" | Jarvis replies "Yes?" and waits for your command |
| "What time is it, Jarvis" | The wake word may also come at the end |
| "Jarvis, goodbye" | Jarvis says goodbye and exits (`shut down`, `tschüss`, `beenden` also work) |
| Anything without the wake word | Ignored |

Press Ctrl-C at any time to stop.

The wake word is only recognized at the start of an utterance (within the first
three words) or at its end, so a sentence that merely mentions "Jarvis" in the
middle does not trigger it.

## Options

| Option | Description |
|---|---|
| `-m`, `--model` | Model override |
| `-a`, `--agent` | Agent type, for example `orchestrator` |
| `--tools` | Comma-separated tool names the agent may use |
| `--wake-word` | Additional wake word, repeatable (default: `jarvis`) |
| `--no-speak` | Print replies instead of speaking them |

```bash
jarvis assistant -a orchestrator --tools web_search,calculator
jarvis assistant --wake-word computer --no-speak
```

## Limitations

- The wake word is detected by transcribing each utterance with the configured
  speech-to-text backend, not by a dedicated wake-word model. With a cloud STT
  backend, everything said near the microphone is sent to that provider; use a
  local backend such as faster-whisper to keep audio on your machine.
- The assistant remembers only the last six exchanges of the current run, so
  follow-ups like "and tomorrow?" work. Nothing is kept after you stop it.
