"""Smart-home control tool backed by a Home Assistant instance (REST API)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from openjarvis.core.credentials import get_tool_credential
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_TOOL_NAME = "home_assistant"
_TOKEN_ENV = "HOME_ASSISTANT_TOKEN"
_ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_MAX_LISTED = 100

# Domains that can open doors, disarm alarms, watch cameras or run arbitrary
# commands. Blocked unless ``[tools.home_assistant] allow_sensitive = true``.
SENSITIVE_DOMAINS = frozenset(
    {
        "lock",
        "alarm_control_panel",
        "camera",
        "shell_command",
        "homeassistant",
        "hassio",
        "python_script",
        "rest_command",
    }
)


@ToolRegistry.register("home_assistant")
class HomeAssistantTool(BaseTool):
    """List, read and control smart-home devices through Home Assistant."""

    tool_id = _TOOL_NAME
    is_local = True  # Home Assistant normally runs on the local network

    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        allow_sensitive: bool | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        cfg: Any = None
        try:
            from openjarvis.core.config import load_config

            cfg = load_config().tools.home_assistant
        except Exception:
            cfg = None
        self._url = (url or getattr(cfg, "url", "") or "").strip().rstrip("/")
        self._token = (token or "").strip() or None
        self._allow_sensitive = (
            allow_sensitive
            if allow_sensitive is not None
            else bool(getattr(cfg, "allow_sensitive", False))
        )
        self._client = client

    def _resolve_token(self) -> str | None:
        if self._token:
            return self._token
        try:
            value = get_tool_credential(_TOOL_NAME, _TOKEN_ENV)
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return value.strip() if isinstance(value, str) and value.strip() else None

    def is_configured(self) -> bool:
        return bool(self._url and self._resolve_token())

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=_TOOL_NAME,
            description=(
                "Control smart-home devices (lights, switches, climate, covers, "
                "media players, scenes, scripts) via Home Assistant. Use "
                "action='list' to find entity ids, 'get' to read a state, and "
                "'call' to run a service such as light.turn_on or "
                "climate.set_temperature."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "call"],
                        "description": (
                            "list entities, read one state, or call a service."
                        ),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "list: only this domain (e.g. 'light'). "
                            "call: service domain (e.g. 'light')."
                        ),
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Entity id such as 'light.living_room'.",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service name for 'call', e.g. 'turn_on'.",
                    },
                    "data": {
                        "type": "object",
                        "description": (
                            "Extra service data, e.g. {'brightness_pct': 40} "
                            "or {'temperature': 21}."
                        ),
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            category="smart_home",
            latency_estimate=0.5,
            timeout_seconds=15.0,
            required_capabilities=["network:fetch"],
            metadata={"requires_api_key": _TOKEN_ENV},
        )

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _fail(message: str) -> ToolResult:
        return ToolResult(tool_name=_TOOL_NAME, content=message, success=False)

    @staticmethod
    def _ok(message: str) -> ToolResult:
        return ToolResult(tool_name=_TOOL_NAME, content=message, success=True)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._resolve_token()}"}
        url = f"{self._url}{path}"
        if self._client is not None:
            return self._client.request(method, url, headers=headers, **kwargs)
        with httpx.Client(timeout=10.0) as client:
            return client.request(method, url, headers=headers, **kwargs)

    def _blocked(self, domain: str) -> bool:
        return domain in SENSITIVE_DOMAINS and not self._allow_sensitive

    # -- actions ----------------------------------------------------------

    def _list(self, domain: str) -> ToolResult:
        if domain and not _NAME_RE.fullmatch(domain):
            return self._fail("Invalid domain.")
        response = self._request("GET", "/api/states")
        response.raise_for_status()
        rows = []
        for state in response.json():
            entity_id = str(state.get("entity_id", ""))
            entity_domain = entity_id.split(".", 1)[0]
            if (domain and entity_domain != domain) or self._blocked(entity_domain):
                continue
            name = (state.get("attributes") or {}).get("friendly_name", "")
            rows.append(f"{entity_id} | {name} | {state.get('state')}")
        if not rows:
            return self._ok("No matching entities.")
        shown = rows[:_MAX_LISTED]
        extra = len(rows) - len(shown)
        suffix = f"\n... and {extra} more; narrow with 'domain'." if extra else ""
        return self._ok("\n".join(shown) + suffix)

    def _get(self, entity_id: str) -> ToolResult:
        if not _ENTITY_RE.fullmatch(entity_id):
            return self._fail("A valid entity_id like 'light.kitchen' is required.")
        if self._blocked(entity_id.split(".", 1)[0]):
            return self._fail(self._sensitive_message(entity_id.split(".", 1)[0]))
        response = self._request("GET", f"/api/states/{entity_id}")
        if response.status_code == 404:
            return self._fail(f"Unknown entity '{entity_id}'. Use action='list'.")
        response.raise_for_status()
        state = response.json()
        attrs = state.get("attributes") or {}
        details = ", ".join(f"{k}={v}" for k, v in sorted(attrs.items())[:15])
        return self._ok(f"{entity_id} is {state.get('state')}. {details}".strip())

    def _call(self, domain: str, service: str, entity_id: str, data: Any) -> ToolResult:
        if not (_NAME_RE.fullmatch(domain) and _NAME_RE.fullmatch(service)):
            return self._fail(
                "'domain' and 'service' are required, e.g. light/turn_on."
            )
        if self._blocked(domain):
            return self._fail(self._sensitive_message(domain))
        body: dict[str, Any] = {}
        if data:
            if not isinstance(data, dict):
                return self._fail("'data' must be an object.")
            body.update(data)
        if entity_id:
            if not _ENTITY_RE.fullmatch(entity_id):
                return self._fail("Invalid entity_id.")
            if self._blocked(entity_id.split(".", 1)[0]):
                return self._fail(self._sensitive_message(entity_id.split(".", 1)[0]))
            body["entity_id"] = entity_id
        elif "entity_id" in body or "area_id" in body or "device_id" in body:
            return self._fail("Pass the target as 'entity_id', not inside 'data'.")
        response = self._request("POST", f"/api/services/{domain}/{service}", json=body)
        if response.status_code == 404:
            return self._fail(f"Unknown service '{domain}.{service}'.")
        response.raise_for_status()
        target = entity_id or domain
        return self._ok(f"Done: {domain}.{service} on {target}.")

    @staticmethod
    def _sensitive_message(domain: str) -> str:
        return (
            f"The '{domain}' domain is blocked for safety. Set "
            "[tools.home_assistant] allow_sensitive = true to permit it."
        )

    def execute(self, **params: Any) -> ToolResult:
        if not self._url:
            return self._fail(
                "Home Assistant URL not configured. Set [tools.home_assistant] url."
            )
        if not self._resolve_token():
            return self._fail(
                f"No Home Assistant token. Set {_TOKEN_ENV} or save it in the "
                "tool credentials."
            )
        action = str(params.get("action", "")).strip()
        domain = str(params.get("domain") or "").strip().lower()
        entity_id = str(params.get("entity_id") or "").strip().lower()
        try:
            if action == "list":
                return self._list(domain)
            if action == "get":
                return self._get(entity_id)
            if action == "call":
                if not domain and entity_id:
                    domain = entity_id.split(".", 1)[0]
                service = str(params.get("service") or "").strip().lower()
                return self._call(domain, service, entity_id, params.get("data"))
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = " (check the token)" if code in (401, 403) else ""
            return self._fail(f"Home Assistant returned HTTP {code}{hint}.")
        except httpx.HTTPError as exc:
            return self._fail(f"Could not reach Home Assistant: {type(exc).__name__}.")
        return self._fail("action must be 'list', 'get' or 'call'.")


__all__ = ["HomeAssistantTool", "SENSITIVE_DOMAINS"]
