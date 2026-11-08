# Inari Connector

A proximity voice chat plugin for [Endstone](https://github.com/EndstoneMC/endstone) (Minecraft Bedrock servers), powered by [Inari](https://inari.thedrewen.com/).

The plugin connects your server to an Inari instance over WebSocket, lets players pair their account with a pairing code or QR code, and gives players and staff in-game commands to manage voice (mute, deafen, ban).


---

## Table of contents

- [Installation](#installation)
  - [Plugin installation](#plugin-installation)
  - [Resource pack installation](#resource-pack-installation)
  - [Inari installation](#inari-installation)
- [Plugin configuration](#plugin-configuration)
  - [config.toml](#configtoml)
  - [Commands](#commands)
  - [Permissions](#permissions)
- [Upcoming updates](#upcoming-updates)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Installation

### Plugin installation

**Requirements**

- An [Endstone](https://github.com/EndstoneMC/endstone) server (API version `0.11`)
- Python `>= 3.10`
- A running Inari instance (see [Inari installation](#inari-installation))

**Steps**

1. Download the latest `endstone_inari-<version>-py3-none-any.whl` from [Releases](https://github.com/CircuitCrafter2/Endstone-Proximity-Voice-Chat--InariConnector/releases).
2. Drop the `.whl` file into the `plugins/` folder of your Endstone server.
3. Restart the server.
4. The plugin generates its `config.toml` on first start. Fill it in (see [Plugin configuration](#plugin-configuration)) and restart the server again.

> The plugin will not start the voice connector until both `url` and `api_key` are set in `config.toml`. A message is logged in the console if one of them is missing.

### Resource pack installation

> [!IMPORTANT]
> The resource pack is **required** for the plugin's forms to display correctly (for example the QR code shown by `/inari pair` and the centered text of the pairing form). Without it, those forms will not render as intended.

**Steps**

1. Get the resource pack: `InariRessourcePack` (or the ready-to-use `InnariConnectorPack.mcpack` file).
2. Copy the `InariRessourcePack` folder into the `resource_packs/` folder of your server.
3. Enable it for your world by adding it to your world's `world_resource_packs.json` (in `worlds/<your world>/`):

   ```json
   [
     {
       "pack_id": "e2eb5209-8e47-44dc-b68e-f9b020d4fffb",
       "version": [1, 0, 0]
     }
   ]
   ```


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


### Commands

The main command is `/inari`. It also works with the aliases `/vocal` and `/voice`.

#### Player commands

| Command | Description |
| --- | --- |
| `/inari info` | Shows your voice profile: mute, deafen and ban status, plus your live voice state. |
| `/inari gui` | Opens the Inari GUI with buttons to connect, mute and deafen. |
| `/inari pair` | Opens a form with a QR code, the connection link, your pairing code and the channel name. **Do not share this information.** |
| `/inari mute` | Requests a self-mute / unmute (toggle). |
| `/inari deafen` | Requests a self-deafen / undeafen (toggle). |

#### Staff commands

Staff commands are restricted to operators by default.

| Command | Description |
| --- | --- |
| `/inari staff info <target>` | Shows the voice status of a player (mute, deafen, ban, live state). |
| `/inari staff mute <target>` | Force-mutes a player. Run it again to lift the mute. |
| `/inari staff deafen <target>` | Force-deafens a player. Run it again to lift the deafen. |
| `/inari staff ban <target>` | Bans a player from the voice chat. Run it again to unban. |
| `/inari staff tempmute <target> <duration>` | Force-mutes a player for a limited time. |
| `/inari staff tempdeafen <target> <duration>` | Force-deafens a player for a limited time. |
| `/inari staff tempban <target> <duration>` | Bans a player from the voice chat for a limited time. |

**Duration format:** a number followed by a unit: `s` (seconds), `m` (minutes), `h` (hours) or `d` (days). Examples: `30s`, `10m`, `2h`, `1d`.

> A player must have joined the server at least once to be targeted by a staff command.

#### Other commands

| Command | Description |
| --- | --- |
| `/test` | Simple command to check that the plugin is loaded. Operators only. |

### Permissions

| Permission | Default | Description |
| --- | --- | --- |
| `inari.command.inari` | everyone | Use the `/inari` command. |
| `inari.command.public.info` | everyone | Use `/inari info`. |
| `inari.command.public.gui` | everyone | Use `/inari gui`. |
| `inari.command.public.pair` | everyone | Use `/inari pair`. |
| `inari.command.public.mute` | everyone | Use `/inari mute`. |
| `inari.command.public.deafen` | everyone | Use `/inari deafen`. |
| `inari.command.staff` | op | Use `/inari staff`. |
| `inari.command.staff.mute` | op | Use `/inari staff mute`. |
| `inari.command.staff.deafen` | op | Use `/inari staff deafen`. |
| `inari.command.staff.ban` | op | Use `/inari staff ban`. |
| `inari.command.staff.tempmute` | op | Use `/inari staff tempmute`. |
| `inari.command.staff.tempdeafen` | op | Use `/inari staff tempdeafen`. |
| `inari.command.staff.tempban` | op | Use `/inari staff tempban`. |
| `inari.command.test` | op | Use `/test`. |



---

## Upcoming updates

| Feature | Description | Status |
| --- | --- | --- |
| Statistical | Add a statistics system | :white_check_mark: Finish |
| Update | Add a system that warns if the plugin is no longer up to date. | :white_check_mark: Finish |
| Spy | Add a system that allows staff to eavesdrop on conversations without being nearby | :test_tube: In the latest Release Candidate |
| API | Add an API for developers | :calendar: Planned |
| Logos | Add in-game logos to display voice status | :calendar: Planned |

---

## Acknowledgements

Thanks to `! zelišče` for his explanation on QR codes with JSON UI and to [`TheDreWen`](https://github.com/thedrewen) for his help in general.

---

## License

This project is licensed under the [MIT License](LICENSE).
