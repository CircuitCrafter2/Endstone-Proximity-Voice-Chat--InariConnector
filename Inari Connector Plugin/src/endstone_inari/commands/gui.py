from endstone import Player
from endstone.command import CommandSender
from endstone.form import ActionForm, Button, Divider

from ..utils import ban_state, deafen_state, get_player_data, mute_state
from . import deafen, mute, pair


def execute(sender: CommandSender, args: list[str], data_path: str) -> bool:
    if not isinstance(sender, Player):
        sender.send_error_message("§4This command can only be executed by a player.")
        return True

    # Récupération des données du joueur connecté
    player_config = get_player_data(data_path, sender)
    if player_config is None:
        sender.send_error_message("§4Your player data could not be found. Try rejoining the server.")
        return True

    # Récupération de l'état en direct (section "state" du JSON)
    live_state = player_config.get("state") or {}
    is_currently_muted = live_state.get("mute", False)
    is_currently_deafened = live_state.get("deafen", False)

    # Le contenu d'un formulaire est une simple chaîne de texte.
    code = player_config.get("code")
    if not code:
        status = "Please connect with §e/inari pair§r to use proximity voice chat."
    elif player_config.get("is_ban") is True:
        status = "§4You are currently banned from proximity voice chat."
    else:
        status = "\n".join([
            f"§bYour Inari Voice Profile (§e{player_config.get('username', sender.name)}§b)",
            f"Mute status : {mute_state(player_config)}",
            f"Deafen status : {deafen_state(player_config)}",
            f"Ban status : {ban_state(player_config)}",
            f"Active Voice -> Muted: {is_currently_muted} | Deafened: {is_currently_deafened}",
        ])

    # Les callbacks reçoivent le joueur qui a cliqué ; on les passe par référence
    # (sans parenthèses), ils sont appelés par Endstone au moment du clic.
    def on_pair(player: Player):
        pair.execute(player, [], data_path)

    def on_mute(player: Player):
        mute.execute(player, [], data_path)

    def on_deafen(player: Player):
        deafen.execute(player, [], data_path)

    form = ActionForm(
        "Inari voice GUI",
        status,
        [
            Divider(),
            Button("Connect to Inari", None, on_pair),
            Button("Mute", None, on_mute),
            Button("Deafen", None, on_deafen),
            Button("Close", None, None)
        ],
        None,
        None
    )

    sender.send_form(form)
    return True
