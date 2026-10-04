"""Der Agent: Gesprächsverlauf plus Werkzeugschleife über die Claude-API."""

from __future__ import annotations

import os
from typing import Any

from .memory import Memory
from .tools import Toolbox

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_STEPS = 10

SYSTEM_PROMPT = (
    "Du bist Jarvis, ein persönlicher KI-Assistent. Antworte in der Sprache des "
    "Nutzers (standardmäßig Deutsch), knapp, höflich und hilfreich. Nutze deine "
    "Werkzeuge, wenn sie helfen: Uhrzeit, Rechnen, Gedächtnis (remember/recall) "
    "und Notizen. Merke dir dauerhaft nützliche Fakten, wenn der Nutzer sie "
    "mitteilt. Erfinde nichts; sage, wenn du etwas nicht weißt."
)


class Agent:
    def __init__(self, toolbox: Toolbox, memory: Memory, client: Any = None,
                 model: str | None = None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.toolbox = toolbox
        self.memory = memory
        self.model = model or os.environ.get("JARVIS_MODEL", DEFAULT_MODEL)
        self.messages: list[dict] = []

    def _system(self) -> str:
        extra = self.memory.as_prompt()
        return f"{SYSTEM_PROMPT}\n\n{extra}" if extra else SYSTEM_PROMPT

    def reset(self) -> None:
        self.messages.clear()

    def chat(self, user_text: str) -> str:
        """Verarbeitet eine Nutzernachricht und gibt Jarvis' Antwort zurück."""
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_STEPS):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self._system(),
                tools=self.toolbox.schemas,
                messages=self.messages,
            )
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return "".join(
                    b.text for b in response.content if b.type == "text"
                ).strip()
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, is_error = self.toolbox.run(block.name, block.input)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    })
            self.messages.append({"role": "user", "content": results})
        return "Abbruch: zu viele Werkzeugschritte."
