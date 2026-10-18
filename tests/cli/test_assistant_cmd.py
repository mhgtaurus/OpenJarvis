from openjarvis.cli.assistant_cmd import (
    AssistantLoop,
    build_query,
    is_exit,
    resolve_agent_and_tools,
    strip_wake_word,
    wait_for_wake_word,
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


def test_wait_for_wake_word_triggers_at_threshold():
    scores = iter([0.1, 0.4, 0.7, 0.9])
    seen = []

    def predict(frame):
        seen.append(frame)
        return {"hey_jarvis": next(scores)}

    assert wait_for_wake_word(iter("abcd"), predict, 0.5)
    assert seen == ["a", "b", "c"]  # stops consuming audio once triggered


def test_wait_for_wake_word_runs_out_of_frames():
    assert not wait_for_wake_word(iter("ab"), lambda f: {"m": 0.0}, 0.5)


def test_model_gated_loop_greets_then_answers():
    heard = iter(["what is the capital of France"])
    spoken, asked, woke = [], [], []

    def answer(q):
        asked.append(q)
        return "Paris"

    loop = AssistantLoop(
        listen=lambda: next(heard, None),
        answer=answer,
        speak=spoken.append,
        wait_for_wake=lambda: woke.append(1),
    )
    assert loop.step()
    assert woke == [1]
    assert asked == ["what is the capital of France"]
    assert spoken == ["Yes?", "Paris"]


def test_model_gated_loop_ignores_silence_and_exits():
    heard = iter([None, "goodbye"])
    spoken = []
    loop = AssistantLoop(
        listen=lambda: next(heard, None),
        answer=lambda q: "x",
        speak=spoken.append,
        wait_for_wake=lambda: None,
    )
    assert loop.step()  # nothing said after the wake word
    assert not loop.step()
    assert spoken[-1] == loop.farewell


def test_resolve_agent_and_tools():
    assert resolve_agent_and_tools(None, None, False) == (None, None)
    assert resolve_agent_and_tools(None, None, True) == (
        "orchestrator",
        ["home_assistant"],
    )
    assert resolve_agent_and_tools("react", ["calculator"], True) == (
        "react",
        ["calculator", "home_assistant"],
    )
    assert resolve_agent_and_tools(None, ["home_assistant"], True)[1] == [
        "home_assistant"
    ]
