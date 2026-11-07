from urllib.parse import urlencode

from endstone import Player
from endstone.command import CommandSender
from endstone.form import ActionForm, Button, Label

from ..utils import get_player_data

# Must match the prefix handled by the resource pack (ui/server_form.json):
# a button whose icon starts with this prefix is drawn as a QR code.
QR_PREFIX = "qr:"

# Same idea for labels: a label whose text starts with this prefix is
# displayed centered by the resource pack (the prefix itself is removed).
CENTER_PREFIX = "ctr:"

conf = {
    "url": "",
    "channel": "",
}


def importconfig(config: dict):
    cfg = config.get("clients", {})
    conf["url"] = cfg.get("connect_url", "")
    cfg = config.get("connection", {})
    conf["channel"] = cfg.get("channel", "")
    return True


def execute(sender: CommandSender, args: list[str], data_path: str) -> bool:
    if not isinstance(sender, Player):
        sender.send_error_message("§4This command can only be executed by a player.")
        return True

    player_data = get_player_data(data_path, sender)
    if player_data is None:
        sender.send_error_message("§4Your player data could not be found. Try rejoining the server.")
        return True

    code = player_data.get("code")
    if not code:
        sender.send_error_message("§4No pairing code found for your account. Try rejoining the server.")
        return True

    if not conf["url"]:
        sender.send_error_message("§4The voice chat connect URL is not configured on this server.")
        return True

    # Le code et le canal sont encodés : certains caractères casseraient l'URL.
    query = urlencode({"channel": conf["channel"], "code": code})
    full_link = conf["url"] + "?" + query
    qr_link = QR_PREFIX + full_link

    form = ActionForm(
        "Connect to voice chat",
        "Scan this QR code or enter the following link to connect to the voice chat :",
        [
            Button("", qr_link),
            Label(CENTER_PREFIX + f"Or go to \n§6{conf['url']}§r \nand enter the following login information:"),
            Label(f"  > Code : §6{code}§r\n  > Channel : §6{conf['channel']}§r"),
            Label("§4§l/!\\ Do not share this information or the QR code /!\\")
        ]
    )

    sender.send_form(form)
    return True