"""Tests for the Home Assistant smart-home tool (HTTP mocked)."""

from __future__ import annotations

import json

import httpx

from openjarvis.tools.home_assistant import HomeAssistantTool

STATES = [
    {
        "entity_id": "light.living_room",
        "state": "off",
        "attributes": {"friendly_name": "Living Room"},
    },
    {
        "entity_id": "lock.front_door",
        "state": "locked",
        "attributes": {"friendly_name": "Front Door"},
    },
    {
        "entity_id": "climate.hall",
        "state": "heat",
        "attributes": {"friendly_name": "Hall", "temperature": 21},
    },
]


def _tool(
    allow_sensitive: bool = False, token: str | None = "s3cr3t-value", url="http://ha"
):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/api/states":
            return httpx.Response(200, json=STATES)
        if path.startswith("/api/states/"):
            entity = path.rsplit("/", 1)[1]
            for state in STATES:
                if state["entity_id"] == entity:
                    return httpx.Response(200, json=state)
            return httpx.Response(404)
        if path == "/api/services/light/turn_on":
            return httpx.Response(200, json=[])
        if path == "/api/services/lock/unlock":
            return httpx.Response(200, json=[])
        if path == "/api/services/light/boom":
            return httpx.Response(401)
        return httpx.Response(404)

    tool = HomeAssistantTool(
        url=url,
        token=token,
        allow_sensitive=allow_sensitive,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return tool, calls


def test_not_configured():
    assert not HomeAssistantTool(url="", token="x").execute(action="list").success
    tool = HomeAssistantTool(url="http://ha", token="")
    tool._resolve_token = lambda: None  # no env/credentials in this test
    assert "token" in tool.execute(action="list").content.lower()


def test_list_hides_sensitive_domains():
    tool, calls = _tool()
    result = tool.execute(action="list")
    assert result.success
    assert "light.living_room | Living Room | off" in result.content
    assert "lock.front_door" not in result.content
    assert calls[0].headers["Authorization"] == "Bearer s3cr3t-value"


def test_list_filters_by_domain():
    tool, _ = _tool()
    content = tool.execute(action="list", domain="climate").content
    assert "climate.hall" in content and "light." not in content


def test_get_state_and_unknown_entity():
    tool, _ = _tool()
    assert (
        "climate.hall is heat"
        in tool.execute(action="get", entity_id="climate.hall").content
    )
    assert not tool.execute(action="get", entity_id="light.nope").success


def test_call_service_sends_entity_and_data():
    tool, calls = _tool()
    result = tool.execute(
        action="call",
        domain="light",
        service="turn_on",
        entity_id="light.living_room",
        data={"brightness_pct": 40},
    )
    assert result.success
    body = json.loads(calls[-1].content)
    assert body == {"brightness_pct": 40, "entity_id": "light.living_room"}


def test_call_infers_domain_from_entity():
    tool, calls = _tool()
    tool.execute(action="call", service="turn_on", entity_id="light.living_room")
    assert calls[-1].url.path == "/api/services/light/turn_on"


def test_sensitive_domains_blocked_by_default():
    tool, calls = _tool()
    result = tool.execute(
        action="call", domain="lock", service="unlock", entity_id="lock.front_door"
    )
    assert not result.success and "allow_sensitive" in result.content
    assert not tool.execute(action="get", entity_id="lock.front_door").success
    assert calls == []  # never reached the server


def test_sensitive_domains_allowed_when_enabled():
    tool, _ = _tool(allow_sensitive=True)
    assert tool.execute(
        action="call", domain="lock", service="unlock", entity_id="lock.front_door"
    ).success


def test_target_cannot_be_smuggled_through_data():
    tool, calls = _tool()
    result = tool.execute(
        action="call",
        domain="light",
        service="turn_on",
        data={"entity_id": "lock.front_door"},
    )
    assert not result.success and calls == []


def test_rejects_malformed_names_and_actions():
    tool, calls = _tool()
    assert not tool.execute(action="call", domain="../x", service="y").success
    assert not tool.execute(action="get", entity_id="light/../x").success
    assert not tool.execute(action="reboot").success
    assert calls == []


def test_http_errors_are_reported_without_the_token():
    tool, _ = _tool()
    result = tool.execute(action="call", domain="light", service="boom")
    assert not result.success and "401" in result.content
    assert "s3cr3t-value" not in result.content
