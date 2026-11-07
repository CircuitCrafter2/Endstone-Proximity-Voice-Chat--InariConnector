from endstone.command import CommandSender

from ...utils import get_player_data, resolve_target, save_player_data


def execute(sender: CommandSender, args: list[str], data_path: str, server) -> bool:
    if len(args) < 1:
        sender.send_error_message("Usage: /inari staff mute <target>")
        return True

    uuid_str = resolve_target(server, data_path, args[0])
    player_config = get_player_data(data_path, uuid_str) if uuid_str else None
    if player_config is None:
        sender.send_error_message("§4This player has never logged in.")
        return True

    # Bascule : si l'état est actif on le lève, sinon on l'active (permanent).
    if player_config.get("is_force_muted", False):
        player_config["is_force_muted"] = False
        player_config["end_force_muted"] = False
        action_type = "unmute"
    else:
        player_config["is_force_muted"] = True
        player_config["end_force_muted"] = False
        action_type = "mute"

    if not save_player_data(data_path, uuid_str, player_config):
        sender.send_error_message("§4An error occurred while modifying the file.")
        return True

    username = player_config.get("username", args[0])
    if action_type == "mute":
        sender.send_message(f"§a{username} has been muted from voice chat.")
    else:
        sender.send_message(f"§a{username} has been unmuted from voice chat.")

    return True
