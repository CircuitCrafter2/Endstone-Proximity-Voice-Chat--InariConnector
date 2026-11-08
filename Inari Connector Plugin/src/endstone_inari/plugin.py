"""Plugin Endstone Inari : chat vocal de proximité (connecteur WebSocket)."""

import os
import threading
import traceback
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

import requests
from packaging.version import InvalidVersion
from packaging.version import parse as parse_version

from endstone.command import Command, CommandSender
from endstone.plugin import Plugin

from . import utils
from .commands import deafen as cmd_deafen
from .commands import gui as cmd_gui
from .commands import info as cmd_info
from .commands import mute as cmd_mute
from .commands import pair as cmd_pair
from .commands.staff import ban as staff_ban
from .commands.staff import deafen as staff_deafen
from .commands.staff import info as staff_info
from .commands.staff import mute as staff_mute
from .commands.staff import tempban as staff_tempban
from .commands.staff import tempdeafen as staff_tempdeafen
from .commands.staff import tempmute as staff_tempmute
from .commands.staff import spy as staff_spy
from .listener import InariListener
from .wsmanager import InariConnector

# Actions de /inari <action> : execute(sender, args, data_path)
PUBLIC_ACTIONS = {
    "info": cmd_info.execute,
    "gui": cmd_gui.execute,
    "pair": cmd_pair.execute,
    "mute": cmd_mute.execute,
    "deafen": cmd_deafen.execute,
}

# Actions de /inari staff <action> : execute(sender, args, data_path, server)
STAFF_ACTIONS = {
    "info": staff_info.execute,
    "mute": staff_mute.execute,
    "deafen": staff_deafen.execute,
    "ban": staff_ban.execute,
    "tempmute": staff_tempmute.execute,
    "tempdeafen": staff_tempdeafen.execute,
    "tempban": staff_tempban.execute,
    "spy": staff_spy.execute,
}


