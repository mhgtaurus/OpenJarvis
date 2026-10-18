"""``jarvis assistant`` — hands-free "Hey Jarvis" voice assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import click
from rich.console import Console

DEFAULT_WAKE_WORDS = ("jarvis", "dschawis", "jarvies")
_HISTORY_TURNS = 6
DEFAULT_EXIT_PHRASES = ("goodbye", "good bye", "shut down", "tschüss", "beenden")


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def strip_wake_word(text: str, wake_words: Sequence[str]) -> Optional[str]:
    """Return the command after the wake word, ``""`` if only the wake word was
    said, or ``None`` if the wake word is absent.

    The wake word may appear anywhere in the first few words ("Hey Jarvis, ...",
    "Okay Jarvis ...") or at the end ("... Jarvis").
    """
    words = _normalize(text).split()
    for idx, word in enumerate(words):
        if word in wake_words:
            if idx <= 2:
                return " ".join(words[idx + 1 :])
            if idx == len(words) - 1:
                return " ".join(words[:idx])
    return None


def build_query(command: str, history: Sequence[tuple[str, str]]) -> str:
    """Prefix ``command`` with recent turns so follow-ups ("and tomorrow?") work."""
    if not history:
        return command
    turns = "\n".join(f"User: {u}\nJarvis: {a}" for u, a in history)
    return f"Conversation so far:\n{turns}\n\nUser: {command}"


_WAKE_MODEL = "hey_jarvis"
_WAKE_FRAME = 1280  # 80 ms at 16 kHz, the frame size openWakeWord expects


def wake_model_available() -> bool:
    """True if the optional openWakeWord dependency is importable."""
    try:
        import openwakeword  # noqa: F401
    except ImportError:
        return False
    return True


def wait_for_wake_word(
    frames: Iterable[object],
    predict: Callable[[object], dict],
    threshold: float,
) -> bool:
    """Consume audio ``frames`` until ``predict`` scores >= ``threshold``.

    Returns True on detection, False if ``frames`` ran out first.
    """
    for frame in frames:
        if max(predict(frame).values(), default=0.0) >= threshold:
            return True
    return False


def make_wake_model_waiter(threshold: float) -> Callable[[], None]:
    """Build a blocking "wait until someone says Hey Jarvis" callable."""
    import numpy as np
    import openwakeword
    import sounddevice as sd
    from openwakeword.model import Model

    paths = [p for p in openwakeword.get_pretrained_model_paths() if _WAKE_MODEL in p]
    if not paths:
        raise click.ClickException(f"openWakeWord has no '{_WAKE_MODEL}' model.")
    model = Model(wakeword_model_paths=paths)

    def frames() -> Iterable[object]:
        with sd.RawInputStream(
            samplerate=16000, channels=1, dtype="int16", blocksize=_WAKE_FRAME
        ) as stream:
            while True:
                raw, _ = stream.read(_WAKE_FRAME)
                yield np.frombuffer(bytes(raw), dtype=np.int16)

    def wait() -> None:
        model.reset()  # drop the previous trigger's activations
        wait_for_wake_word(frames(), model.predict, threshold)

    return wait


def resolve_agent_and_tools(
    agent: Optional[str], tools: Optional[Sequence[str]], smart_home: bool
) -> tuple[Optional[str], Optional[list[str]]]:
    """Enable the smart-home tool when configured; tools need an agent to run."""
    tool_list = list(tools) if tools else []
    if smart_home and "home_assistant" not in tool_list:
        tool_list.append("home_assistant")
    if tool_list and agent is None:
        agent = "orchestrator"
    return agent, tool_list or None


def is_exit(command: str, exit_phrases: Sequence[str] = DEFAULT_EXIT_PHRASES) -> bool:
    cmd = _normalize(command)
    return any(cmd.startswith(p) for p in exit_phrases)


@dataclass
class AssistantLoop:
    """Wake word -> command -> agent -> spoken reply, with injectable I/O."""

    listen: Callable[[], Optional[str]]  # record + transcribe; None if nothing heard
    answer: Callable[[str], str]
    speak: Callable[[str], None]
    wake_words: Sequence[str] = DEFAULT_WAKE_WORDS
    greeting: str = "Yes?"
    farewell: str = "Goodbye. Shutting down."
    log: Callable[[str], None] = field(default=lambda _msg: None)
    # When set, a wake-word model gates the loop instead of transcribing
    # everything: block until it fires, then record the command.
    wait_for_wake: Optional[Callable[[], None]] = None

    def step(self) -> bool:
        """Handle one utterance. Returns False when the assistant should exit."""
        if self.wait_for_wake is not None:
            self.wait_for_wake()
            self.speak(self.greeting)
            heard = (self.listen() or "").strip()
            if not heard:
                return True
            stripped = strip_wake_word(heard, self.wake_words)
            command = heard if stripped is None else stripped
            if not command:
                return True
        else:
            heard = self.listen()
            if not heard:
                return True
            command = strip_wake_word(heard, self.wake_words)
            if command is None:
                return True  # not addressed to us
        if not command:
            self.speak(self.greeting)
            command = (self.listen() or "").strip()
            if not command:
                return True
        if is_exit(command):
            self.speak(self.farewell)
            return False
        self.log(f"> {command}")
        reply = self.answer(command)
        self.log(reply)
        if reply:
            self.speak(reply)
        return True

    def run(self) -> None:
        while self.step():
            pass


@click.command()
@click.option("-m", "--model", "model_name", default=None, help="Model override.")
@click.option("-a", "--agent", "agent_name", default=None, help="Agent type.")
@click.option("--tools", default=None, help="Comma-separated tool names.")
@click.option(
    "--wake-word",
    "wake_words",
    multiple=True,
    help="Additional wake word (repeatable). Default: 'jarvis'.",
)
@click.option(
    "--wake-engine",
    type=click.Choice(["auto", "model", "stt"]),
    default="auto",
    show_default=True,
    help=(
        "How 'Hey Jarvis' is detected: 'model' uses openWakeWord (light, always-on), "
        "'stt' transcribes every utterance, 'auto' picks 'model' when installed "
        "and no custom --wake-word is given."
    ),
)
@click.option(
    "--wake-threshold",
    type=click.FloatRange(0.0, 1.0),
    default=0.5,
    show_default=True,
    help="Wake-word model score needed to trigger (lower = more sensitive).",
)
@click.option("--no-speak", is_flag=True, help="Print replies instead of speaking.")
def assistant(
    model_name: str | None,
    agent_name: str | None,
    tools: str | None,
    wake_words: tuple[str, ...],
    wake_engine: str,
    wake_threshold: float,
    no_speak: bool,
) -> None:
    """Run Jarvis hands-free: say "Jarvis, <request>" and hear the answer.

    Needs a microphone and the speech extras (``pip install 'OpenJarvis[speech]'``).
    For a dedicated wake-word model install ``pip install 'OpenJarvis[wakeword]'``.
    If Home Assistant is configured (see the Smart Home guide) the smart-home tool
    is enabled automatically. Say "Jarvis, goodbye" or press Ctrl-C to stop.
    """
    from openjarvis.cli._voice_chat import VoiceSession, speak
    from openjarvis.sdk import Jarvis
    from openjarvis.speech.voice_io import record_until_silence

    use_model = wake_engine == "model" or (
        wake_engine == "auto" and not wake_words and wake_model_available()
    )
    if use_model and wake_words:
        raise click.ClickException(
            "--wake-word needs --wake-engine stt; the model only knows 'Hey Jarvis'."
        )
    if use_model and not wake_model_available():
        raise click.ClickException(
            "openWakeWord is not installed. "
            "Install with: pip install 'OpenJarvis[wakeword]'"
        )
    console = Console()
    session = VoiceSession()
    stt = session.get_stt_backend()
    if stt is None:
        raise click.ClickException(
            "No speech-to-text backend available. "
            "Install with: pip install 'OpenJarvis[speech]'"
        )

    def listen() -> Optional[str]:
        audio = record_until_silence(silence_seconds=1.0, startup_silence_seconds=30)
        text = stt.transcribe(audio, format="wav").text.strip()
        return text or None

    waiter = make_wake_model_waiter(wake_threshold) if use_model else None

    from openjarvis.tools.home_assistant import HomeAssistantTool

    agent_name, tool_list = resolve_agent_and_tools(
        agent_name,
        [t.strip() for t in tools.split(",") if t.strip()] if tools else None,
        HomeAssistantTool().is_configured(),
    )
    words = tuple(DEFAULT_WAKE_WORDS) + tuple(_normalize(w) for w in wake_words)

    with Jarvis(model=model_name) as jarvis:
        history: list[tuple[str, str]] = []

        def answer(query: str) -> str:
            reply = jarvis.ask(
                build_query(query, history), agent=agent_name, tools=tool_list
            )
            history.append((query, reply))
            del history[:-_HISTORY_TURNS]
            return reply

        def say(text: str) -> None:
            console.print(f"[bold cyan]Jarvis:[/bold cyan] {text}")
            if not no_speak:
                speak(text, console, session)

        loop = AssistantLoop(
            listen=listen,
            answer=answer,
            speak=say,
            wake_words=words,
            wait_for_wake=waiter,
            log=lambda m: console.print(f"[dim]{m}[/dim]"),
        )
        mode = "wake-word model" if use_model else "speech recognition"
        console.print(
            f'[green]Jarvis online[/green] ({mode}). Say "Hey Jarvis" (Ctrl-C to quit)'
        )
        try:
            loop.run()
        except KeyboardInterrupt:
            console.print("\n[dim]Offline.[/dim]")


__all__ = [
    "AssistantLoop",
    "assistant",
    "build_query",
    "is_exit",
    "resolve_agent_and_tools",
    "strip_wake_word",
    "wait_for_wake_word",
]
