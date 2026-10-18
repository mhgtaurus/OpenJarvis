# Smart Home

The `home_assistant` tool lets agents, and the [voice assistant](voice-assistant.md),
control your smart home through [Home Assistant](https://www.home-assistant.io/):
"Jarvis, dim the living room lights to 30 percent", "Jarvis, is the hallway
heating on?". Home Assistant already bridges most systems (Hue, Zigbee, Matter,
Sonos, KNX, and many more), so one integration covers them all.

## Setup

1. In Home Assistant open your profile, then **Security → Long-lived access
   tokens**, and create a token.
2. Point OpenJarvis at your instance:

   ```toml
   # ~/.openjarvis/config.toml
   [tools.home_assistant]
   url = "http://homeassistant.local:8123"
   ```

3. Provide the token. Keep it out of `config.toml`:

   ```bash
   export HOME_ASSISTANT_TOKEN="<your token>"
   ```

   You can also save it through the tool credentials API/UI.

4. Try it:

   ```bash
   jarvis ask -a orchestrator --tools home_assistant "Which lights are on?"
   jarvis assistant      # enables the tool automatically once configured
   ```

## Actions

| Action | Parameters | What it does |
|---|---|---|
| `list` | `domain` (optional) | Lists entity ids, names and states, e.g. `light.living_room \| Living Room \| off` (first 100) |
| `get` | `entity_id` | Reads one state and its attributes |
| `call` | `service`, `entity_id`, `domain` (optional, inferred from the entity), `data` (optional) | Calls a Home Assistant service, e.g. `light.turn_on` with `{"brightness_pct": 30}` or `climate.set_temperature` with `{"temperature": 21}` |

The agent normally lists entities first, so it can find the right id for
"the living room lights" by itself.

## Safety

- **Sensitive domains are blocked by default**: `lock`, `alarm_control_panel`,
  `camera`, `shell_command`, `python_script`, `rest_command`, `homeassistant`
  and `hassio`. A voice command that is misheard or injected through a web page
  an agent reads should not be able to unlock your door. These entities are also
  hidden from `list`. To allow them deliberately:

  ```toml
  [tools.home_assistant]
  allow_sensitive = true
  ```

- The service target must be passed as `entity_id`; it cannot be smuggled in
  through `data`, so one call always acts on one named entity (or none).
- Domain, service and entity names are validated, and the token is never
  echoed in results or errors.
- The tool talks to your Home Assistant URL only. Its URL is trusted
  configuration, so private network addresses are allowed (unlike the generic
  `http_request` tool).
- Use `http://` only on a trusted home network; prefer HTTPS when the instance
  is reachable from outside.
