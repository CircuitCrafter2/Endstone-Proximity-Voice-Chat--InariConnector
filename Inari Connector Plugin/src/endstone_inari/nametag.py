import re

from . import utils

DEFAULT_FORMAT = "{name}"
DEFAULT_REFRESH_TICKS = 20
MIN_REFRESH_TICKS = 5

# {variable} intégrée (sans deux-points)
_VARIABLE = re.compile(r"\{(\w+)\}")
# {identifiant:paramètres} : syntaxe de PlaceholderAPI (le premier ':' sépare les deux)
_PAPI_PLACEHOLDER = re.compile(r"\{[^{}:]+:[^{}]*\}")


class NameTagManager:
    def __init__(self, server, logger, data_path, template, refresh_ticks):
        self._server = server
        self._logger = logger
        self._data_path = data_path
        self._template = template
        self.refresh_ticks = refresh_ticks

        # PlaceholderAPI n'est sollicité que si le format contient un {id:params}.
        self._uses_papi = bool(_PAPI_PLACEHOLDER.search(template))
        self._papi_cls = None       # classe PlaceholderAPI (importée à la demande)
        self._papi_missing = False  # endstone_papi introuvable : on n'insiste pas

        self._applied = {}          # uuid -> dernier name tag appliqué
        self._original = {}         # uuid -> name tag d'origine (pour le restaurer)
        self._warned = set()        # avertissements déjà affichés (pas de spam)

    # ------------------------------------------------------------------
    # Création depuis config.toml
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, conf, server, logger, data_path):
        """Retourne un NameTagManager, ou None si la fonctionnalité est désactivée."""
        cfg = conf.get("display", {})
        if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
            return None

        template = cfg.get("name_format", DEFAULT_FORMAT)
        if not isinstance(template, str) or not template.strip():
            logger.warning(f"Invalid [display] name_format, using '{DEFAULT_FORMAT}'")
            template = DEFAULT_FORMAT

        refresh = cfg.get("refresh_ticks", DEFAULT_REFRESH_TICKS)
        if isinstance(refresh, bool) or not isinstance(refresh, int):
            refresh = DEFAULT_REFRESH_TICKS
        refresh = max(refresh, MIN_REFRESH_TICKS)

        logger.info(f"Custom name format enabled: {template}")
        return cls(server, logger, data_path, template, refresh)

    # ------------------------------------------------------------------
    # Points d'entrée (thread principal)
    # ------------------------------------------------------------------

    def update_all(self):
        """Met à jour le pseudo de tous les joueurs en ligne (appelé par le scheduler)."""
        papi = self._load_papi()
        for player in list(self._server.online_players):
            self._update(player, papi)

    def update(self, player):
        """Met à jour le pseudo d'un seul joueur (ex: à sa connexion)."""
        self._update(player, self._load_papi())

    def forget(self, player):
        """À appeler quand un joueur quitte : libère sa mémoire."""
        uuid_str = utils.get_uuid_string(player)
        self._applied.pop(uuid_str, None)
        self._original.pop(uuid_str, None)

    def restore_all(self):
        """Rend leur pseudo d'origine aux joueurs en ligne (arrêt du plugin)."""
        for player in list(self._server.online_players):
            uuid_str = utils.get_uuid_string(player)
            if uuid_str not in self._applied:
                continue
            try:
                player.name_tag = self._original.get(uuid_str) or player.name
            except Exception:
                pass  # à l'arrêt, on ne veut surtout pas lever d'exception
        self._applied.clear()
        self._original.clear()

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _update(self, player, papi):
        try:
            tag = self._render(player, papi)
            uuid_str = utils.get_uuid_string(player)
            if self._applied.get(uuid_str) == tag:
                return  # rien n'a changé : on n'envoie rien aux clients
            if uuid_str not in self._original:
                self._original[uuid_str] = player.name_tag
            player.name_tag = tag
            self._applied[uuid_str] = tag
        except Exception as e:
            self._warn_once("update", f"Could not update a player's name tag: {e!r}")

    def _render(self, player, papi):
        text = self._template

        # 1) PlaceholderAPI d'abord : il laisse intactes nos {variables} (sans ':'),
        #    et ses valeurs ne sont jamais reparcourues par lui.
        if papi is not None:
            text = self._parse_papi(papi, player, text)

        # 2) Variables intégrées. Une variable inconnue reste écrite telle quelle,
        #    ce qui permet à l'admin de repérer sa faute de frappe.
        data = utils.get_player_data(self._data_path, player)
        values = {
            "name": player.name,
            "glyph": utils.get_glyph_state(data) if data else "",
            "group": str((data or {}).get("group") or ""),
        }
        text = _VARIABLE.sub(lambda m: values.get(m.group(1), m.group(0)), text)

        # Jamais de pseudo vide : on retombe sur le vrai pseudo.
        return text if text.strip() else player.name

    def _parse_papi(self, papi, player, text):
        try:
            return papi.set_placeholders(player, text)
        except Exception as e:
            self._warn_once("papi-parse", f"PlaceholderAPI could not parse the name format: {e!r}")
            return text

    def _load_papi(self):
        """Retourne le service PlaceholderAPI actif, ou None."""
        if not self._uses_papi or self._papi_missing:
            return None

        if self._papi_cls is None:
            try:
                from endstone_papi import PlaceholderAPI  # pyright: ignore[reportMissingImports]
            except ImportError:
                self._papi_missing = True
                self._warn_once(
                    "papi-missing",
                    "name_format contains PlaceholderAPI placeholders but PlaceholderAPI is not "
                    "installed: they are left as written",
                )
                return None
            self._papi_cls = PlaceholderAPI

        try:
            service = self._papi_cls.load(self._server.service_manager)
        except Exception:
            return None
        if service is None or not service.active:
            return None
        return service

    def _warn_once(self, key, message):
        if key not in self._warned:
            self._warned.add(key)
            self._logger.warning(message)
