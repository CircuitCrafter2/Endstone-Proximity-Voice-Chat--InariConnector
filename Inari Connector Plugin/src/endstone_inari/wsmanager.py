# Fichier : ws_manager.py
"""
Gestionnaire WebSocket pour le connecteur Inari (plugin Endstone).

Utilisation depuis ton plugin (exemple, à adapter) :

    def on_enable(self):
        ...
        self.connector = InariConnector(
            server=self.server,
            logger=self.logger,
            data_path=self.data_path,   # dossier où utils.py stocke les <uuid>.json
            url="wss://inari.example.com/ws",
            api_key="MA_CLE_API",
            channel="default",
        )
        self.connector.start()          # lance le thread WebSocket
        # tick() est appelé toutes les 6 ticks (~300 ms à 20 TPS) sur le thread principal
        self.server.scheduler.run_task(self, self.connector.tick, delay=0, period=6)

    def on_disable(self):
        self.connector.stop()

Dépendance externe : `websockets` (à déclarer dans les dépendances du plugin).

ARCHITECTURE (deux « mondes » qui ne se touchent jamais directement) :

  Thread principal Endstone                   Thread WebSocket (asyncio)
  -------------------------                   --------------------------
  tick() toutes les 300 ms                    _run() / _session()
   - lit les joueurs + fichiers JSON  ------>  envoie sync_connector_state
   - construit la liste `clients`      outbox  attend la réponse (transaction_uuid)
   - applique la réponse `connections` <------ dépose la réponse
     dans les fichiers JSON             inbox

  => Toute l'API Endstone ET tous les accès fichiers restent sur le thread
     principal (l'API Endstone n'est pas thread-safe, et ça évite que deux
     threads écrivent le même fichier JSON en même temps).
  => Le thread WebSocket ne manipule que du JSON déjà prêt.
"""
import asyncio
import datetime
import json
import math
import queue
import threading
import time
import uuid

import websockets

# Import relatif : utils.py doit être dans le même package que ce fichier.
# Si ton projet n'est pas un package, remplace par : import utils
from . import utils


class InariError(Exception):
    """Erreur renvoyée par Inari (message de kind "error")."""

    def __init__(self, code, message, details):
        super().__init__(f"{code} {message}: {details}")
        self.code = code
        self.message = message
        self.details = details


