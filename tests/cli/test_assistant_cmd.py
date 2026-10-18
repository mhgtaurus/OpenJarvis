from openjarvis.cli.assistant_cmd import (
    AssistantLoop,
    build_query,
    is_exit,
    strip_wake_word,
)

WAKE = ("jarvis",)


def test_strip_wake_word():
    assert strip_wake_word("Hey Jarvis, what time is it?", WAKE) == "what time is it"
    assert strip_wake_word("Jarvis", WAKE) == ""
    assert strip_wake_word("turn on the lights Jarvis", WAKE) == "turn on the lights"
    assert strip_wake_word("what a nice day", WAKE) is None
    assert (
        strip_wake_word("Yesterday I watched a movie where jarvis was the butler", WAKE)
        is None
    )


def test_is_exit():
    assert is_exit("goodbye")
    assert not is_exit("what is the weather")


def _loop(utterances, replies=None):
    heard = iter(utterances)
    spoken, asked = [], []

    def answer(q):
        asked.append(q)
        return f"re:{q}"

    loop = AssistantLoop(
        listen=lambda: next(heard, None), answer=answer, speak=spoken.append
    )
    return loop, spoken, asked


def test_command_in_one_utterance():
    loop, spoken, asked = _loop(["Jarvis what is two plus two"])
    assert loop.step()
    assert asked == ["what is two plus two"]
    assert spoken == ["re:what is two plus two"]


def test_ignores_unaddressed_speech():
    loop, spoken, asked = _loop(["random chatter"])
    assert loop.step()
    assert asked == [] and spoken == []


def test_wake_then_followup():
    loop, spoken, asked = _loop(["Jarvis", "open the report"])
    assert loop.step()
    assert spoken == ["Yes?", "re:open the report"]


def test_exit():
    loop, spoken, _ = _loop(["Jarvis goodbye"])
    assert not loop.step()
    assert spoken == [loop.farewell]


def test_build_query_includes_history():
    assert build_query("and tomorrow?", []) == "and tomorrow?"
    q = build_query("and tomorrow?", [("weather today", "sunny")])
    assert "User: weather today" in q and "Jarvis: sunny" in q
    assert q.endswith("User: and tomorrow?")
