# Voice Assistant

`jarvis assistant` runs OpenJarvis hands-free. It listens continuously, reacts when
you address it with a wake word, sends your request to the agent, and speaks the
answer. For push-to-talk in a normal chat session, use `jarvis chat --voice` instead.

## Setup

```bash
pip install 'OpenJarvis[speech]'     # speech-to-text and text-to-speech backends
pip install 'OpenJarvis[wakeword]'   # optional: always-on "Hey Jarvis" model
jarvis assistant
```

You need a working microphone and speakers, and a running inference engine
(for example Ollama). Speech backends are picked from your `[speech]` config, the
same way as for `jarvis chat --voice`.

## Wake word detection

There are two ways to detect "Jarvis", chosen with `--wake-engine`:

| Engine | How it works |
|---|---|
| `model` | A small [openWakeWord](https://github.com/dscripka/openWakeWord) model ("Hey Jarvis") listens to the microphone locally and only starts recording and transcribing after it fires. Light on CPU, and no audio is transcribed or sent anywhere until you say the wake word. |
| `stt` | Every utterance is transcribed by the speech-to-text backend and checked for the wake word. Works without extra packages and supports custom `--wake-word`s. |
| `auto` (default) | `model` if openWakeWord is installed and no `--wake-word` is given, otherwise `stt`. |

With the model engine, Jarvis answers "Yes?" after the wake word and then records
your request. If it triggers too rarely or too often, adjust `--wake-threshold`
(default 0.5; lower is more sensitive).

## Usage

| You say | What happens |
|---|---|
| "Jarvis, what's on my calendar today?" | Jarvis answers the request out loud (`stt` engine) |
| "Hey Jarvis" / "Jarvis" | Jarvis replies "Yes?" and waits for your command |
| "What time is it, Jarvis" | The wake word may also come at the end (`stt` engine) |
| "Jarvis, goodbye" | Jarvis says goodbye and exits (`shut down`, `tschüss`, `beenden` also work) |
| Anything without the wake word | Ignored |

Press Ctrl-C at any time to stop.

With the `stt` engine the wake word is only recognized at the start of an utterance (within the first
three words) or at its end, so a sentence that merely mentions "Jarvis" in the
middle does not trigger it.

## Options

| Option | Description |
|---|---|
| `-m`, `--model` | Model override |
| `-a`, `--agent` | Agent type, for example `orchestrator` |
| `--tools` | Comma-separated tool names the agent may use |
| `--wake-word` | Additional wake word, repeatable (default: `jarvis`); `stt` engine only |
| `--wake-engine` | `auto` (default), `model` or `stt` |
| `--wake-threshold` | Wake-word model sensitivity, 0 to 1 (default 0.5) |
| `--no-speak` | Print replies instead of speaking them |

```bash
jarvis assistant -a orchestrator --tools web_search,calculator
jarvis assistant --wake-word computer --no-speak   # picks the stt engine
jarvis assistant --wake-engine model --wake-threshold 0.4
```

## Smart home

When [Home Assistant](smart-home.md) is configured, `jarvis assistant` enables the
`home_assistant` tool automatically (using the `orchestrator` agent unless you
pass `-a`), so you can say "Hey Jarvis, turn off the kitchen lights".

## Limitations

- With the `stt` engine, every utterance is transcribed to look for the wake
  word. With a cloud STT backend, everything said near the microphone is sent
  to that provider; use the `model` engine or a local backend such as
  faster-whisper to keep audio on your machine.
- The wake-word model only knows "Hey Jarvis"; custom wake words need the
  `stt` engine.
- The assistant remembers only the last six exchanges of the current run, so
  follow-ups like "and tomorrow?" work. Nothing is kept after you stop it.
