from endstone import Player, Server
from endstone.boss import BarColor, BarStyle
from endstone.command import CommandSender

from ...utils import ban_state, deafen_state, get_player_data, get_uuid_string, mute_state, resolve_target, save_player_data


_active: dict[str, dict] = {}


def _default_spy() -> dict:
    return {"active": False, "target": None}

def _get_spy(config: dict) -> dict:
    """Retourne config["staff"]["spy"] (créé ou réparé s'il est absent/invalide)."""
    staff = config.get("staff")
    if not isinstance(staff, dict):
        staff = {}
        config["staff"] = staff
    spy = staff.get("spy")
    if not isinstance(spy, dict):
        spy = _default_spy()
        staff["spy"] = spy
    return spy

def stop_spy(data_path: str, spy_uuid: str, server: Server | None = None, message: str | None = None) -> None:
    """Arrête le spy de `spy_uuid` : retire la boss bar, remet le JSON à zéro et,
    si `message` est donné et que le surveillant est en ligne, le prévient."""
    info = _active.pop(spy_uuid, None)
    if info is not None:
        info["bar"].remove_all()

    config = get_player_data(data_path, spy_uuid)
    if config is not None:
        _get_spy(config).update(_default_spy())
        save_player_data(data_path, spy_uuid, config)

    if message and server is not None:
        for player in server.online_players:
            if get_uuid_string(player) == spy_uuid:
                player.send_message(message)
                break

def handle_quit(data_path: str, server: Server, quitting_player: Player) -> None:
    """À appeler quand un joueur quitte le serveur (PlayerQuitEvent)."""
    quitting_uuid = get_uuid_string(quitting_player)

    # 1) Le joueur qui part surveillait quelqu'un : on nettoie (il est déjà hors ligne).
    if quitting_uuid in _active:
        stop_spy(data_path, quitting_uuid)

    # 2) Le joueur qui part était surveillé : on arrête ces spys et on prévient.
    for spy_uuid, info in list(_active.items()):
        if info["target"] == quitting_uuid:
            name = info.get("target_name", quitting_player.name)
            stop_spy(
                data_path,
                spy_uuid,
                server,
                f"§r-----End of {name}§r's spy ({name} left the server)-----",
            )

def stop_all(data_path: str) -> None:
    """Arrête tous les spys (à appeler dans on_disable / rechargement du plugin)."""
    for spy_uuid in list(_active):
        stop_spy(data_path, spy_uuid)


def execute(sender: CommandSender, args: list[str], data_path: str, server: Server) -> bool:
    if len(args) < 1:
        sender.send_error_message("Usage: /inari staff spy <target>")
        return True

    if not isinstance(sender, Player):
        sender.send_error_message("§4This command can only be executed by a player.")
        return True

    uuid_str = resolve_target(server, data_path, args[0])
    player_config = get_player_data(data_path, uuid_str) if uuid_str else None
    if player_config is None:
        sender.send_error_message("§4This player has never logged in.")
        return True

    sender_uuid = get_uuid_string(sender)
    sender_config = get_player_data(data_path, sender)
    if sender_config is None:
        sender.send_error_message("§4An error occurred while activating spy mode.")
        return True

    # ------------------------------------------------------------------
    # Quitter le mode spy : /inari staff spy <son propre pseudo>
    # ------------------------------------------------------------------
    if uuid_str == sender_uuid:
        if sender_uuid not in _active and not _get_spy(sender_config).get("active"):
            sender.send_error_message("§4You are not spying on anyone.")
            return True

        previous = _active.get(sender_uuid, {})
        previous_name = previous.get("target_name", "the player")
        stop_spy(data_path, sender_uuid)
        sender.send_message(f"§r-----End of {previous_name}§r's spy-----")
        return True

    # ------------------------------------------------------------------
    # Activer le mode spy (ou changer de cible)
    # ------------------------------------------------------------------
    online = {get_uuid_string(p) for p in server.online_players}
    if uuid_str not in online:
        sender.send_error_message("§4The target must be online to be spied on.")
        return True

    target_name = player_config.get("username", args[0])

    # Live state du joueur surveillé (section "state" du JSON)
    live_state = player_config.get("state") or {}
    is_currently_muted = live_state.get("mute", False)
    is_currently_deafened = live_state.get("deafen", False)

    # 1) On enregistre l'état dans le fichier (c'est ce que lit wsmanager)
    spy = _get_spy(sender_config)
    spy["active"] = True
    spy["target"] = uuid_str
    if not save_player_data(data_path, sender, sender_config):
        sender.send_error_message("§4An error occurred while activating spy mode.")
        return True

    # 2) Déjà en train de surveiller quelqu'un : on retire l'ancienne boss bar
    previous = _active.pop(sender_uuid, None)
    if previous is not None:
        previous["bar"].remove_all()

    # 3) Nouvelle boss bar, gardée en mémoire
    bar = server.create_boss_bar(
        f"You spy {target_name}'s voice",
        BarColor.WHITE,
        BarStyle.SOLID,
    )
    bar.progress = 1.0
    _active[sender_uuid] = {"bar": bar, "target": uuid_str, "target_name": target_name}

    sender.send_message("§r--------------------")
    sender.send_message(f"§rInformation about §e{target_name}")
    sender.send_message(f"§rMute state : {mute_state(player_config)}")
    sender.send_message(f"§rDeafen state : {deafen_state(player_config)}")
    sender.send_message(f"§rBan state : {ban_state(player_config)}")
    sender.send_message(f"§rLive Voice State : Muted: {is_currently_muted} | Deafened: {is_currently_deafened}")
    sender.send_message("§r--------------------")
    sender.send_message("\n")
    sender.send_message(f"§r-----Beginning of {target_name}§r's spy-----")
    sender.send_message("§rDuring the spying session, you will not be able to speak and listen as if you were connected normally.")
    sender.send_message(f"§rYou will hear everything {target_name} hears, as well as everything he says.")
    sender.send_message("§rYour microphone will be muted and you will not be able to speak.")
    sender.send_message(f"§rTo exit, execute the command §6/inari staff spy {sender.name}§r.")
    sender.send_message("§r--------------------")
    bar.add_player(sender)

    return True