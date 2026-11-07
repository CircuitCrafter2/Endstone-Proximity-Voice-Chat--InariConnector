from endstone import Player
from endstone.command import CommandSender

from ..utils import ban_state, deafen_state, get_player_data, mute_state, active_time, last_time


def execute(sender: CommandSender, args: list[str], data_path: str) -> bool:
    if not isinstance(sender, Player):
        sender.send_error_message("§4This command can only be executed by a player.")
        return True

    player_config = get_player_data(data_path, sender)
    if player_config is None:
        sender.send_error_message("§4Your player data could not be found. Try rejoining the server.")
        return True

    # Récupération de l'état en direct (section "state" du JSON)
    live_state = player_config.get("state") or {}
    is_currently_muted = live_state.get("mute", False)
    is_currently_deafened = live_state.get("deafen", False)

    # Affichage des informations au joueur
    sender.send_message("--------------------")
    sender.send_message(f"§bYour Inari Voice Profile (§e{player_config.get('username', sender.name)}§b)§r")
    sender.send_message(f"§rMute status : {mute_state(player_config)}")
    sender.send_message(f"§rDeafen status : {deafen_state(player_config)}")
    sender.send_message(f"§rBan status : {ban_state(player_config)}")
    sender.send_message(f"§rActive Voice -> Muted: {is_currently_muted} §r| Deafened: {is_currently_deafened}")
    sender.send_message(f"§rActivity time : {active_time(player_config)} (Synchronized on {last_time(player_config)})")
    sender.send_message("--------------------")

    return True
