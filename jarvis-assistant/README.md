# Jarvis Assistant

Ein eigenständiger, kleiner KI-Assistent (unabhängig vom restlichen OpenJarvis-Code).

- **Agent-Schleife** über die Claude-API mit Tool-Use (`jarvis/agent.py`)
- **Werkzeuge**: Uhrzeit, sicherer Taschenrechner, Gedächtnis, Notizen im Arbeitsordner (`jarvis/tools.py`)
- **Gedächtnis**: dauerhafte Fakten in `~/.jarvis-assistant/memory.json`, werden in den System-Prompt eingeblendet

## Start

```bash
pip install -e .
export ANTHROPIC_API_KEY=...
jarvis-assistant        # oder: python -m jarvis.cli
```

Optional: `JARVIS_MODEL` (Standard `claude-sonnet-5-5`), `JARVIS_HOME` (Datenordner).
Befehle im Chat: `/reset`, `/memory`, `/exit`.

## Tests

```bash
pip install -e ".[dev]" && pytest
```
