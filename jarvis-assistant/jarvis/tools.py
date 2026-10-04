"""Werkzeuge, die Jarvis aufrufen kann."""

from __future__ import annotations

import ast
import operator
from datetime import datetime
from pathlib import Path
from typing import Callable

from .memory import Memory

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expression: str) -> float:
    """Wertet reine Rechenausdrücke aus, ohne eval()."""

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent zu groß")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.operand))
        raise ValueError("Nur Zahlen und + - * / // % ** sind erlaubt")

    return walk(ast.parse(expression, mode="eval"))


class Toolbox:
    """Bündelt Werkzeuge samt Schemas. Dateizugriff ist auf `workspace` beschränkt."""

    def __init__(self, memory: Memory, workspace: Path):
        self.memory = memory
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._handlers: dict[str, Callable[..., str]] = {
            "get_time": self._get_time,
            "calculate": self._calculate,
            "remember": self._remember,
            "recall": self._recall,
            "forget": self._forget,
            "list_notes": self._list_notes,
            "read_note": self._read_note,
            "write_note": self._write_note,
        }

    def _path(self, name: str) -> Path:
        p = (self.workspace / name).resolve()
        if p != self.workspace and self.workspace not in p.parents:
            raise ValueError("Zugriff außerhalb des Arbeitsordners nicht erlaubt")
        return p

    def _get_time(self) -> str:
        return datetime.now().astimezone().strftime("%A, %d.%m.%Y %H:%M:%S %Z")

    def _calculate(self, expression: str) -> str:
        return str(safe_eval(expression))

    def _remember(self, key: str, value: str) -> str:
        self.memory.remember(key, value)
        return f"Gemerkt: {key} = {value}"

    def _recall(self, query: str = "") -> str:
        found = self.memory.recall(query)
        if not found:
            return "Nichts gefunden."
        return "\n".join(f"{k}: {v}" for k, v in found.items())

    def _forget(self, key: str) -> str:
        return "Vergessen." if self.memory.forget(key) else "Nicht vorhanden."

    def _list_notes(self) -> str:
        files = sorted(p.name for p in self.workspace.iterdir() if p.is_file())
        return "\n".join(files) or "Keine Notizen."

    def _read_note(self, name: str) -> str:
        return self._path(name).read_text(encoding="utf-8")

    def _write_note(self, name: str, content: str) -> str:
        self._path(name).write_text(content, encoding="utf-8")
        return f"Notiz '{name}' gespeichert."

    def run(self, name: str, args: dict) -> tuple[str, bool]:
        """Führt ein Werkzeug aus. Gibt (Ergebnis, ist_fehler) zurück."""
        handler = self._handlers.get(name)
        if handler is None:
            return f"Unbekanntes Werkzeug: {name}", True
        try:
            return handler(**args), False
        except Exception as exc:  # Fehler gehen als Ergebnis zurück ans Modell
            return f"Fehler: {exc}", True

    @property
    def schemas(self) -> list[dict]:
        def tool(name: str, description: str, props: dict | None = None,
                 required: list[str] | None = None) -> dict:
            return {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": props or {},
                    "required": required or [],
                },
            }

        s = {"type": "string"}
        return [
            tool("get_time", "Aktuelles Datum und Uhrzeit."),
            tool("calculate", "Berechnet einen mathematischen Ausdruck.",
                 {"expression": s}, ["expression"]),
            tool("remember", "Merkt sich dauerhaft einen Fakt über den Nutzer.",
                 {"key": s, "value": s}, ["key", "value"]),
            tool("recall", "Sucht gemerkte Fakten (leer = alle).", {"query": s}),
            tool("forget", "Löscht einen gemerkten Fakt.", {"key": s}, ["key"]),
            tool("list_notes", "Listet alle Notizen im Arbeitsordner."),
            tool("read_note", "Liest eine Notiz.", {"name": s}, ["name"]),
            tool("write_note", "Schreibt oder überschreibt eine Notiz.",
                 {"name": s, "content": s}, ["name", "content"]),
        ]