class InariPlugin(Plugin):
    # The prefix shown in log messages, e.g. [ExamplePlugin] Hello!
    prefix = "Inari"

    # Must match the major.minor version of the Endstone API you are targeting.
    api_version = "0.11"
    soft_depend = ["papi"]
    # Commands are declared as a dict. Each key is the command name, and the value
    # configures how it appears in-game. The "permissions" list controls who can use it.
    commands = {
        "test": {
            "description": "Test the plugin",
            "usages": ["/test"],
            "permissions": ["inari.command.test"],
        },
        "inari": {
            "description": "Main plugin command.",
            "usages": [
                "/inari",
                "/inari (info|gui|pair|mute|deafen)<action: string>",
                "/inari staff (info|mute|deafen|ban|tempmute|tempdeafen|tempban|spy)<subaction: string> <target: target> [duration: string]",
                ],
            "permissions": ["inari.command.inari"],
            "aliases": ["vocal", "voice"],
        },
    }
    
    # Permissions are declared separately from commands. The "default" field controls
    # who gets the permission automatically: True = everyone, "op" = operators only,
    # False = no one (must be explicitly granted).
    permissions = {
        "inari.command.inari": {
            "description": "Allow users to use the /inari command.",
            "default": True,
        },
        "inari.command.test": {
            "description": "Allow users to use the /test command.",
            "default": "op",
        },
        "inari.command.public": {
            "description": "Allow users to use all /inari public command.",
            "default": True,
            "children": {
                "inari.command.public.info": True,
                "inari.command.public.gui": True,
                "inari.command.public.pair": True,
                "inari.command.public.mute": True,
                "inari.command.public.deafen": True,
            },
        },
        "inari.command.public.info": {
            "description": "Allow users to use the info command.",
            "default": True,
        },
        "inari.command.public.gui": {
            "description": "Allow users to use the gui.",
            "default": True,
        },
        "inari.command.public.pair": {
            "description": "Allow users to use the pair command.",
            "default": True,
        },
        "inari.command.public.mute": {
            "description": "Allow users to mute themselves.",
            "default": True,
        },
        "inari.command.public.deafen": {
            "description": "Allow users to deafen themselves.",
            "default": True,
        },
        "inari.command.staff": {
            "description": "Allow users to use the staff command.",
            "default": "op",
            "children": {
                "inari.command.staff.mute": True,
                "inari.command.staff.deafen": True,
                "inari.command.staff.ban": True,
                "inari.command.staff.tempmute": True,
                "inari.command.staff.tempdeafen": True,
                "inari.command.staff.tempban": True,
                "inari.command.staff.spy": True,
            },
        },
        "inari.command.staff.mute": {
            "description": "Allow users to mute another.",
            "default": "op",
        },
        "inari.command.staff.deafen": {
            "description": "Allow users to deafen another.",
            "default": "op",
        },
        "inari.command.staff.ban": {
            "description": "Allow users to ban another.",
            "default": "op",
        },
        "inari.command.staff.tempmute": {
            "description": "Allow users to temporarily mute another.",
            "default": "op",
        },
        "inari.command.staff.tempdeafen": {
            "description": "Allow users to temporarily deafen another.",
            "default": "op",
        },
        "inari.command.staff.tempban": {
            "description": "Allow users to temporarily ban another.",
            "default": "op",
        },
        "inari.command.staff.spy": {
            "description": "Allow users to spy another.",
            "default": "op",
        },        
    }


    def on_enable(self) -> None:
        self.save_default_config()

        # La config des modules utilitaires est importée en premier : elle doit
        # l'être même si le connecteur ne peut pas démarrer (clé API absente...).
        utils.importconfig(self.config)
        cmd_pair.importconfig(self.config)

        self.data_path = os.path.join(self.data_folder, "data")
        os.makedirs(self.data_path, exist_ok=True)
        self.logger.info(f"Player storage folder initialized to: {self.data_path}")

        self.register_events(InariListener(self))

        # Connection settings, read from config.toml
        cfg = self.config.get("connection", {})
        url = cfg.get("url", "")
        api_key = cfg.get("api_key", "")
        if not url or not api_key:
            self.logger.error("Missing 'url' or 'api_key' in config.toml, voice connector not started")
            return

        # Mode debug : journal brut des échanges WebSocket dans debug.txt
        debug_file = None
        if self.config.get("debug", False) is True:
            debug_file = os.path.join(self.data_folder, "debug.txt")
            self.logger.warning(f"Debug mode enabled: raw WebSocket traffic is written to {debug_file}")

        self.connector = InariConnector(
            server=self.server,
            logger=self.logger,
            data_path=self.data_path,
            url=url,
            api_key=api_key,
            channel=cfg.get("channel", "default"),
            debug_file=debug_file,
        )
        self.connector.start()
        # tick() runs every 6 ticks (~300 ms at 20 TPS) on the main thread
        self.server.scheduler.run_task(self, self.connector.tick, delay=0, period=6)

        self._register_placeholders()

        self.logger.info("Inari enabled!")
        threading.Thread(target=self.check_for_updates, name="inari-update-check", daemon=True).start()

    def _register_placeholders(self) -> None:
        """Enregistre l'expansion PlaceholderAPI si PAPI est installé (dépendance facultative)."""
        try:
            from endstone_papi import PlaceholderAPI  # pyright: ignore[reportMissingImports]
            from .PlaceholderExpansion import InariExpansion
        except ImportError:
            self.logger.info("PlaceholderAPI not found, placeholders are disabled")
            return

        try:
            service = PlaceholderAPI.load(self.server.service_manager)
            if service is None or not service.active:
                self.logger.info("PlaceholderAPI is not active, placeholders are disabled")
                return
            expansion = InariExpansion()
            expansion.datapath = self.data_path
            service.register_expansion(self, expansion)
        except Exception as e:
            self.logger.warning(f"Could not register the PlaceholderAPI expansion: {e}")

    def _current_version(self):
        """Version du plugin : celle d'Endstone si elle existe, sinon celle du paquet."""
        version = getattr(self, "version", None)
        if version:
            return str(version)
        try:
            return package_version("endstone-inari")
        except PackageNotFoundError:
            return None

    def check_for_updates(self):
        try:
            current_version = self._current_version()
            if current_version is None:
                self.logger.warning("Unable to determine the plugin version, update check skipped")
                return

            repo_url = (
                "https://api.github.com/repos/CircuitCrafter2/Endstone-Proximity-Voice-Chat--InariConnector/releases/latest"
            )
            response = requests.get(repo_url, timeout=5)

            if response.status_code != 200:
                self.logger.error(f"Unable to check for updates (HTTP Code: {response.status_code})")
                return

            data = response.json()
            latest_tag = data.get("tag_name")
            if not latest_tag:
                self.logger.warning("The latest GitHub release has no tag name, update check skipped")
                return

            # Tag non standard (ex: "release-final") : on ignore au lieu de lever une erreur
            latest_version = str(latest_tag).strip().lstrip("vV")
            try:
                latest = parse_version(latest_version)
                current = parse_version(current_version)
            except InvalidVersion:
                self.logger.warning(
                    f"Cannot compare versions (release tag: '{latest_tag}', current: '{current_version}'), update check skipped"
                )
                return

            if latest > current:
                self.logger.warning(f"A new version is available: {latest_version} (Current: {current_version})")
                self.logger.warning(f"You can download it here: {data.get('html_url')}")
            else:
                self.logger.info(f"Your plugin is up to date (version {current_version}).")
        except Exception as e:
            self.logger.error(f"Error checking for update: {e}")

    def on_disable(self) -> None:
        staff_spy.stop_all(self.data_path)
        if getattr(self, "connector", None) is not None:
            self.connector.stop()
        self.logger.info("Inari disabled!")

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        # On intercepte la commande principale /test
        if command.name == "test":
            if not sender.has_permission("inari.command.test"):
                sender.send_error_message("§4You do not have permission to execute this command.")
                return True
            sender.send_message("Test du plugin Inari réussi !")
            return True

        # On intercepte la commande principale /inari (et ses alias)
        if command.name == "inari":
            if len(args) == 0:
                sender.send_message("Usage: /inari <action> or /inari staff <action>")
                return True

            action = args[0].lower()

            # =================================================================
            # 1. BRANCHE STAFF (/inari staff <subaction> ...)
            # =================================================================
            if action == "staff":
                if not sender.has_permission("inari.command.staff"):
                    sender.send_error_message("§4You do not have permission to execute this command.")
                    return True

                if len(args) < 2:
                    sender.send_error_message("Required usage: /inari staff <action>")
                    return True

                sub_action = args[1].lower()
                handler = STAFF_ACTIONS.get(sub_action)
                if handler is None:
                    sender.send_error_message(f"§4Action staff '{sub_action}' unknown.")
                    return True

                # Permission spécifique (ex: inari.command.staff.mute)
                if not sender.has_permission(f"inari.command.staff.{sub_action}"):
                    sender.send_error_message(f"§4You do not have permission to execute the command {sub_action}.")
                    return True

                try:
                    return handler(sender, args[2:], self.data_path, self.server)
                except Exception:
                    self.logger.error(f"Error while running 'staff {sub_action}':\n{traceback.format_exc()}")
                    sender.send_error_message(f"§4Internal error while running the staff action '{sub_action}'.")
                    return True

            # =================================================================
            # 2. BRANCHE PUBLIQUE (/inari <action> ...)
            # =================================================================
            handler = PUBLIC_ACTIONS.get(action)
            if handler is None:
                sender.send_error_message(f"Unknown action '{action}'.")
                return True

            # Permission spécifique (ex: inari.command.public.info)
            if not sender.has_permission(f"inari.command.public.{action}"):
                sender.send_error_message(f"§4You do not have permission to use the command {action}.")
                return True

            try:
                return handler(sender, args[1:], self.data_path)
            except Exception:
                self.logger.error(f"Error while running '{action}':\n{traceback.format_exc()}")
                sender.send_error_message(f"§4Internal error while running the action '{action}'.")
                return True

        return False