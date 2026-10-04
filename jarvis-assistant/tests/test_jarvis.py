from types import SimpleNamespace as NS

import pytest

from jarvis import Agent, Memory
from jarvis.tools import Toolbox, safe_eval


def make(tmp_path):
    mem = Memory(tmp_path / "mem.json")
    return mem, Toolbox(mem, tmp_path / "notes")


def test_safe_eval():
    assert safe_eval("2 + 3 * 4") == 14
    assert safe_eval("-(2 ** 3)") == -8
    for bad in ["__import__('os')", "1 + a", "2 ** 99999"]:
        with pytest.raises(Exception):
            safe_eval(bad)


def test_memory_persists(tmp_path):
    Memory(tmp_path / "m.json").remember("Name", "Max")
    assert Memory(tmp_path / "m.json").recall("max") == {"Name": "Max"}


def test_notes_sandbox(tmp_path):
    _, tb = make(tmp_path)
    assert tb.run("write_note", {"name": "a.txt", "content": "hi"})[1] is False
    assert tb.run("read_note", {"name": "a.txt"})[0] == "hi"
    out, err = tb.run("read_note", {"name": "../mem.json"})
    assert err and "außerhalb" in out
    assert tb.run("nope", {})[1] is True


class FakeClient:
    """Erst ein Werkzeugaufruf, dann die Endantwort."""

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        if self.calls == 1:
            block = NS(type="tool_use", id="t1", name="calculate",
                       input={"expression": "6*7"})
            return NS(stop_reason="tool_use", content=[block])
        return NS(stop_reason="end_turn", content=[NS(type="text", text="42")])


def test_agent_tool_loop(tmp_path):
    mem, tb = make(tmp_path)
    agent = Agent(tb, mem, client=FakeClient())
    assert agent.chat("Was ist 6*7?") == "42"
    result = agent.messages[2]["content"][0]
    assert result["content"] == "42" and result["is_error"] is False
