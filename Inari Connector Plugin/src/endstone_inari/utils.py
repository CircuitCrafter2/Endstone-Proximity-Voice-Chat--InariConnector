# Fichier : utils.py
import copy
import json
import logging
import os
import re
import secrets
import string
import uuid
from datetime import datetime

logger = logging.getLogger("endstone_inari")

# Inari refuse les codes de moins de 6 caractères.
MIN_CODE_LENGTH = 6
DEFAULT_CODE_LENGTH = 8

# Alphabet alphanumérique sans caractères ambigus (0/O, 1/l/I) : le code est
# saisi à la main par certains joueurs et placé dans une URL.
CODE_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")

config = {
    "code_length": DEFAULT_CODE_LENGTH,
}

# Cache mémoire des fichiers joueurs : {uuid: (mtime_ns, données)}.
# Évite de relire/parser le JSON de chaque joueur toutes les 300 ms.
_cache: dict[str, tuple[int, dict]] = {}


def importconfig(conf: dict):
    cfg = conf.get("clients", {})
    # "code_lenght" (ancienne faute de frappe) reste accepté en secours.
    length = cfg.get("code_length", cfg.get("code_lenght", DEFAULT_CODE_LENGTH))
    if isinstance(length, bool) or not isinstance(length, int):
        length = DEFAULT_CODE_LENGTH
    config["code_length"] = max(length, MIN_CODE_LENGTH)


def parse_duration(duration_str: str) -> int | None:
    """Convertit une chaîne de durée (ex: 1d, 2h, 30m, 10s) en secondes."""
    match = re.match(r"^(\d+)([dhms])$", duration_str.lower())
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
    }

    return value * multipliers.get(unit, 0)


def generate_code() -> str:
    length = max(config.get("code_length") or DEFAULT_CODE_LENGTH, MIN_CODE_LENGTH)
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


# ---------------------------------------------------------------------------
# Identifiants / chemins
# ---------------------------------------------------------------------------

def is_valid_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def get_uuid_string(player_or_uuid) -> str:
    """UUID canonique (minuscules, avec tirets) si valide, sinon la chaîne brute."""
    if isinstance(player_or_uuid, str):
        raw = player_or_uuid
    else:
        raw = str(getattr(player_or_uuid, "unique_id", ""))
    try:
        return str(uuid.UUID(raw))
    except (ValueError, AttributeError, TypeError):
        return raw


def _player_path(data_path: str, player_or_uuid) -> str | None:
    """Chemin du fichier joueur, ou None si l'identifiant n'est pas un UUID valide
    (empêche toute traversée de répertoire du type '../../fichier')."""
    uuid_str = get_uuid_string(player_or_uuid)
    if not is_valid_uuid(uuid_str):
        return None
    return os.path.join(data_path, f"{uuid_str}.json")


def get_player_file_path(data_path: str, player) -> str | None:
    return _player_path(data_path, player)


# ---------------------------------------------------------------------------
# Lecture / écriture des données joueur
# ---------------------------------------------------------------------------

def get_player_data(data_path: str, player_or_uuid) -> dict | None:
    """Retourne une COPIE des données du joueur (modifiable sans effet de bord)."""
    uuid_str = get_uuid_string(player_or_uuid)
    file_path = _player_path(data_path, uuid_str)
    if file_path is None:
        return None

    try:
        mtime = os.stat(file_path).st_mtime_ns
    except OSError:
        _cache.pop(uuid_str, None)
        return None

    cached = _cache.get(uuid_str)
    if cached is not None and cached[0] == mtime:
        return copy.deepcopy(cached[1])

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Unreadable player file {file_path}: {e!r}")
        return None

    if not isinstance(data, dict):
        logger.warning(f"Invalid player file (not an object): {file_path}")
        return None

    _cache[uuid_str] = (mtime, data)
    return copy.deepcopy(data)


def save_player_data(data_path: str, player_or_uuid, data: dict) -> bool:
    """Écriture atomique : fichier temporaire puis os.replace()."""
    uuid_str = get_uuid_string(player_or_uuid)
    file_path = _player_path(data_path, uuid_str)
    if file_path is None:
        return False

    tmp_path = file_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, file_path)
        _cache[uuid_str] = (os.stat(file_path).st_mtime_ns, copy.deepcopy(data))
        return True
    except OSError as e:
        logger.warning(f"Could not write player file {file_path}: {e!r}")
        _cache.pop(uuid_str, None)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False


def update_player_fields(data_path: str, player_or_uuid, fields: dict) -> bool:
    data = get_player_data(data_path, player_or_uuid)
    if data is None:
        return False
    data.update(fields)
    return save_player_data(data_path, player_or_uuid, data)


def update_player_data(data_path: str, player_or_uuid, key: str, value) -> bool:
    return update_player_fields(data_path, player_or_uuid, {key: value})


def forget_player(player_or_uuid) -> None:
    """Retire un joueur du cache mémoire (à appeler quand il quitte le serveur)."""
    _cache.pop(get_uuid_string(player_or_uuid), None)


