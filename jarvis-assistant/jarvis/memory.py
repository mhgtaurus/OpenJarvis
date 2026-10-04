"""Dauerhaftes Gedächtnis: einfache Fakten in einer JSON-Datei."""

from __future__ import annotations

import json
from pathlib import Path


class Memory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._facts: dict[str, str] = {}
        if self.path.exists():
            try:
                self._facts = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._facts = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._facts, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def remember(self, key: str, value: str) -> None:
        self._facts[key.strip()] = value.strip()
        self._save()

    def forget(self, key: str) -> bool:
        removed = self._facts.pop(key.strip(), None) is not None
        if removed:
            self._save()
        return removed

    def recall(self, query: str = "") -> dict[str, str]:
        q = query.strip().lower()
        if not q:
            return dict(self._facts)
        return {
            k: v for k, v in self._facts.items() if q in k.lower() or q in v.lower()
        }

    def as_prompt(self) -> str:
        if not self._facts:
            return ""
        lines = "\n".join(f"- {k}: {v}" for k, v in self._facts.items())
        return f"Bekannte Fakten über den Nutzer:\n{lines}"