class InariConnector:
    # Inari refuse (erreur 400) les codes de moins de 6 caractères :
    # on les filtre côté plugin pour ne pas faire échouer toute la synchro.
    MIN_CODE_LENGTH = utils.MIN_CODE_LENGTH

    def __init__(self, server, logger, data_path, url, api_key, channel="default", debug_file=None):
        self.server = server
        self.logger = logger
        self.data_path = data_path
        self.url = url
        self.api_key = api_key
        self.channel = channel

        # ---- Mode debug : chemin du fichier où écrire le trafic brut (None = désactivé) ----
        self.debug_file = debug_file
        self._debug_lock = threading.Lock()

        # ---- État lisible depuis les deux threads (simples booléens/valeurs) ----
        self.connected = False      # True quand l'auth a réussi
        self.max_distance = None    # reçu dans la réponse d'auth
        self.app_version = None     # ex: "1.0.1-stable" ou "1.7.0-nightly"
        self._busy = False          # True tant qu'un sync est en vol (envoyé, réponse non reçue)

        # ---- File thread WebSocket -> thread principal ----
        # queue.Queue est thread-safe : le thread WS y dépose, le principal consomme.
        self._inbox = queue.Queue()

        # Remarque : l'association code -> UUID et les demandes de bascule envoyées
        # voyagent avec chaque requête (« contexte »), puis reviennent avec la
        # réponse. Cela évite toute confusion si un nouveau sync est construit
        # avant que la réponse précédente ait été traitée.

        # ---- Utilisé uniquement par le thread WebSocket ----
        self._thread = None
        self._loop = None           # boucle asyncio du thread WS
        self._main_task = None      # tâche principale (annulée pour arrêter proprement)
        self._outbox = None         # asyncio.Queue : thread principal -> thread WS
        self._ws = None             # connexion courante
        self._pending = {}          # transaction_uuid -> Future en attente de réponse

    # =====================================================================
    # CYCLE DE VIE (appelé depuis le thread principal)
    # =====================================================================

    def start(self):
        """Démarre le thread WebSocket (à appeler dans on_enable)."""
        self._debug("INFO", "=== session start ===")
        # On crée la boucle et la tâche ici (avant de lancer le thread) pour que
        # stop() puisse toujours annuler la tâche, même si on l'appelle très vite.
        self._loop = asyncio.new_event_loop()
        self._main_task = self._loop.create_task(self._run())
        self._thread = threading.Thread(
            target=self._thread_main, name="inari-ws", daemon=True
        )
        self._thread.start()

    def stop(self):
        """Arrête proprement le thread WebSocket (à appeler dans on_disable)."""
        self.connected = False
        loop, task = self._loop, self._main_task
        # La boucle peut déjà être fermée (ex: clé API rejetée => _run s'est terminé).
        if loop is not None and task is not None and not loop.is_closed():
            # On ne touche pas à la boucle depuis un autre thread directement :
            # call_soon_threadsafe est le seul moyen sûr de lui donner un ordre.
            # L'annulation ferme la connexion (sortie du `async with` dans _session).
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # boucle fermée entre-temps : rien à annuler
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _debug(self, direction, raw):
        """Ajoute une ligne horodatée à debug.txt (no-op si le mode debug est désactivé).

        direction : "SEND" (plugin -> Inari), "RECV" (Inari -> plugin) ou "INFO".
        `raw` est écrit tel quel, sans aucune modification.
        """
        if not self.debug_file:
            return
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).decode("utf-8", errors="replace")
        stamp = datetime.datetime.now().isoformat(timespec="milliseconds")
        try:
            with self._debug_lock:  # appelé depuis plusieurs threads (principal + WS)
                with open(self.debug_file, "a", encoding="utf-8") as f:
                    f.write(f"[{stamp}] {direction} {raw}\n")
        except OSError:
            pass  # le debug ne doit jamais faire planter le connecteur

    # =====================================================================
    # CÔTÉ THREAD PRINCIPAL : tick() est le point d'entrée du scheduler
    # =====================================================================

    def tick(self):
        """Appelé toutes les ~300 ms par le scheduler Endstone (thread principal)."""
        # 1) D'abord, on traite les réponses déjà arrivées (états mute/deafen).
        self._apply_responses()

        # 2) On n'envoie rien si on n'est pas connecté, ou si le sync précédent
        #    n'a pas encore reçu sa réponse. Important : on ne construit PAS
        #    l'instantané dans ces cas-là, car construire = consommer les
        #    demandes de bascule (mute/deafen). Si on les consommait sans envoyer,
        #    elles seraient perdues.
        if not self.connected or self._busy:
            return

        clients, context = self._build_clients()
        self._busy = True
        try:
            # Passage sûr du thread principal vers la boucle asyncio du thread WS.
            self._loop.call_soon_threadsafe(
                self._outbox.put_nowait, ({"clients": clients}, context)
            )
        except RuntimeError:
            # La boucle vient de se fermer (arrêt du plugin) : on abandonne.
            self._busy = False

    def _build_clients(self):
        """Construit la liste `clients` du message sync_connector_state.

        Retourne (clients, contexte). Le contexte contient :
          - code_to_uuid : code envoyé -> UUID du joueur (pour lire la réponse) ;
          - toggles      : demandes de bascule incluses dans CE sync.
        Les demandes de bascule ne sont PAS effacées ici : elles ne le sont qu'une
        fois la réponse reçue (voir _apply_responses). Si le sync échoue (timeout,
        rejet), elles restent dans le fichier et sont renvoyées au sync suivant.
        """
        clients = []
        code_to_uuid = {}
        toggles = {}

        for player in self.server.online_players:
            # Lecture du fichier <uuid>.json géré par utils.py
            data = utils.get_player_data(self.data_path, player)
            if data is None:
                continue  # init_player_file() n'a pas (encore) été appelé pour ce joueur

            # Pas de code => le joueur n'a pas lié son compte vocal : on l'ignore.
            code = data.get("code")
            if not code or len(code) < self.MIN_CODE_LENGTH:
                continue

            uuid_str = utils.get_uuid_string(player)

            # Joueur banni du vocal : on ne l'envoie pas du tout.
            if self._is_active(uuid_str, data, "is_ban", "end_ban"):
                continue

            # Mute forcé (état persistant) : renvoyé tel quel à CHAQUE sync
            # tant que le mute n'est pas levé ou expiré.
            force_muted = self._is_active(
                uuid_str, data, "is_force_muted", "end_force_muted"
            )

            # Sourdine forcée (état persistant, même logique que le mute forcé).
            # Requis par les serveurs Inari "nightly" (sans valeur par défaut) et
            # simplement ignoré par les serveurs "stable" : on l'envoie donc toujours.
            force_deafened = self._is_active(
                uuid_str, data, "is_force_deafened", "end_force_deafened"
            )

            # Bascules demandées par le joueur (ex: /mute pour couper son propre micro).
            # Ce sont des TOGGLES : on les envoie à true, et on ne les remet à false
            # dans le fichier qu'une fois la réponse reçue (sinon l'état s'inverserait
            # toutes les 300 ms, ou la demande serait perdue en cas d'échec du sync).
            request = data.get("request") or {}
            toggle_muted = bool(request.get("mute"))
            toggle_deafened = bool(request.get("deafen"))
            if toggle_muted or toggle_deafened:
                toggles[uuid_str] = {"mute": toggle_muted, "deafen": toggle_deafened}

            loc = player.location
            entry = {
                "code": code,
                "display_name": player.name,
                "position": [loc.x, loc.y, loc.z],
                "head": self._head_vector(loc.yaw, loc.pitch),
                "is_force_muted": force_muted,
                "is_force_deafened": force_deafened,
                "actions": {
                    "toggle_muted": toggle_muted,
                    "toggle_deafened": toggle_deafened,
                },
            }
            # `group` est optionnel : on ne l'envoie que s'il est défini
            # (sinon Inari utilise le groupe "default").
            if data.get("group"):
                entry["group"] = data["group"]

            clients.append(entry)
            code_to_uuid[code] = uuid_str

        return clients, {"code_to_uuid": code_to_uuid, "toggles": toggles}

    def _apply_responses(self):
        """Écrit dans les fichiers JSON l'état mute/deafen renvoyé par Inari."""
        while True:
            try:
                context, connections = self._inbox.get_nowait()
            except queue.Empty:
                return

            # Le sync a réussi : les bascules qu'il contenait sont consommées.
            # On ne retire que ce qui a été envoyé : une nouvelle demande faite
            # pendant que le sync était en vol est conservée pour le suivant.
            for uuid_str, sent in context["toggles"].items():
                self._consume_toggles(uuid_str, sent)

            code_to_uuid = context["code_to_uuid"]
            for conn in connections:
                if conn.get("is_connector"):
                    continue  # on ne s'intéresse qu'aux joueurs
                uuid_str = code_to_uuid.get(conn.get("code"))
                if uuid_str is None:
                    continue  # connecté à Inari mais pas (ou plus) en jeu

                # Inari est la source de vérité de l'état : on le recopie dans "state".
                new_state = {
                    "mute": bool(conn.get("is_muted")),
                    "deafen": bool(conn.get("is_deafened")),
                }
                data = utils.get_player_data(self.data_path, uuid_str)
                # On n'écrit sur le disque que si quelque chose a changé
                # (sinon on réécrirait le fichier toutes les 300 ms).
                if data is not None and data.get("state") != new_state:
                    utils.update_player_data(self.data_path, uuid_str, "state", new_state)

    def _consume_toggles(self, uuid_str, sent):
        """Remet à false les demandes de bascule qui viennent d'être envoyées."""
        data = utils.get_player_data(self.data_path, uuid_str)
        if data is None:
            return
        request = data.get("request")
        if not isinstance(request, dict):
            request = {}
        new_request = {
            "mute": bool(request.get("mute")) and not sent["mute"],
            "deafen": bool(request.get("deafen")) and not sent["deafen"],
        }
        if request != new_request:
            utils.update_player_data(self.data_path, uuid_str, "request", new_request)

    def _is_active(self, uuid_str, data, flag_key, end_key):
        """
        Dit si un état temporaire (mute, ban...) est actif, en gérant l'expiration.

        Hypothèse : `end_*` vaut False (pas de fin => permanent) ou un timestamp
        UNIX en secondes (ex: time.time() + parse_duration("2h")).
        """
        if not data.get(flag_key):
            return False

        end = data.get(end_key)
        if isinstance(end, (int, float)) and not isinstance(end, bool):
            if time.time() >= end:
                # Expiré : on remet les deux champs à zéro, en mémoire ET sur disque.
                data[flag_key] = False
                data[end_key] = False
                utils.update_player_fields(
                    self.data_path, uuid_str, {flag_key: False, end_key: False}
                )
                return False
        return True

    @staticmethod
    def _head_vector(yaw_deg, pitch_deg):
        """
        Convertit yaw/pitch (degrés) en vecteur de direction UNITAIRE.

        Convention Minecraft : yaw 0 regarde vers +Z, pitch positif regarde vers le bas.
        Le résultat a toujours une longueur de 1 (exigé par Inari).
        À vérifier en jeu : si les voix sont inversées gauche/droite, c'est ici.
        """
        yaw = math.radians(yaw_deg)
        pitch = math.radians(pitch_deg)
        return [
            -math.sin(yaw) * math.cos(pitch),
            -math.sin(pitch),
            math.cos(yaw) * math.cos(pitch),
        ]

    # =====================================================================
    # CÔTÉ THREAD WEBSOCKET (asyncio) : rien ici ne doit toucher à Endstone
    # =====================================================================

    def _thread_main(self):
        """Point d'entrée du thread WS : fait tourner la boucle asyncio."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass  # arrêt demandé par stop() : normal
        finally:
            self._loop.close()

    async def _run(self):
        """Boucle de (re)connexion : relance une session si la connexion tombe."""
        self._outbox = asyncio.Queue()  # créée dans la boucle qui va l'utiliser
        delay = 1  # délai avant reconnexion, double à chaque échec (max 30 s)

        while True:
            started = time.monotonic()
            try:
                await self._session()
            except asyncio.CancelledError:
                raise  # stop() : on laisse remonter pour terminer proprement
            except InariError as e:
                if e.code == 401:
                    # Mauvaise clé API : réessayer ne servirait à rien.
                    self.logger.error(f"API key rejected: {e.details}")
                    return
                self.logger.warning(f"Error: {e}")
            except Exception as e:
                self.logger.warning(f"Connection lost: {e!r}")

            # Si la session a tenu un moment, la panne est récente : on repart à 1 s.
            if time.monotonic() - started > 30:
                delay = 1
            self.logger.info(f"Retrying in {delay}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    async def _session(self):
        """Une connexion complète : connexion -> auth -> boucle de synchro."""
        async with websockets.connect(self.url) as ws:
            self._ws = ws
            # La lecture tourne en tâche de fond AVANT le premier envoi,
            # sinon la réponse d'auth pourrait arriver sans personne pour la lire.
            reader = asyncio.create_task(self._read_loop(ws))
            try:
                # `auth` doit être le premier message, et n'être envoyé qu'une fois
                # par connexion (c'est pour ça qu'on reconnecte pour ré-authentifier).
                auth = await self.request(
                    "auth",
                    {"is_connector": True, "auth_key": self.api_key, "channel": self.channel},
                )
                self.max_distance = auth.get("max_distance")
                self.app_version = auth.get("app_version")

                # Remise à zéro : on jette ce qui aurait pu rester d'une ancienne session.
                while not self._outbox.empty():
                    self._outbox.get_nowait()
                self._busy = False
                self.connected = True
                self.logger.info(f"Connected (max distance: {self.max_distance}; server version: {self.app_version})")

                while True:
                    # Attend qu'un instantané soit déposé par tick() (thread principal).
                    payload, context = await self._outbox.get()
                    try:
                        result = await self.request(
                            "sync_connector_state", payload, timeout=2.0
                        )
                        # On renvoie la réponse au thread principal (il fera les écritures fichiers).
                        self._inbox.put((context, result.get("connections", [])))
                    except asyncio.TimeoutError:
                        self.logger.warning("No response to sync request (timeout)")
                    except InariError as e:
                        self.logger.warning(f"Sync request rejected: {e}")
                    finally:
                        # Dans tous les cas, tick() peut de nouveau envoyer.
                        self._busy = False
            finally:
                self.connected = False
                self._busy = False
                self._ws = None
                reader.cancel()

    async def request(self, kind, data, timeout=5.0):
        """Envoie un message et attend la réponse portant le même transaction_uuid."""
        transaction_uuid = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[transaction_uuid] = future  # "j'attends la réponse à celui-ci"
        try:
            raw = json.dumps({"kind": kind, "data": data, "transaction_uuid": transaction_uuid})
            self._debug("SEND", raw)
            await self._ws.send(raw)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(transaction_uuid, None)  # nettoyage dans tous les cas

    async def _read_loop(self, ws):
        """Lit tous les messages entrants et les associe à la requête d'origine."""
        try:
            async for raw in ws:
                self._debug("RECV", raw)  # avant tout traitement : message brut
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue  # JSON invalide : ignoré, comme le fait Inari
                if not isinstance(message, dict):
                    continue

                future = self._pending.get(message.get("transaction_uuid"))
                if future is None or future.done():
                    continue  # réponse inconnue ou requête déjà expirée

                if message.get("kind") == "error":
                    err = message.get("data") or {}
                    future.set_exception(
                        InariError(err.get("code"), err.get("message"), err.get("details"))
                    )
                else:
                    future.set_result(message.get("data") or {})
        finally:
            # Connexion fermée : on débloque tous ceux qui attendaient une réponse.
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("Inari connection closed"))