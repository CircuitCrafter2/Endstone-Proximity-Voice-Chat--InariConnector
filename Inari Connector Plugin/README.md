# Inari Connector Plugin

Plugin [Endstone](https://github.com/EndstoneMC/endstone) (Minecraft Bedrock Dedicated Server) qui
connecte les joueurs à un serveur [Inari](https://inari.yourserver.com/) pour fournir un
**chat vocal de proximité**.

## Installation

```bash
pip install build        # ou : uv build
python -m build          # génère le .whl dans dist/
```

Copiez le `.whl` de `dist/` dans le dossier `plugins/` du serveur, puis redémarrez.
Pour le développement, `pip install -e .` dans le virtualenv du serveur puis `/reload`.

## Configuration (`config.toml`)

| Clé | Description |
|-----|-------------|
| `connection.url` | URL WebSocket du serveur Inari (`wss://.../ws`) |
| `connection.api_key` | Clé API (**obligatoire**, sinon le connecteur ne démarre pas) |
| `connection.channel` | Canal vocal utilisé |
| `clients.code_length` | Longueur du code d'appairage des joueurs (minimum 6, défaut 8) |
| `clients.connect_url` | URL de la page web Inari donnée aux joueurs |

## Commandes

Alias : `/vocal`, `/voice`.

| Commande | Permission | Description |
|----------|------------|-------------|
| `/inari info` | `inari.command.public.info` | Affiche votre profil vocal |
| `/inari gui` | `inari.command.public.gui` | Ouvre l'interface |
| `/inari pair` | `inari.command.public.pair` | QR code / code de connexion |
| `/inari mute` / `deafen` | `inari.command.public.mute` / `.deafen` | Bascule votre micro / casque |
| `/inari staff info <joueur>` | `inari.command.staff.info` | Infos d'un joueur |
| `/inari staff mute\|deafen\|ban <joueur>` | `inari.command.staff.<action>` | Bascule l'état (permanent) |
| `/inari staff tempmute\|tempdeafen\|tempban <joueur> <durée>` | `inari.command.staff.<action>` | État temporaire (`10s`, `30m`, `2h`, `1d`) |

`<joueur>` peut être un pseudo (en ligne ou déjà venu sur le serveur) ou un UUID.

## Données

Un fichier `<uuid>.json` par joueur est créé dans `plugins/Inari/data/` (pseudo, code d'appairage,
états mute/deafen/ban forcés, demandes en attente, état vocal courant).
Le code d'appairage est un secret : il ne doit pas être partagé.
