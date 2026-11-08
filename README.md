# Inari Connector

A proximity voice chat plugin for [Endstone](https://github.com/EndstoneMC/endstone) (Minecraft Bedrock servers), powered by [Inari](https://inari.thedrewen.com/).

The plugin connects your server to an Inari instance over WebSocket, lets players pair their account with a pairing code or QR code, and gives players and staff in-game commands to manage voice (mute, deafen, ban).


---

## Table of contents

- [Commands](#commands)
  - [Player commands](#player-commands)
  - [Staff commands](#staff-commands)
  - [Other commands](#other-commands)
- [Permissions](#permissions)
- [Plugin configuration](#plugin-configuration)
  - [config.toml](#configtoml)
- [Installation](#installation)
  - [Plugin installation](#plugin-installation)
  - [Resource pack installation](#resource-pack-installation)
  - [Inari installation](#inari-installation)
- [Updating](#updating)
- [PlaceholderAPI extension](#placeholderapi-extension)
- [Upcoming updates](#upcoming-updates)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Commands

The main command is `/inari`. It also works with the aliases `/vocal` and `/voice`.

### Player commands

| Command | Description |
| --- | --- |
| `/inari info` | Shows your voice profile: mute, deafen and ban status, plus your live voice state. |
| `/inari gui` | Opens the Inari GUI with buttons to connect, mute and deafen. |
| `/inari pair` | Opens a form with a QR code, the connection link, your pairing code and the channel name. **Do not share this information.** |
| `/inari mute` | Requests a self-mute / unmute (toggle). |
| `/inari deafen` | Requests a self-deafen / undeafen (toggle). |

### Staff commands

Staff commands are restricted to operators by default.

| Command | Description |
| --- | --- |
| `/inari staff info <target>` | Shows the voice status of a player (mute, deafen, ban, live state). |
| `/inari staff spy <target>` | Listens to what a player says and hears. You are muted and moved to the target's position while spying. Run it on yourself to stop. The target must be online, and the spy ends automatically if the target leaves the server. |
| `/inari staff mute <target>` | Force-mutes a player. Run it again to lift the mute. |
| `/inari staff deafen <target>` | Force-deafens a player. Run it again to lift the deafen. |
| `/inari staff ban <target>` | Bans a player from the voice chat. Run it again to unban. |
| `/inari staff tempmute <target> <duration>` | Force-mutes a player for a limited time. |
| `/inari staff tempdeafen <target> <duration>` | Force-deafens a player for a limited time. |
| `/inari staff tempban <target> <duration>` | Bans a player from the voice chat for a limited time. |

**Duration format:** a number followed by a unit: `s` (seconds), `m` (minutes), `h` (hours) or `d` (days). Examples: `30s`, `10m`, `2h`, `1d`.

> A player must have joined the server at least once to be targeted by a staff command.

### Other commands

| Command | Description |
| --- | --- |
| `/test` | Simple command to check that the plugin is loaded. Operators only. |

---

## Permissions

| Permission | Default | Description |
| --- | --- | --- |
| `inari.command.inari` | everyone | Use the `/inari` command. |
| `inari.command.public.info` | everyone | Use `/inari info`. |
| `inari.command.public.gui` | everyone | Use `/inari gui`. |
| `inari.command.public.pair` | everyone | Use `/inari pair`. |
| `inari.command.public.mute` | everyone | Use `/inari mute`. |
| `inari.command.public.deafen` | everyone | Use `/inari deafen`. |
| `inari.command.staff` | op | Use `/inari staff`. |
| `inari.command.staff.spy` | op | Use `/inari staff spy`. |
| `inari.command.staff.mute` | op | Use `/inari staff mute`. |
| `inari.command.staff.deafen` | op | Use `/inari staff deafen`. |
| `inari.command.staff.ban` | op | Use `/inari staff ban`. |
| `inari.command.staff.tempmute` | op | Use `/inari staff tempmute`. |
| `inari.command.staff.tempdeafen` | op | Use `/inari staff tempdeafen`. |
| `inari.command.staff.tempban` | op | Use `/inari staff tempban`. |
| `inari.command.test` | op | Use `/test`. |

---

## Plugin configuration

### config.toml

The configuration file is located in the plugin's data folder (`plugins/inari/config.toml`).

```toml
# true : logs all raw messages sent/received in plugins/Inari/debug.txt
# Warning: the file contains the API key (authentication message).
debug = false

[connection]
url = "wss://inari.yourserver.com/ws"
api_key = ""
channel = "default"

[clients]
code_length = 8
connect_url = "https://inari.yourserver.com/"
```

| Section | Key | Default | Description |
| --- | --- | --- | --- |
| *(root)* | `debug` | `false` | Writes every raw WebSocket message to `debug.txt` in the plugin folder. **The file contains your API key**, never share it. |
| `[connection]` | `url` | `wss://inari.yourserver.com/ws` | WebSocket URL of your Inari instance. **Required.** |
| `[connection]` | `api_key` | `""` | API key used to authenticate the server on Inari. **Required.** |
| `[connection]` | `channel` | `"default"` | Voice channel used by this server. |
| `[clients]` | `code_length` | `8` | Length of the pairing code generated for each player. Minimum is `6` (smaller values are raised to 6). |
| `[clients]` | `connect_url` | `https://inari.yourserver.com/` | Web page where players enter their pairing code. Also used to build the QR code link. |

---

## Installation

### Plugin installation

**Requirements**

- An [Endstone](https://github.com/EndstoneMC/endstone) server (API version `0.11`)
- Python `>= 3.10`
- A running Inari instance (see [Inari installation](#inari-installation))
- *Optional:* a PlaceholderAPI plugin for Endstone, to use the plugin's placeholder (see [PlaceholderAPI extension](#placeholderapi-extension))

**Steps**

1. Download the latest `endstone_inari-<version>-py3-none-any.whl` from [Releases](https://github.com/CircuitCrafter2/Endstone-Proximity-Voice-Chat--InariConnector/releases).
2. Drop the `.whl` file into the `plugins/` folder of your Endstone server.
3. Restart the server.
4. The plugin generates its `config.toml` on first start. Fill it in (see [Plugin configuration](#plugin-configuration)) and restart the server again.

> The plugin will not start the voice connector until both `url` and `api_key` are set in `config.toml`. A message is logged in the console if one of them is missing.

### Resource pack installation

> [!IMPORTANT]
> The resource pack is **required** for the plugin's forms to display correctly (for example the QR code shown by `/inari pair` and the centered text of the pairing form). It also contains the voice status glyphs used by the [PlaceholderAPI extension](#placeholderapi-extension). Without it, those forms and glyphs will not render as intended.

**Steps**

1. Get the resource pack: `InariRessourcePack` (or the ready-to-use `InariConnectorPack.mcpack` file).
2. Copy the `InariRessourcePack` folder into the `resource_packs/` folder of your server.
3. Enable it for your world by adding it to your world's `world_resource_packs.json` (in `worlds/<your world>/`):

   ```json
   [
     {
       "pack_id": "e2eb5209-8e47-44dc-b68e-f9b020d4fffb",
       "version": [1, 1, 0]
     }
   ]
   ```

   The `version` must match the `version` of the pack's `manifest.json`.

4. Force players to download it by adding the following line to your `server.properties`:

   ```properties
   texturepack-required=true
   ```

   This makes the server require the resource pack, so every player gets the correct forms.

5. Restart the server.

### Inari installation

Inari itself (the voice server the plugin connects to) has its own installation guide:

👉 **https://inari.thedrewen.com/guides/installation/**

Once Inari is installed, you will need its WebSocket URL and an API key to fill in the plugin's `config.toml`.

---

## Updating

At startup, the plugin checks the latest GitHub release and logs a warning in the console, with the download link, when a newer version is available. Only stable releases are reported (pre-releases are not).

**Steps**

1. **Back up** the `plugins/inari/` folder (it contains your `config.toml` and the players' data).
2. **Stop the server.**
3. Download the new `endstone_inari-<version>-py3-none-any.whl` from [Releases](https://github.com/CircuitCrafter2/Endstone-Proximity-Voice-Chat--InariConnector/releases).
4. In `plugins/`, **delete the old `.whl`** and put the new one in its place. Never keep two versions of the plugin at the same time.
5. **Start the server.**

**What is kept**

- Your `config.toml` is **not** overwritten. If the release notes mention a new option, add it manually (compare with [config.toml](#configtoml)); a missing option falls back to its default value.
- Players' data is kept. Missing fields are added automatically when a player joins.

**If the resource pack changed**

When a release comes with a new version of the resource pack:

1. Replace the `InariRessourcePack` folder in `resource_packs/` (or use the new `.mcpack`).
2. Update the `version` in `world_resource_packs.json` so it matches the `version` of the new `manifest.json`.
3. Restart the server. Players will download the new version when they join.

---

## PlaceholderAPI extension

Inari Connector provides an optional expansion for PlaceholderAPI. It lets other plugins display a player's voice status as in-game glyphs.

The expansion is registered automatically at startup when PlaceholderAPI is installed and active. Otherwise the plugin works normally, and a message in the console tells you that placeholders are disabled.

**Requirements**

- A PlaceholderAPI plugin for Endstone installed on the server.
- The [resource pack](#resource-pack-installation), which contains the glyphs.

### Placeholders

| Placeholder | Description |
| --- | --- |
| `{inari:global_status}` | The voice status of the player, as one or two glyphs. |

### Status shown

The status is chosen in this order, the first match wins:

1. **Banned** from the voice chat.
2. **Not connected** to Inari.
3. **Spying** on another player.
4. Otherwise, **two glyphs side by side**: the mute icon followed by the deafen icon. Each one can be *off*, *on* (chosen by the player) or *forced* (by staff). A forced state takes priority over the player's own choice.

| State | Glyph |
| --- | --- |
| Not connected | `U+E921` |
| Banned | `U+E922` |
| Spying | `U+E921` (same glyph as *not connected*) |
| Mute: off / on / forced | `U+E900` / `U+E901` / `U+E902` |
| Deafen: off / on / forced | `U+E910` / `U+E911` / `U+E912` |

> A banned player is shown as banned even when not connected. A player is shown as *not connected* about 15 seconds after leaving Inari.

### Customizing the glyphs

The glyphs are stored in `font/glyph_E9.png` of the resource pack (a 16×16 grid covering `U+E900` to `U+E9FF`). Edit that image to change how they look, then increase the pack version and follow the [resource pack update steps](#updating).

---

## Upcoming updates

| Feature | Description | Status |
| --- | --- | --- |
| Statistical | Add a statistics system | :white_check_mark: Finish |
| Update | Add a system that warns if the plugin is no longer up to date. | :white_check_mark: Finish |
| Spy | Add a system that allows staff to eavesdrop on conversations without being nearby | :white_check_mark: Finish |
| API | Add an API for developers | :calendar: Planned |
| Logos | Add in-game logos to display voice status | :test_tube: In the latest Release Candidate |

---

## Acknowledgements

Thanks to `! zelišče` for his explanation on QR codes with JSON UI and to [`TheDreWen`](https://github.com/thedrewen) for his help in general.

---

## License

This project is licensed under the [MIT License](LICENSE).