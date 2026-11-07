import time

from endstone.command import CommandSender

from ...utils import get_player_data, parse_duration, resolve_target, save_player_data


def execute(sender: CommandSender, args: list[str], data_path: str, server) -> bool:
    if len(args) < 2:
        sender.send_error_message("Usage: /inari staff tempban <target> <duration>")
        return True

    target_identifier = args[0]
    duration_str = args[1]

    # Utilisation de la fonction centralisée dans utils.py
    duration_seconds = parse_duration(duration_str)
    if duration_seconds is None or duration_seconds <= 0:
        sender.send_error_message("§4Invalid duration format. Use numbers followed by s, m, h, or d (e.g., 2h, 1d).")
        return True

    uuid_str = resolve_target(server, data_path, target_identifier)
    player_config = get_player_data(data_path, uuid_str) if uuid_str else None
    if player_config is None:
        sender.send_error_message("§4This player has never logged in.")
        return True

    player_config["is_ban"] = True
    player_config["end_ban"] = time.time() + duration_seconds

    if not save_player_data(data_path, uuid_str, player_config):
        sender.send_error_message("§4An error occurred while modifying the file.")
        return True

    username = player_config.get("username", target_identifier)
    sender.send_message(f"§a{username} has been temporarily banned from voice chat for {duration_str}.")
    return True
