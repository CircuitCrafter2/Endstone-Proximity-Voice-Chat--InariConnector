"""Écouteur d'évènements du plugin Inari.

Les listeners sont des classes séparées (pas le Plugin lui-même) qui contiennent
les méthodes @event_handler. Ils sont enregistrés dans on_enable avec
self.register_events().
"""

from endstone.event import EventPriority, PlayerJoinEvent, PlayerQuitEvent, event_handler
from endstone.plugin import Plugin

from .utils import forget_player, init_player_file
from .commands.staff import spy as staff_spy

class InariListener:
    def __init__(self, plugin: Plugin) -> None:
        self._plugin = plugin

    @event_handler(priority=EventPriority.HIGH)
    def on_player_join(self, event: PlayerJoinEvent) -> None:
        """Crée / met à jour le fichier de données du joueur qui se connecte."""
        init_player_file(self._plugin.data_path, event.player)

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        """Libère le cache mémoire du joueur qui quitte le serveur."""
        staff_spy.handle_quit(self._plugin.data_path, self._plugin.server, event.player)
        forget_player(event.player)
