from endstone.command import CommandSender

from ...utils import ban_state, deafen_state, get_player_data, mute_state, resolve_target, last_time, active_time


def execute(sender: CommandSender, args: list[str], data_path: str, server) -> bool:
    if len(args) < 1:
        sender.send_error_message("Usage: /inari staff info <target>")
        return True

    uuid_str = resolve_target(server, data_path, args[0])
    player_config = get_player_data(data_path, uuid_str) if uuid_str else None
    if player_config is None:
        sender.send_error_message("§4This player has never logged in.")
        return True

    # Récupération de l'état en direct (section "state" du JSON)
    live_state = player_config.get("state") or {}
    is_currently_muted = live_state.get("mute", False)
    is_currently_deafened = live_state.get("deafen", False)

    # Affichage du rapport complet
    sender.send_message("--------------------")
    sender.send_message(f"Information about §e{player_config.get('username', args[0])}")
    sender.send_message(f"Mute state : {mute_state(player_config)}")
    sender.send_message(f"Deafen state : {deafen_state(player_config)}")
    sender.send_message(f"Ban state : {ban_state(player_config)}")
    sender.send_message(f"Live Voice State : Muted: {is_currently_muted} | Deafened: {is_currently_deafened}")
    sender.send_message(f"§rActivity time : {active_time(player_config)} (Synchronized on {last_time(player_config)})")
    sender.send_message("--------------------")

    return True