def _default_data(username: str, uuid_str: str) -> dict:
    return {
        "username": username,
        "uuid": uuid_str,
        "code": generate_code(),
        "group": None,
        "is_force_muted": False,
        "end_force_muted": False,
        "is_force_deafened": False,
        "end_force_deafened": False,
        "is_ban": False,
        "end_ban": False,
        "request": {
            "mute": False,
            "deafen": False,
        },
        "state": {
            "mute": False,
            "deafen": False,
        },
        "statistics": {
            "total_time": 0,
            "session_history": {}
        },
        "staff": {
            "spy": {
                "active": False,
                "target": None,
            }
        }
    }


def init_player_file(data_path: str, player):
    """Crée le fichier UUID.json, met à jour le pseudo et complète les clés manquantes."""
    uuid_str = get_uuid_string(player)
    file_path = _player_path(data_path, uuid_str)
    if file_path is None:
        logger.warning(f"Invalid player UUID, no data file created: {uuid_str!r}")
        return

    defaults = _default_data(player.name, uuid_str)

    if not os.path.exists(file_path):
        save_player_data(data_path, uuid_str, defaults)
        return

    data = get_player_data(data_path, uuid_str)
    if data is None:
        # Fichier illisible/corrompu : on ne l'écrase pas (il peut contenir un ban),
        # l'erreur est déjà loguée par get_player_data.
        return

    changed = False

    if data.get("username") != player.name:
        data["username"] = player.name  # Mise à jour du pseudo
        changed = True

    # Migration : complète les clés absentes (anciens fichiers) sans toucher aux existantes.
    for key, default in defaults.items():
        if key not in data:
            data[key] = default
            changed = True
        elif isinstance(default, dict):
            if not isinstance(data[key], dict):
                data[key] = default
                changed = True
            else:
                for sub_key, sub_default in default.items():
                    if sub_key not in data[key]:
                        data[key][sub_key] = sub_default
                        changed = True

    # Spy : l'état ne survit pas à une reconnexion (la boss bar est en mémoire seulement)
    staff = data.get("staff")
    spy = staff.get("spy") if isinstance(staff, dict) else None
    if isinstance(spy, dict) and (spy.get("active") or spy.get("target") is not None):
        spy["active"] = False
        spy["target"] = None
        changed = True

    if changed:
        save_player_data(data_path, uuid_str, data)


# ---------------------------------------------------------------------------
# Résolution d'une cible (commandes staff)
# ---------------------------------------------------------------------------

def find_uuid_by_username(data_path: str, username: str) -> str | None:
    """Cherche (même hors ligne) un joueur par pseudo dans les fichiers de données."""
    wanted = username.lower()
    try:
        names = os.listdir(data_path)
    except OSError:
        return None

    for name in names:
        if not name.endswith(".json"):
            continue
        stem = name[:-5]
        if not is_valid_uuid(stem):
            continue
        data = get_player_data(data_path, stem)
        if data and str(data.get("username", "")).lower() == wanted:
            return get_uuid_string(stem)
    return None


def resolve_target(server, data_path: str, identifier: str) -> str | None:
    """Transforme un pseudo ou un UUID saisi par un admin en UUID (ou None)."""
    ident = identifier.strip().strip('"').strip("'")
    if not ident:
        return None

    if is_valid_uuid(ident):
        return get_uuid_string(ident)

    try:
        online = server.get_player(ident)
    except Exception:
        online = None
    if online is not None:
        return get_uuid_string(online)

    return find_uuid_by_username(data_path, ident)


# ---------------------------------------------------------------------------
# Affichage des états (utilisé par /inari info, la GUI et /inari staff info)
# ---------------------------------------------------------------------------

def _describe_state(config_data: dict, flag_key: str, end_key: str, label: str) -> str:
    value = config_data.get(flag_key)
    if value is True:
        # end_* faux/vide => permanent, sinon temporaire
        if not config_data.get(end_key):
            return f"§4{label} (Permanent)§r"
        return f"§4{label} (Temporary)§r"
    if value is False:
        return "§aFree§r"
    return "§eUndefined§r"


def mute_state(config_data: dict) -> str:
    return _describe_state(config_data, "is_force_muted", "end_force_muted", "Force Muted")


def deafen_state(config_data: dict) -> str:
    return _describe_state(config_data, "is_force_deafened", "end_force_deafened", "Force Deafened")


def ban_state(config_data: dict) -> str:
    return _describe_state(config_data, "is_ban", "end_ban", "Banned")

def active_time(config_data: dict) -> str:
    """Temps total actif sur Inari, ex: '1d 2h 5m 3s'."""
    statistics = config_data.get("statistics") or {}
    total = statistics.get("total_time", 0)

    # Sécurité : valeur absente, négative ou d'un mauvais type
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        total = 0
    total = max(int(total), 0)

    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def last_time(config_data: dict) -> str:
    """Date de fin de la dernière session, ou 'Never' s'il n'y en a pas."""
    statistics = config_data.get("statistics") or {}
    history = statistics.get("session_history") or {}

    last_date = None
    last_text = None

    for session in history.values():
        if not isinstance(session, dict):
            continue
        end_text = session.get("end_time")
        try:
            end_date = datetime.strptime(end_text, "%d/%m/%Y %H:%M:%S")
        except (TypeError, ValueError):
            continue   # entrée absente ou mal formée : on l'ignore

        if last_date is None or end_date > last_date:
            last_date, last_text = end_date, end_text

    return last_text if last_text else "Never"