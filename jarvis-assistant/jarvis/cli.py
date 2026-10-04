"""Kommandozeile: interaktiver Chat mit Jarvis."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .agent import Agent
from .memory import Memory
from .tools import Toolbox

HELP = "Befehle: /reset (Verlauf löschen), /memory (Fakten zeigen), /exit"


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Bitte ANTHROPIC_API_KEY setzen.", file=sys.stderr)
        return 1
    home = Path(os.environ.get("JARVIS_HOME", Path.home() / ".jarvis-assistant"))
    memory = Memory(home / "memory.json")
    agent = Agent(Toolbox(memory, home / "notes"), memory)
    print(f"Jarvis bereit (Modell: {agent.model}). {HELP}")
    while True:
        try:
            text = input("Du > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text in ("/exit", "/quit"):
            return 0
        if text == "/reset":
            agent.reset()
            print("Verlauf gelöscht.")
        elif text == "/memory":
            print(agent.toolbox.run("recall", {})[0])
        else:
            try:
                print(f"Jarvis > {agent.chat(text)}")
            except Exception as exc:
                print(f"Fehler: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
