from __future__ import annotations

from endstone_papi import PlaceholderExpansion  # pyright: ignore[reportMissingImports]

from .utils import get_glyph_state, get_player_data


class InariExpansion(PlaceholderExpansion):
    """Placeholder %inari_global_status% : glyphes d'état vocal du joueur."""

    identifier = "inari"
    author = "CircuitCrafter"
    version = "1.0.0"

    # Défini par le plugin juste après la création (voir InariPlugin._register_placeholders)
    datapath = None

    def on_request(self, player, params):
        if self.datapath is None:
            return None
        player_config = get_player_data(self.datapath, player)
        if player_config is None:
            return None
        if params == "global_status":
            return str(get_glyph_state(player_config))
        return None