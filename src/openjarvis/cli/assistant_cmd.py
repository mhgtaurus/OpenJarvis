"""``jarvis assistant`` — hands-free "Hey Jarvis" voice assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import click
from rich.console import Console

DEFAULT_WAKE_WORDS = ("jarvis", "dschawis", "jarvies")
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

    def step(self) -> bool:
        """Handle one utterance. Returns False when the assistant should exit."""
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
@click.option("--no-speak", is_flag=True, help="Print replies instead of speaking.")
def assistant(
    model_name: str | None,
    agent_name: str | None,
    tools: str | None,
    wake_words: tuple[str, ...],
    no_speak: bool,
) -> None:
    """Run Jarvis hands-free: say "Jarvis, <request>" and hear the answer.

    Needs a microphone and the speech extras (``pip install 'OpenJarvis[speech]'``).
    Say "Jarvis, goodbye" or press Ctrl-C to stop.
    """
    from openjarvis.cli._voice_chat import VoiceSession, speak
    from openjarvis.sdk import Jarvis
    from openjarvis.speech.voice_io import record_until_silence

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

    tool_list = [t.strip() for t in tools.split(",")] if tools else None
    words = tuple(DEFAULT_WAKE_WORDS) + tuple(_normalize(w) for w in wake_words)

    with Jarvis(model=model_name) as jarvis:

        def answer(query: str) -> str:
            return jarvis.ask(query, agent=agent_name, tools=tool_list)

        def say(text: str) -> None:
            console.print(f"[bold cyan]Jarvis:[/bold cyan] {text}")
            if not no_speak:
                speak(text, console, session)

        loop = AssistantLoop(
            listen=listen,
            answer=answer,
            speak=say,
            wake_words=words,
            log=lambda m: console.print(f"[dim]{m}[/dim]"),
        )
        console.print('[green]Jarvis online.[/green] Say "Jarvis ..." (Ctrl-C to quit)')
        try:
            loop.run()
        except KeyboardInterrupt:
            console.print("\n[dim]Offline.[/dim]")


__all__ = ["AssistantLoop", "assistant", "is_exit", "strip_wake_word"]
