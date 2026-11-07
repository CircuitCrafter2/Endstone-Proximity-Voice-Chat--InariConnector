from endstone import Player
from endstone.command import CommandSender

from ..utils import get_player_data, save_player_data


def execute(sender: CommandSender, args: list[str], data_path: str) -> bool:
    if not isinstance(sender, Player):
        sender.send_error_message("§4This command can only be executed by a player.")
        return True

    player_data = get_player_data(data_path, sender)
    if player_data is None:
        sender.send_error_message("§4Your player data could not be found. Try rejoining the server.")
        return True

    request = player_data.get("request")
    if not isinstance(request, dict):
        request = {"mute": False, "deafen": False}
        player_data["request"] = request
    request["deafen"] = True

    if not save_player_data(data_path, sender, player_data):
        sender.send_error_message("§4An error occurred while saving your deafen request.")
        return True

    sender.send_message("§aYou have successfully requested a self-deafen or undeafen.")
    return True
