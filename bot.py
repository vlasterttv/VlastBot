import json
import os
import random
import sqlite3
import threading
import unicodedata
import urllib.error
import urllib.request
import math
import statistics
import asyncio
import io
import urllib.parse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple
from itertools import combinations

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None  # type: ignore

# Requis pour la génération d'images style Koya
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERREUR] La librairie Pillow n'est pas installée. Tapez 'pip install Pillow' dans le terminal.")

# ===================== CONFIG =====================
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DB_PATH = os.getenv("PP_DB_PATH", "pp_bot.sqlite3")

VERIFY_CHANNEL_NAME = os.getenv("VERIFY_CHANNEL_NAME", "verification")
PREP_CHANNEL_NAMES = [
    name.strip()
    for name in os.getenv(
        "PREP_CHANNEL_NAMES",
        "Préparation 1,Préparation 2,Préparation 3,Préparation 4",
    ).split(",")
    if name.strip()
]

VERIFY_CHANNEL_ALIASES = [
    name.strip()
    for name in os.getenv(
        "VERIFY_CHANNEL_ALIASES",
        f"{VERIFY_CHANNEL_NAME},vérification,verification-rank,verif",
    ).split(",")
    if name.strip()
]

# Nouvelles catégories et salons
HOME_CATEGORY_NAME = os.getenv("HOME_CATEGORY_NAME", "⛩️ ・ GRAND PORTAIL ・ ⛩️")
ARTISANS_CATEGORY_NAME = os.getenv("ARTISANS_CATEGORY_NAME", "🏯 ・ QUARTIER DES ARTISANS ・ 🏯")
RANK_CATEGORY_NAME = os.getenv("RANK_CATEGORY_NAME", "🎭 ・ PARTIE PERSO ・ 🎭")
RANK_CHANNEL_NAME = os.getenv("RANK_CHANNEL_NAME", "🎭・choisi-ton-rank")
PARTY_CATEGORY_NAME = os.getenv("PARTY_CATEGORY_NAME", "PARTIE PERSO")
ORGA_TEXT_CHANNEL_NAME = os.getenv("ORGA_TEXT_CHANNEL_NAME", "orga-pp")
WELCOME_CHANNEL_NAME = os.getenv("WELCOME_CHANNEL_NAME", "├🏮・kaminarimon")

# Config Tickets
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "🏮 ・ TICKETS D'ASAKUSA ・ 🏮")
TICKET_CHANNEL_NAME = os.getenv("TICKET_CHANNEL_NAME", "├🎟️・créer-un-ticket")
METSUKE_ROLE_ID = 1460123520905380117

CUSTOM_VOICE_CATEGORY_ID = int(os.getenv("CUSTOM_VOICE_CATEGORY_ID", "0"))
CUSTOM_VOICE_CATEGORY_NAME = os.getenv("CUSTOM_VOICE_CATEGORY_NAME", ARTISANS_CATEGORY_NAME)
CUSTOM_VOICE_DEFAULT_LIMIT = int(os.getenv("CUSTOM_VOICE_DEFAULT_LIMIT", "0"))

CREATE_VOICE_TRIGGER_NAME = os.getenv("CREATE_VOICE_TRIGGER_NAME", "🔊・Créer un salon")
CREATE_VOICE_TRIGGER_ALIASES = [
    name.strip()
    for name in os.getenv(
        "CREATE_VOICE_TRIGGER_ALIASES",
        f"{CREATE_VOICE_TRIGGER_NAME},creer un salon,+ creer un salon,+ 🔊・Créer un salon",
    ).split(",")
    if name.strip()
]

NON_VERIFIED_ROLE = os.getenv("NON_VERIFIED_ROLE", "Non vérifié")
MEMBER_ROLE = os.getenv("MEMBER_ROLE", "Membre")
ORGA_ROLE = os.getenv("ORGA_ROLE", "Orga PP")
TEAM_ATTACK_ROLE = os.getenv("TEAM_ATTACK_ROLE", "Équipe Attaque")
TEAM_DEFENSE_ROLE = os.getenv("TEAM_DEFENSE_ROLE", "Équipe Défense")
PLAYER_ROLE = os.getenv("PLAYER_ROLE", "🌸・Pèlerin")

VALORANT_MAPS = [
    "Ascent",
    "Bind",
    "Haven",
    "Split",
    "Lotus",
    "Sunset",
    "Icebox",
    "Breeze",
    "Pearl",
    "Fracture",
    "Abyss",
    "Corrode",
    "Summit",
]

VOTE_THRESHOLD_ACCEPT = 5
VOTE_THRESHOLD_REJECT = 5

INTENTS = discord.Intents.default()
INTENTS.guilds = True
INTENTS.members = True
INTENTS.voice_states = True
INTENTS.messages = True
INTENTS.message_content = False
INTENTS.invites = True

RANK_OPTIONS: List[Tuple[str, int]] = [
    ("Fer 1", 100), ("Fer 2", 110), ("Fer 3", 120),
    ("Bronze 1", 200), ("Bronze 2", 210), ("Bronze 3", 220),
    ("Argent 1", 300), ("Argent 2", 310), ("Argent 3", 320),
    ("Or 1", 400), ("Or 2", 410), ("Or 3", 420),
    ("Platine 1", 500), ("Platine 2", 510), ("Platine 3", 520),
    ("Diamant 1", 600), ("Diamant 2", 610), ("Diamant 3", 620),
    ("Ascendant 1", 700), ("Ascendant 2", 710), ("Ascendant 3", 720),
    ("Immortal 1", 800), ("Immortal 2", 810), ("Immortal 3", 820),
    ("Radiant", 900),
]
RANK_VALUE_BY_NAME = {name: value for name, value in RANK_OPTIONS}

RANK_EMOJI_BY_NAME = {
    "Fer 1": "Iron_1_Rank",
    "Fer 2": "Iron_2_Rank",
    "Fer 3": "Iron_3_Rank",
    "Bronze 1": "Bronze_1_Rank",
    "Bronze 2": "Bronze_2_Rank",
    "Bronze 3": "Bronze_3_Rank",
    "Argent 1": "Silver_1_Rank",
    "Argent 2": "Silver_2_Rank",
    "Argent 3": "Silver_3_Rank",
    "Or 1": "Gold_1_Rank",
    "Or 2": "Gold_2_Rank",
    "Or 3": "Gold_3_Rank",
    "Platine 1": "Platinum_1_Rank",
    "Platine 2": "Platinum_2_Rank",
    "Platine 3": "Platinum_3_Rank",
    "Diamant 1": "Diamond_1_Rank",
    "Diamant 2": "Diamond_2_Rank",
    "Diamant 3": "Diamond_3_Rank",
    "Ascendant 1": "Ascendant_1_Rank",
    "Ascendant 2": "Ascendant_2_Rank",
    "Ascendant 3": "Ascendant_3_Rank",
    "Immortal 1": "Immortal_1_Rank",
    "Immortal 2": "Immortal_2_Rank",
    "Immortal 3": "Immortal_3_Rank",
    "Radiant": "Radiant_Rank",
}

RANK_TIER_EMOJI = {
    "Fer": "⚫",
    "Bronze": "🥉",
    "Argent": "🥈",
    "Or": "🥇",
    "Platine": "🔷",
    "Diamant": "💎",
    "Ascendant": "🟢",
    "Immortal": "👑",
    "Radiant": "🌟",
}

MAP_IMAGE: Dict[str, str] = {
    "Haven":    "https://media.valorant-api.com/maps/2bee0dc9-4ffe-519b-1cbd-7fbe763a6047/splash.png",
    "Corrode":  "https://media.valorant-api.com/maps/1c18ab1f-420d-0d8b-71d0-77ad3c439115/splash.png",
    "Icebox":   "https://media.valorant-api.com/maps/e2ad5c54-4114-a870-9641-8ea21279579a/splash.png",
    "Pearl":    "https://media.valorant-api.com/maps/fd267378-4d1d-484f-ff52-77821ed10dc2/splash.png",
    "Sunset":   "https://media.valorant-api.com/maps/92584fbe-486a-b1b2-9faa-39b0f486b498/splash.png",
    "Lotus":    "https://media.valorant-api.com/maps/2fe4ed3a-450a-948b-6d6b-e89a78e680a9/splash.png",
    "Abyss":    "https://media.valorant-api.com/maps/224b0a95-48b9-f703-1bd8-67aca101a61f/splash.png",
    "Breeze":   "https://media.valorant-api.com/maps/2fb9a4fd-47b8-4e7d-a969-74b4046ebd53/splash.png",
    "Ascent":   "https://media.valorant-api.com/maps/7eaecc1b-4337-bbf6-6ab9-04b8f06b3319/splash.png",
    "Split":    "https://media.valorant-api.com/maps/d960549e-485c-e861-8d71-aa9d1aed12a2/splash.png",
    "Fracture": "https://media.valorant-api.com/maps/b529448b-4d60-346e-e89e-00a4c527a405/splash.png",
    "Bind":     "https://media.valorant-api.com/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba/splash.png",
    "Summit":   "https://cdn.discordapp.com/attachments/1460123533828030699/1531838845157638164/1200px-Loading_Screen_Summit.png?ex=6a6aab98&is=6a695a18&hm=5cea97a069046a65a7b5cd94f4dcd2b84bffc1e3d925b912f966f46dafd127ed&",
}

# Ordre d'arrivée dans chaque vocal Préparation.
JOIN_SEQUENCE = 0
PREP_JOIN_ORDER: Dict[int, Dict[int, int]] = {}

def next_join_sequence() -> int:
    global JOIN_SEQUENCE
    JOIN_SEQUENCE += 1
    return JOIN_SEQUENCE

def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for sep in ["・", "|", "—", "-", "•", "·", "_", "/"]:
        text = text.replace(sep, " ")
    return " ".join(text.lower().split())

# ===================== DATABASE =====================
class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                rank_name TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS active_matches (
                prep_channel_id INTEGER PRIMARY KEY,
                started_by_id INTEGER NOT NULL,
                ui_message_id INTEGER NOT NULL,
                party_code TEXT NOT NULL,
                map_name TEXT NOT NULL,
                attack_ids TEXT NOT NULL,
                defense_ids TEXT NOT NULL,
                map_yes INTEGER NOT NULL DEFAULT 0,
                map_no INTEGER NOT NULL DEFAULT 0,
                map_locked INTEGER NOT NULL DEFAULT 0,
                map_voters TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        existing_columns = {row[1] for row in cur.execute("PRAGMA table_info(active_matches)").fetchall()}
        migrations = {
            "map_yes": "ALTER TABLE active_matches ADD COLUMN map_yes INTEGER NOT NULL DEFAULT 0",
            "map_no": "ALTER TABLE active_matches ADD COLUMN map_no INTEGER NOT NULL DEFAULT 0",
            "map_locked": "ALTER TABLE active_matches ADD COLUMN map_locked INTEGER NOT NULL DEFAULT 0",
            "map_voters": "ALTER TABLE active_matches ADD COLUMN map_voters TEXT NOT NULL DEFAULT '{}'",
        }
        for column, statement in migrations.items():
            if column not in existing_columns:
                cur.execute(statement)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_voice_rooms (
                channel_id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL
            )
            """
        )

        # ---------- RR TRACKER ----------
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rr_players (
                puuid TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                discord_id INTEGER,
                riot_name TEXT NOT NULL,
                riot_tag TEXT NOT NULL,
                region TEXT NOT NULL DEFAULT 'eu',
                platform TEXT NOT NULL DEFAULT 'pc',
                current_tier_id INTEGER NOT NULL DEFAULT 0,
                current_tier_name TEXT,
                current_rr INTEGER NOT NULL DEFAULT 0,
                elo INTEGER NOT NULL DEFAULT 0,
                peak_tier_id INTEGER NOT NULL DEFAULT 0,
                peak_tier_name TEXT,
                last_match_id TEXT,
                added_by INTEGER,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rr_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                puuid TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                match_id TEXT NOT NULL,
                rr_change INTEGER NOT NULL,
                rr_after INTEGER,
                tier_name TEXT,
                map_name TEXT,
                agent TEXT,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                rounds_won INTEGER,
                rounds_lost INTEGER,
                played_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (puuid, match_id)
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rr_history_guild_date ON rr_history (guild_id, played_at)")

        # Migration douce pour les bases déjà déployées (avant l'ajout du peak rank).
        for ddl in (
            "ALTER TABLE rr_players ADD COLUMN peak_tier_id INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE rr_players ADD COLUMN peak_tier_name TEXT",
        ):
            try:
                cur.execute(ddl)
            except sqlite3.OperationalError:
                pass  # la colonne existe déjà

        self.conn.commit()

    def upsert_player_rank(self, user_id: int, rank_name: str) -> None:
        self.conn.execute(
            """
            INSERT INTO players (user_id, rank_name)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET rank_name = excluded.rank_name
            """,
            (user_id, rank_name),
        )
        self.conn.commit()

    def get_player_rank(self, user_id: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT rank_name FROM players WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else None

    def register_custom_voice(self, channel_id: int, owner_id: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO custom_voice_rooms (channel_id, owner_id) VALUES (?, ?)",
            (channel_id, owner_id),
        )
        self.conn.commit()

    def get_custom_voice_owner(self, channel_id: int) -> Optional[int]:
        row = self.conn.execute(
            "SELECT owner_id FROM custom_voice_rooms WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        return int(row[0]) if row else None

    def delete_custom_voice(self, channel_id: int) -> None:
        self.conn.execute("DELETE FROM custom_voice_rooms WHERE channel_id = ?", (channel_id,))
        self.conn.commit()

    def save_active_match(
        self,
        prep_channel_id: int,
        started_by_id: int,
        ui_message_id: int,
        party_code: str,
        map_name: str,
        attack_ids: List[int],
        defense_ids: List[int],
        map_yes: int,
        map_no: int,
        map_locked: bool,
        map_voters: Dict[str, str],
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO active_matches (
                prep_channel_id, started_by_id, ui_message_id, party_code,
                map_name, attack_ids, defense_ids, map_yes, map_no, map_locked, map_voters
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prep_channel_id,
                started_by_id,
                ui_message_id,
                party_code,
                map_name,
                json.dumps(attack_ids),
                json.dumps(defense_ids),
                map_yes,
                map_no,
                int(map_locked),
                json.dumps(map_voters),
            ),
        )
        self.conn.commit()

    def get_active_match(self, prep_channel_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM active_matches WHERE prep_channel_id = ?",
            (prep_channel_id,),
        ).fetchone()

    def delete_active_match(self, prep_channel_id: int) -> None:
        self.conn.execute(
            "DELETE FROM active_matches WHERE prep_channel_id = ?",
            (prep_channel_id,),
        )
        self.conn.commit()

    # ---------- RR TRACKER ----------
    def rr_add_player(self, puuid: str, guild_id: int, discord_id: Optional[int],
                      riot_name: str, riot_tag: str, region: str, platform: str,
                      added_by: int) -> None:
        self.conn.execute(
            """
            INSERT INTO rr_players (puuid, guild_id, discord_id, riot_name, riot_tag,
                                    region, platform, added_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(puuid) DO UPDATE SET
                guild_id = excluded.guild_id,
                discord_id = COALESCE(excluded.discord_id, rr_players.discord_id),
                riot_name = excluded.riot_name,
                riot_tag = excluded.riot_tag,
                region = excluded.region,
                platform = excluded.platform
            """,
            (puuid, guild_id, discord_id, riot_name, riot_tag, region, platform, added_by),
        )
        self.conn.commit()

    def rr_remove_player(self, puuid: str) -> None:
        self.conn.execute("DELETE FROM rr_players WHERE puuid = ?", (puuid,))
        self.conn.execute("DELETE FROM rr_history WHERE puuid = ?", (puuid,))
        self.conn.commit()

    def rr_get_player(self, puuid: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM rr_players WHERE puuid = ?", (puuid,)).fetchone()

    def rr_find_player(self, guild_id: int, name: str, tag: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM rr_players
            WHERE guild_id = ? AND LOWER(riot_name) = LOWER(?) AND LOWER(riot_tag) = LOWER(?)
            """,
            (guild_id, name, tag),
        ).fetchone()

    def rr_find_by_discord(self, guild_id: int, discord_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM rr_players WHERE guild_id = ? AND discord_id = ?",
            (guild_id, discord_id),
        ).fetchone()

    def rr_list_players(self, guild_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM rr_players WHERE guild_id = ? ORDER BY riot_name COLLATE NOCASE",
            (guild_id,),
        ).fetchall()

    def rr_leaderboard(self, guild_id: int) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM rr_players
            WHERE guild_id = ?
            ORDER BY (CASE WHEN elo > 0 THEN elo ELSE current_tier_id * 100 + current_rr END) DESC,
                     riot_name COLLATE NOCASE ASC
            """,
            (guild_id,),
        ).fetchall()

    def rr_update_identity(self, puuid: str, riot_name: str, riot_tag: str) -> None:
        self.conn.execute(
            "UPDATE rr_players SET riot_name = ?, riot_tag = ? WHERE puuid = ?",
            (riot_name, riot_tag, puuid),
        )
        self.conn.commit()

    def rr_link_discord(self, puuid: str, discord_id: Optional[int]) -> None:
        self.conn.execute(
            "UPDATE rr_players SET discord_id = ? WHERE puuid = ?", (discord_id, puuid)
        )
        self.conn.commit()

    def rr_update_state(self, puuid: str, tier_id, tier_name, rr, elo, last_match_id) -> None:
        self.conn.execute(
            """
            UPDATE rr_players
            SET current_tier_id = COALESCE(?, current_tier_id),
                current_tier_name = COALESCE(?, current_tier_name),
                current_rr = COALESCE(?, current_rr),
                elo = COALESCE(?, elo),
                last_match_id = COALESCE(?, last_match_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE puuid = ?
            """,
            (tier_id, tier_name, rr, elo, last_match_id, puuid),
        )
        self.conn.commit()

    def rr_update_peak(self, puuid: str, tier_id, tier_name) -> None:
        """Met à jour le peak rank uniquement s'il est plus haut que celui déjà enregistré."""
        if tier_id is None:
            return
        self.conn.execute(
            """
            UPDATE rr_players
            SET peak_tier_id = ?, peak_tier_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE puuid = ? AND ? >= peak_tier_id
            """,
            (tier_id, tier_name, puuid, tier_id),
        )
        self.conn.commit()

    def rr_add_history(self, puuid: str, guild_id: int, match_id: str, rr_change: int,
                       rr_after, tier_name, map_name, agent, kills, deaths, assists,
                       rounds_won, rounds_lost, played_at: str) -> bool:
        """Retourne True si la partie est nouvelle (donc à annoncer)."""
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO rr_history (
                puuid, guild_id, match_id, rr_change, rr_after, tier_name, map_name,
                agent, kills, deaths, assists, rounds_won, rounds_lost, played_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (puuid, guild_id, match_id, rr_change, rr_after, tier_name, map_name,
             agent, kills, deaths, assists, rounds_won, rounds_lost, played_at),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def rr_player_history(self, puuid: str, limit: int = 10) -> List[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM rr_history WHERE puuid = ? ORDER BY played_at DESC LIMIT ?",
            (puuid, limit),
        ).fetchall()

    def rr_daily_stats(self, guild_id: int, since_iso: str) -> List[dict]:
        rows = self.conn.execute(
            """
            SELECT h.puuid AS puuid,
                   p.riot_name AS name,
                   SUM(h.rr_change) AS total,
                   COUNT(*) AS games,
                   SUM(CASE WHEN h.rr_change > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN h.rr_change < 0 THEN 1 ELSE 0 END) AS losses
            FROM rr_history h
            JOIN rr_players p ON p.puuid = h.puuid
            WHERE h.guild_id = ? AND h.played_at >= ?
            GROUP BY h.puuid
            ORDER BY total DESC
            """,
            (guild_id, since_iso),
        ).fetchall()
        return [dict(row) for row in rows]

    def rr_period_stats(self, guild_id: int, puuid: str, since_iso: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT SUM(rr_change) AS total,
                   COUNT(*) AS games,
                   SUM(CASE WHEN rr_change > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN rr_change < 0 THEN 1 ELSE 0 END) AS losses
            FROM rr_history
            WHERE guild_id = ? AND puuid = ? AND played_at >= ?
            """,
            (guild_id, puuid, since_iso),
        ).fetchone()


db = Database(DB_PATH)


@dataclass
class MatchState:
    prep_channel_id: int
    started_by_id: int
    ui_message_id: int
    party_code: str
    map_name: str
    attack_ids: List[int]
    defense_ids: List[int]
    map_yes: int
    map_no: int
    map_locked: bool
    map_voters: Dict[str, str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "MatchState":
        raw_voters = row["map_voters"] if "map_voters" in row.keys() else "{}"
        return cls(
            prep_channel_id=row["prep_channel_id"],
            started_by_id=row["started_by_id"],
            ui_message_id=row["ui_message_id"],
            party_code=row["party_code"],
            map_name=row["map_name"],
            attack_ids=json.loads(row["attack_ids"]),
            defense_ids=json.loads(row["defense_ids"]),
            map_yes=row["map_yes"] if "map_yes" in row.keys() else 0,
            map_no=row["map_no"] if "map_no" in row.keys() else 0,
            map_locked=bool(row["map_locked"]) if "map_locked" in row.keys() else False,
            map_voters=json.loads(raw_voters or "{}"),
        )


# ===================== IMAGE GENERATION =====================
_WELCOME_BG_CACHE: Optional[bytes] = None


async def generate_welcome_card(member: discord.Member) -> io.BytesIO:
    # 1. Base Background (Image Demandée)
    bg_url = "https://cdn.discordapp.com/attachments/1460123533828030699/1533549541972902030/a0e0ef14cf5902013f6c12e94e79e45f.png?ex=6a70e4ce&is=6a6f934e&hm=3c2e90efd79c22aff07b073e636d21525ef46595a6d82f2df5bf57d2505527e7&"
    global _WELCOME_BG_CACHE
    try:
        if _WELCOME_BG_CACHE is None:
            async with aiohttp.ClientSession() as s:
                async with s.get(bg_url, headers={"User-Agent": "Mozilla/5.0"}) as r:
                    _WELCOME_BG_CACHE = await r.read()
        bg = Image.open(io.BytesIO(_WELCOME_BG_CACHE)).convert("RGBA")
        bg = bg.resize((800, 400))  # Format bannière large
    except Exception:
        # Fallback si l'image ne charge pas
        bg = Image.new("RGBA", (800, 400), (20, 22, 28, 255))
        
    # 2. Avatar Processing (Image très grande, parfaitement centrée)
    avatar_size = 300 # Très grande taille
    avatar_bytes = await member.display_avatar.replace(size=512, format="png").read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((avatar_size, avatar_size))

    # Masque circulaire
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    
    circular_avatar = Image.new("RGBA", (avatar_size, avatar_size))
    circular_avatar.paste(avatar, (0, 0), mask)

    # Création du contour (Border rouge, +16px plus grand que l'avatar)
    border_size = avatar_size + 16
    border_mask = Image.new("RGBA", (border_size, border_size), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border_mask)
    border_draw.ellipse((0, 0, border_size, border_size), fill=(231, 76, 60, 255))
    
    # Centrage parfait sur le canvas de 800x400
    avatar_x = (800 - avatar_size) // 2
    avatar_y = (400 - avatar_size) // 2
    
    border_x = (800 - border_size) // 2
    border_y = (400 - border_size) // 2
    
    # Collage sur le fond
    bg.paste(border_mask, (border_x, border_y), border_mask)
    bg.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

    # Sauvegarde
    buffer = io.BytesIO()
    bg.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# ===================== HELPERS =====================
def tier_emoji(rank_name: str) -> str:
    tier = rank_name.split()[0]
    return RANK_TIER_EMOJI.get(tier, "🎯")


def rank_select_emoji(guild: Optional[discord.Guild], rank_name: str):
    if guild is not None:
        emoji_name = RANK_EMOJI_BY_NAME.get(rank_name)
        if emoji_name:
            custom_emoji = discord.utils.get(guild.emojis, name=emoji_name)
            if custom_emoji is not None:
                return custom_emoji
    return tier_emoji(rank_name)


def find_rank_role_name(role: discord.Role) -> Optional[str]:
    """Retourne le nom de rang correspondant à un rôle, même s'il est décoré."""
    role_slug = slug(role.name)
    best = None
    for rank_name, _ in RANK_OPTIONS:
        rank_slug = slug(rank_name)
        if role_slug == rank_slug or rank_slug in role_slug.split():
            return rank_name
        if rank_slug in role_slug and (best is None or len(rank_name) > len(best)):
            best = rank_name
    return best


def rank_value_for_member(member: discord.Member) -> int:
    stored = db.get_player_rank(member.id)
    best = 0
    if stored and stored in RANK_VALUE_BY_NAME:
        best = RANK_VALUE_BY_NAME[stored]
    for role in member.roles:
        if role.name in RANK_VALUE_BY_NAME:
            best = max(best, RANK_VALUE_BY_NAME[role.name])
    return best


def is_prep_voice(channel: Optional[discord.abc.GuildChannel]) -> bool:
    return isinstance(channel, discord.VoiceChannel) and slug(channel.name) in {slug(n) for n in PREP_CHANNEL_NAMES}


def find_category(guild: discord.Guild, name: str) -> Optional[discord.CategoryChannel]:
    return discord.utils.find(
        lambda c: isinstance(c, discord.CategoryChannel) and slug(c.name) == slug(name),
        guild.categories,
    )


def find_text_channel(guild: discord.Guild, aliases: List[str], *, category: Optional[discord.CategoryChannel] = None) -> Optional[discord.TextChannel]:
    wanted = {slug(name) for name in aliases if name}
    channels = category.text_channels if category is not None else guild.text_channels
    return discord.utils.find(
        lambda c: isinstance(c, discord.TextChannel) and slug(c.name) in wanted,
        channels,
    )


def get_verify_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    aliases = [VERIFY_CHANNEL_NAME, *VERIFY_CHANNEL_ALIASES]
    return find_text_channel(guild, aliases)


def get_rank_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    category = find_category(guild, RANK_CATEGORY_NAME)
    return find_text_channel(guild, [RANK_CHANNEL_NAME, "choisi-ton-rank"], category=category) or find_text_channel(guild, [RANK_CHANNEL_NAME])


def get_welcome_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    home_category = find_category(guild, HOME_CATEGORY_NAME)
    aliases = [WELCOME_CHANNEL_NAME, "kaminarimon", "bienvenue", "welcome"]
    return find_text_channel(guild, aliases, category=home_category) or find_text_channel(guild, aliases)


def is_admin(member: discord.Member) -> bool:
    return member.guild_permissions.administrator


def has_orga_access(member: discord.Member) -> bool:
    return is_admin(member) or any(r.name == ORGA_ROLE for r in member.roles)


def is_verified_member(member: discord.Member) -> bool:
    return any(r.name == PLAYER_ROLE for r in member.roles) or has_orga_access(member)


def is_custom_voice(channel: Optional[discord.abc.GuildChannel]) -> bool:
    return isinstance(channel, discord.VoiceChannel) and db.get_custom_voice_owner(channel.id) is not None


def is_create_voice_trigger(channel: Optional[discord.abc.GuildChannel]) -> bool:
    if not isinstance(channel, discord.VoiceChannel): return False
    return slug(channel.name) in {slug(n) for n in CREATE_VOICE_TRIGGER_ALIASES}


def custom_voice_locked(channel: discord.VoiceChannel) -> bool:
    player_role = discord.utils.get(channel.guild.roles, name=PLAYER_ROLE)
    if player_role is None:
        return False
    overwrite = channel.overwrites_for(player_role)
    return overwrite.connect is False


def can_manage_custom_voice(member: discord.Member, channel: Optional[discord.VoiceChannel]) -> bool:
    if not isinstance(channel, discord.VoiceChannel):
        return False
    owner_id = db.get_custom_voice_owner(channel.id)
    return owner_id is not None and (member.id == owner_id or has_orga_access(member))


async def ensure_role(guild: discord.Guild, role_name: str, *, color: Optional[discord.Color] = None) -> discord.Role:
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name, color=color or discord.Color.default(), reason="PP setup")
    return role


async def ensure_core_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
    player_role = await ensure_role(guild, PLAYER_ROLE)
    roles = {
        "non_verified": await ensure_role(guild, NON_VERIFIED_ROLE),
        "member": player_role,
        "orga": await ensure_role(guild, ORGA_ROLE),
        "attack": await ensure_role(guild, TEAM_ATTACK_ROLE),
        "defense": await ensure_role(guild, TEAM_DEFENSE_ROLE),
        "player": player_role,
    }
    if MEMBER_ROLE != PLAYER_ROLE:
        await ensure_role(guild, MEMBER_ROLE)
    for rank_name, _ in RANK_OPTIONS:
        await ensure_role(guild, rank_name)
    return roles

async def sync_existing_membership_roles(guild: discord.Guild) -> None:
    roles = await ensure_core_roles(guild)
    verified_role = roles["player"]
    non_verified_role = roles["non_verified"]

    for member in guild.members:
        if member.bot:
            continue
        if non_verified_role in member.roles:
            continue
        if verified_role in member.roles:
            continue
        try:
            await member.add_roles(verified_role, reason="PP setup membership sync")
        except discord.Forbidden:
            pass

async def _safe_set_permissions(channel: discord.abc.GuildChannel, target: discord.abc.Snowflake, **kwargs) -> None:
    for tentative in range(3):
        try:
            await channel.set_permissions(target, reason="PP access setup", **kwargs)
            return
        except discord.Forbidden:
            return
        except discord.HTTPException as exc:
            if exc.status == 429 and tentative < 2:
                await asyncio.sleep(2 * (tentative + 1))
                continue
            print(f"[PERMS] Échec sur {getattr(channel, 'name', channel)} : {exc}")
            return


async def _configure_text_channel(
    channel: discord.TextChannel,
    *,
    default_role: discord.Role,
    non_verified: discord.Role,
    member: discord.Role,
    orga: discord.Role,
    member_can_write: bool,
    visible_to_member: bool = True,
    visible_to_orga: bool = True,
) -> None:
    await _safe_set_permissions(channel, default_role, view_channel=False, send_messages=False, add_reactions=False)
    await _safe_set_permissions(channel, non_verified, view_channel=False, send_messages=False, add_reactions=False)
    await _safe_set_permissions(
        channel,
        member,
        view_channel=visible_to_member,
        send_messages=member_can_write if visible_to_member else False,
        add_reactions=member_can_write if visible_to_member else False,
        read_message_history=visible_to_member,
        use_application_commands=visible_to_member,
    )
    await _safe_set_permissions(
        channel,
        orga,
        view_channel=visible_to_orga,
        send_messages=visible_to_orga,
        add_reactions=visible_to_orga,
        read_message_history=visible_to_orga,
        use_application_commands=visible_to_orga,
        manage_messages=visible_to_orga,
    )


async def _configure_voice_channel(
    channel: discord.VoiceChannel,
    *,
    default_role: discord.Role,
    non_verified: discord.Role,
    member: discord.Role,
    orga: discord.Role,
    member_can_connect: bool = True,
    orga_can_connect: bool = True,
) -> None:
    await _safe_set_permissions(channel, default_role, view_channel=False, connect=False, send_messages=False)
    await _safe_set_permissions(channel, non_verified, view_channel=False, connect=False, send_messages=False)
    await _safe_set_permissions(
        channel,
        member,
        view_channel=True,
        connect=member_can_connect,
        speak=member_can_connect,
        stream=member_can_connect,
        use_voice_activation=member_can_connect,
        send_messages=True,
        read_message_history=True,
        use_application_commands=True,
    )
    await _safe_set_permissions(
        channel,
        orga,
        view_channel=True,
        connect=orga_can_connect,
        speak=orga_can_connect,
        stream=orga_can_connect,
        use_voice_activation=orga_can_connect,
        send_messages=True,
        read_message_history=True,
        use_application_commands=True,
        move_members=True,
        mute_members=True,
        deafen_members=True,
    )


async def set_verification_permissions(guild: discord.Guild) -> None:
    roles = await ensure_core_roles(guild)
    await sync_existing_membership_roles(guild)

    default_role = guild.default_role
    non_verified = roles["non_verified"]
    member = roles["member"]
    orga = roles["orga"]

    try:
        perms = non_verified.permissions
        perms.update(read_messages=False, send_messages=False, connect=False)
        await non_verified.edit(permissions=perms, reason="PP Setup: Default block for non verified")
    except discord.Forbidden:
        pass

    verify_channel = get_verify_channel(guild)
    rank_channel = get_rank_channel(guild)
    party_category = find_category(guild, PARTY_CATEGORY_NAME)
    orga_channel = find_text_channel(guild, [ORGA_TEXT_CHANNEL_NAME, "orga pp"], category=party_category)

    # Configuration du salon de vérification (Anti-Robot)
    if verify_channel is not None:
        await _safe_set_permissions(verify_channel, default_role, view_channel=False, send_messages=False, add_reactions=False)
        await _safe_set_permissions(verify_channel, member, view_channel=False, send_messages=False, add_reactions=False)
        await _safe_set_permissions(
            verify_channel,
            non_verified,
            view_channel=True,
            send_messages=False,
            add_reactions=False,
            read_message_history=True,
            use_application_commands=True,
        )
        await _safe_set_permissions(
            verify_channel,
            orga,
            view_channel=True,
            send_messages=True,
            add_reactions=True,
            read_message_history=True,
            use_application_commands=True,
            manage_messages=True,
        )

    # Configuration du salon de choix de rank
    if rank_channel is not None:
        await _safe_set_permissions(rank_channel, default_role, view_channel=False, send_messages=False, add_reactions=False)
        await _safe_set_permissions(rank_channel, non_verified, view_channel=False, send_messages=False, add_reactions=False)
        await _safe_set_permissions(
            rank_channel,
            member,
            view_channel=True,
            send_messages=False,
            add_reactions=False,
            read_message_history=True,
            use_application_commands=True,
        )
        await _safe_set_permissions(
            rank_channel,
            orga,
            view_channel=True,
            send_messages=True,
            add_reactions=True,
            read_message_history=True,
            use_application_commands=True,
            manage_messages=True,
        )

    if orga_channel is not None:
        await _configure_text_channel(
            orga_channel,
            default_role=default_role,
            non_verified=non_verified,
            member=member,
            orga=orga,
            member_can_write=False,
            visible_to_member=False,
            visible_to_orga=True,
        )

    for channel_name in PREP_CHANNEL_NAMES:
        prep = discord.utils.find(
            lambda c: isinstance(c, discord.VoiceChannel) and slug(c.name) == slug(channel_name),
            guild.channels,
        )
        if prep is not None:
            await _configure_voice_channel(
                prep,
                default_role=default_role,
                non_verified=non_verified,
                member=member,
                orga=orga,
            )


async def set_custom_voice_permissions(channel: discord.VoiceChannel, *, owner: discord.Member, locked: bool = False) -> None:
    roles = await ensure_core_roles(channel.guild)
    player = roles["player"]
    orga = roles["orga"]
    await _safe_set_permissions(channel, channel.guild.default_role, view_channel=False, connect=False, send_messages=False)
    await _safe_set_permissions(channel, roles["non_verified"], view_channel=False, connect=False, send_messages=False)
    await _safe_set_permissions(
        channel,
        player,
        view_channel=True,
        connect=not locked,
        speak=True,
        stream=True,
        use_voice_activation=True,
        send_messages=True,
        read_message_history=True,
        use_application_commands=True,
    )
    await _safe_set_permissions(
        channel,
        orga,
        view_channel=True,
        connect=True,
        speak=True,
        stream=True,
        use_voice_activation=True,
        send_messages=True,
        read_message_history=True,
        use_application_commands=True,
        move_members=True,
        manage_channels=True,
        mute_members=True,
        deafen_members=True,
    )
    await _safe_set_permissions(
        channel,
        owner,
        view_channel=True,
        connect=True,
        speak=True,
        stream=True,
        use_voice_activation=True,
        send_messages=True,
        read_message_history=True,
        use_application_commands=True,
        move_members=True,
        manage_channels=True,
        priority_speaker=True,
    )


async def create_custom_voice_channel(guild: discord.Guild, owner: discord.Member, name: str, user_limit: int = 0) -> discord.VoiceChannel:
    category = guild.get_channel(CUSTOM_VOICE_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel):
        category = find_category(guild, CUSTOM_VOICE_CATEGORY_NAME) or find_category(guild, ARTISANS_CATEGORY_NAME)
    channel = await guild.create_voice_channel(name=name, category=category, user_limit=max(0, min(99, user_limit)))
    db.register_custom_voice(channel.id, owner.id)
    await set_custom_voice_permissions(channel, owner=owner, locked=False)
    try:
        await owner.move_to(channel)
    except (discord.Forbidden, discord.HTTPException):
        pass
    return channel


async def cleanup_custom_voice_if_empty(channel: discord.VoiceChannel) -> None:
    if is_custom_voice(channel) and len(channel.members) == 0:
        db.delete_custom_voice(channel.id)
        try:
            await channel.delete(reason="Temporary custom voice empty")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def _build_custom_voice_panel_embed(channel: discord.VoiceChannel) -> discord.Embed:
    owner_id = db.get_custom_voice_owner(channel.id)
    owner = channel.guild.get_member(owner_id) if owner_id else None
    embed = discord.Embed(
        title=f"🎤 {channel.name}",
        description=(
            "Bienvenue dans ton salon privé.\n"
            "Utilise les boutons ci-dessous pour **verrouiller**, **renommer**, "
            "**changer les slots** ou **expulser** quelqu’un de la voc."
        ),
        color=discord.Color.dark_gold(),
    )
    embed.add_field(name="Propriétaire", value=owner.mention if owner else "Inconnu", inline=True)
    embed.add_field(name="État", value="🔒 Verrouillé" if custom_voice_locked(channel) else "🔓 Ouvert", inline=True)
    embed.add_field(name="Slots", value=str(channel.user_limit) if channel.user_limit else "∞", inline=True)
    embed.set_footer(text="Réservé au propriétaire du salon, Orga PP ou admin.")
    return embed


async def ensure_custom_voice_panel(channel: discord.VoiceChannel) -> None:
    try:
        async for msg in channel.history(limit=30):
            if msg.author == channel.guild.me and msg.components:
                return
    except (discord.Forbidden, discord.HTTPException):
        return

    try:
        msg = await channel.send(embed=await _build_custom_voice_panel_embed(channel), view=CustomVoiceControlView())
        try:
            await msg.pin()
        except (discord.Forbidden, discord.HTTPException):
            pass
    except (discord.Forbidden, discord.HTTPException):
        pass


async def refresh_custom_voice_panel(channel: discord.VoiceChannel) -> None:
    try:
        async for msg in channel.history(limit=30):
            if msg.author == channel.guild.me and msg.components:
                await msg.edit(embed=await _build_custom_voice_panel_embed(channel), view=CustomVoiceControlView())
                return
    except (discord.Forbidden, discord.HTTPException):
        return


async def apply_rank(member: discord.Member, rank_name: str) -> None:
    roles = await ensure_core_roles(member.guild)
    # Récupère le rôle custom du rang (même décoré), et le crée avec sa couleur s'il n'existe pas.
    rank_role = await ensure_rank_role(member.guild, rank_name)
    if rank_role is None:
        rank_role = await ensure_role(member.guild, rank_name)

    to_remove = [
        r for r in member.roles
        if (r.name in RANK_VALUE_BY_NAME or find_rank_role_name(r) is not None or r == roles["non_verified"])
        and r != rank_role
    ]
    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason="PP rank verification")
        except discord.Forbidden:
            pass

    add_roles = [rank_role, roles["player"]]
    missing = [r for r in add_roles if r not in member.roles]
    if missing:
        try:
            await member.add_roles(*missing, reason="PP rank verification")
        except discord.Forbidden:
            pass

    db.upsert_player_rank(member.id, rank_name)


async def clear_team_roles(guild: discord.Guild, members: Optional[List[discord.Member]] = None) -> None:
    attack_role = discord.utils.get(guild.roles, name=TEAM_ATTACK_ROLE)
    defense_role = discord.utils.get(guild.roles, name=TEAM_DEFENSE_ROLE)
    if attack_role is None or defense_role is None:
        return

    targets = members or list(guild.members)
    for member in targets:
        to_remove = [r for r in (attack_role, defense_role) if r in member.roles]
        if to_remove:
            try:
                await member.remove_roles(*to_remove, reason="PP team reset")
            except discord.Forbidden:
                pass


async def apply_team_roles(guild: discord.Guild, attack: List[discord.Member], defense: List[discord.Member]) -> None:
    attack_role = discord.utils.get(guild.roles, name=TEAM_ATTACK_ROLE)
    defense_role = discord.utils.get(guild.roles, name=TEAM_DEFENSE_ROLE)
    if attack_role is None or defense_role is None:
        return

    await clear_team_roles(guild, attack + defense)
    for member in attack:
        try:
            await member.add_roles(attack_role, reason="PP teams")
        except discord.Forbidden:
            pass
    for member in defense:
        try:
            await member.add_roles(defense_role, reason="PP teams")
        except discord.Forbidden:
            pass


async def seed_existing_prep_members(guilds: List[discord.Guild]) -> None:
    for guild in guilds:
        for channel in guild.voice_channels:
            if not is_prep_voice(channel):
                continue
            for member in channel.members:
                if member.bot:
                    continue
                remember_member_in_prep(channel, member)


def remember_member_in_prep(channel: discord.VoiceChannel, member: discord.Member) -> None:
    PREP_JOIN_ORDER.setdefault(channel.id, {})[member.id] = PREP_JOIN_ORDER.get(channel.id, {}).get(member.id, next_join_sequence())


def forget_member_from_prep(channel: discord.VoiceChannel, member: discord.Member) -> None:
    PREP_JOIN_ORDER.get(channel.id, {}).pop(member.id, None)


def ordered_prep_members(channel: discord.VoiceChannel) -> List[discord.Member]:
    order_map = PREP_JOIN_ORDER.setdefault(channel.id, {})
    members = [m for m in channel.members if not m.bot]
    for member in members:
        if member.id not in order_map:
            order_map[member.id] = next_join_sequence()
    return sorted(members, key=lambda m: (order_map.get(m.id, 10**12), m.display_name.lower()))


def _effective_player_skill(member: discord.Member) -> float:
    raw = float(max(1, rank_value_for_member(member)))
    return (raw ** 1.12) + (22.0 * math.log1p(raw)) + (8.0 * math.sqrt(raw))


def _team_balance_cost(team_a: List[discord.Member], team_b: List[discord.Member]) -> float:
    skills_a = sorted((_effective_player_skill(m) for m in team_a), reverse=True)
    skills_b = sorted((_effective_player_skill(m) for m in team_b), reverse=True)

    sum_a, sum_b = sum(skills_a), sum(skills_b)
    mean_a, mean_b = statistics.fmean(skills_a), statistics.fmean(skills_b)
    stdev_a = statistics.pstdev(skills_a) if len(skills_a) > 1 else 0.0
    stdev_b = statistics.pstdev(skills_b) if len(skills_b) > 1 else 0.0

    top2_a, top2_b = sum(skills_a[:2]), sum(skills_b[:2])
    bot2_a, bot2_b = sum(skills_a[-2:]), sum(skills_b[-2:])
    median_a, median_b = statistics.median(skills_a), statistics.median(skills_b)

    return (
        abs(sum_a - sum_b)
        + 0.65 * abs(mean_a - mean_b)
        + 0.40 * abs(stdev_a - stdev_b)
        + 0.55 * abs(top2_a - top2_b)
        + 0.35 * abs(bot2_a - bot2_b)
        + 0.25 * abs(median_a - median_b)
    )


def split_balanced_teams(members: List[discord.Member]) -> Tuple[List[discord.Member], List[discord.Member]]:
    if len(members) != 10:
        scored = sorted(members, key=rank_value_for_member, reverse=True)
        midpoint = len(scored) // 2
        return scored[:midpoint], scored[midpoint:]

    indexed = list(enumerate(members))
    best_attack: List[discord.Member] = []
    best_defense: List[discord.Member] = []
    best_cost = float('inf')
    best_raw_gap = float('inf')

    for combo in combinations(indexed, 5):
        attack_indices = {idx for idx, _ in combo}
        attack = [member for idx, member in indexed if idx in attack_indices]
        defense = [member for idx, member in indexed if idx not in attack_indices]

        cost = _team_balance_cost(attack, defense)
        raw_gap = abs(sum(rank_value_for_member(m) for m in attack) - sum(rank_value_for_member(m) for m in defense))

        if cost < best_cost - 1e-9 or (abs(cost - best_cost) <= 1e-9 and raw_gap < best_raw_gap):
            best_cost = cost
            best_raw_gap = raw_gap
            best_attack = attack
            best_defense = defense

    return best_attack, best_defense


def get_associated_team_channels(prep_channel: discord.VoiceChannel) -> Tuple[Optional[discord.VoiceChannel], Optional[discord.VoiceChannel]]:
    category = prep_channel.category
    if category is None:
        return None, None

    voices = sorted(category.voice_channels, key=lambda c: c.position)
    try:
        prep_index = next(i for i, vc in enumerate(voices) if vc.id == prep_channel.id)
    except StopIteration:
        return None, None

    next_prep_index = len(voices)
    for i in range(prep_index + 1, len(voices)):
        if is_prep_voice(voices[i]):
            next_prep_index = i
            break

    attack = None
    defense = None
    for vc in voices[prep_index + 1:next_prep_index]:
        name = slug(vc.name)
        if "attaque" in name or "atk" in name or name.endswith("att"):
            attack = vc
        if "defense" in name or "def" in name:
            defense = vc
    return attack, defense


async def move_teams_if_possible(prep_channel: discord.VoiceChannel, attack: List[discord.Member], defense: List[discord.Member]) -> None:
    attack_vc, defense_vc = get_associated_team_channels(prep_channel)
    if attack_vc is None or defense_vc is None:
        return

    for member in attack:
        if member.voice and member.voice.channel and member.voice.channel.id == prep_channel.id:
            try:
                await member.move_to(attack_vc, reason="PP move attack")
            except discord.Forbidden:
                pass

    for member in defense:
        if member.voice and member.voice.channel and member.voice.channel.id == prep_channel.id:
            try:
                await member.move_to(defense_vc, reason="PP move defense")
            except discord.Forbidden:
                pass


def pick_map(exclude: Optional[str] = None) -> str:
    pool = [m for m in VALORANT_MAPS if m != exclude]
    return random.choice(pool or VALORANT_MAPS)


def map_image_url(map_name: str) -> Optional[str]:
    return MAP_IMAGE.get(map_name)


def load_match_state(prep_channel_id: int) -> Optional[MatchState]:
    row = db.get_active_match(prep_channel_id)
    return MatchState.from_row(row) if row else None


def is_match_controller(member: discord.Member, state: MatchState) -> bool:
    if member.guild_permissions.administrator:
        return True
    if member.id == state.started_by_id:
        return True
    return any(role.name == ORGA_ROLE for role in member.roles)


def format_mentions(members: List[discord.Member]) -> str:
    return "\n".join(member.mention for member in members) if members else "—"


def persist_match_state(state: MatchState) -> None:
    db.save_active_match(
        prep_channel_id=state.prep_channel_id,
        started_by_id=state.started_by_id,
        ui_message_id=state.ui_message_id,
        party_code=state.party_code,
        map_name=state.map_name,
        attack_ids=state.attack_ids,
        defense_ids=state.defense_ids,
        map_yes=state.map_yes,
        map_no=state.map_no,
        map_locked=state.map_locked,
        map_voters=state.map_voters,
    )


def build_match_embeds(guild: discord.Guild, state: MatchState) -> List[discord.Embed]:
    prep_channel = guild.get_channel(state.prep_channel_id)
    prep_name = prep_channel.name if isinstance(prep_channel, discord.VoiceChannel) else "Préparation"
    current_members = ordered_prep_members(prep_channel) if isinstance(prep_channel, discord.VoiceChannel) else []
    selected_members = current_members[:10]
    waiting_members = current_members[10:]

    status_line = "✅ Map acceptée" if state.map_locked else "🗳️ Vote map ouvert"
    if state.attack_ids and state.defense_ids:
        status_line = "🚀 PP lancée"

    header = discord.Embed(
        title=f"🗺️ Roulette map — {prep_name}",
        description=(
            f"**Party code :** `{state.party_code}`\n"
            f"**Map proposée :** **{state.map_name}**"
        ),
        color=discord.Color.green() if state.map_locked else discord.Color.blurple(),
    )

    image_url = map_image_url(state.map_name)
    if image_url:
        header.set_image(url=image_url)
    else:
        header.add_field(name="🖼️ Image de map", value="Image indisponible pour cette map.", inline=False)

    details = discord.Embed(
        description=(
            f"**Votes** — ✅ Oui: **{state.map_yes}/{VOTE_THRESHOLD_ACCEPT}** • ❌ Non: **{state.map_no}/{VOTE_THRESHOLD_REJECT}**\n"
            f"*(1 vote par personne)*\n\n"
            f"{status_line}"
        ),
        color=header.color,
    )

    details.add_field(
        name="👥 Joueurs détectés dans la voc",
        value=(
            f"**{len(current_members)}** joueur(s) présent(s).\n"
            f"La PP prend les **10 premiers arrivés** s'il y a plus de 10 joueurs."
        ),
        inline=False,
    )

    if selected_members:
        details.add_field(name="🎮 Top 10 pris en compte", value=format_mentions(selected_members), inline=False)
    if waiting_members:
        details.add_field(name="⏳ Hors top 10", value=format_mentions(waiting_members), inline=False)

    if state.attack_ids and state.defense_ids:
        attack_members = [guild.get_member(user_id) for user_id in state.attack_ids]
        defense_members = [guild.get_member(user_id) for user_id in state.defense_ids]
        attack_members = [m for m in attack_members if m is not None]
        defense_members = [m for m in defense_members if m is not None]
        details.add_field(name="⚔️ Attaque", value=format_mentions(attack_members), inline=True)
        details.add_field(name="🛡️ Défense", value=format_mentions(defense_members), inline=True)

    details.set_footer(text="Vote map • Lancer la PP • Annuler")
    return [header, details]


async def refresh_match_message(guild: discord.Guild, prep_channel_id: int) -> None:
    state = load_match_state(prep_channel_id)
    if state is None:
        return
    prep_channel = guild.get_channel(prep_channel_id)
    if not isinstance(prep_channel, discord.VoiceChannel):
        return
    try:
        message = await prep_channel.fetch_message(state.ui_message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return
    try:
        await message.edit(embeds=build_match_embeds(guild, state), view=PPMatchView())
    except (discord.Forbidden, discord.HTTPException):
        pass


# ===================== RR TRACKER : CONFIG =====================
HENRIK_API_KEY = os.getenv("HENRIK_API_KEY", "")
RR_CATEGORY_NAME = os.getenv("RR_CATEGORY_NAME", "🌸 ・ NAKAMISE DORI ・ 🌸")
RR_CHANNEL_NAME = os.getenv("RR_CHANNEL_NAME", "├🏆・rr-check")
RR_POLL_INTERVAL = int(os.getenv("RR_POLL_INTERVAL", "180"))
RR_DEFAULT_REGION = os.getenv("RR_DEFAULT_REGION", "eu")
RR_DEFAULT_PLATFORM = os.getenv("RR_DEFAULT_PLATFORM", "pc")
RR_PAGE_SIZE = int(os.getenv("RR_PAGE_SIZE", "10"))
RR_DAILY_RECAP_HOUR = int(os.getenv("RR_DAILY_RECAP_HOUR", "23"))
RR_TIMEZONE = os.getenv("RR_TIMEZONE", "Europe/Paris")

VALID_REGIONS = ["eu", "na", "ap", "kr", "latam", "br"]

# Le rôle Radiant reste attribué manuellement via ticket : on ne le sync pas automatiquement.
RR_AUTO_SYNC_ROLES = os.getenv("RR_AUTO_SYNC_ROLES", "1") == "1"

# Conversion des tiers renvoyés par l'API (anglais) vers les noms de rôles du serveur (français).
API_TIER_TO_FR = {
    "Iron": "Fer",
    "Bronze": "Bronze",
    "Silver": "Argent",
    "Gold": "Or",
    "Platinum": "Platine",
    "Diamond": "Diamant",
    "Ascendant": "Ascendant",
    "Immortal": "Immortal",
    "Immortalr": "Immortal",
    "Radiant": "Radiant",
}

RANK_TIER_COLOR = {
    "Fer": 0x5A5A5A,
    "Bronze": 0xA9744F,
    "Argent": 0xC0C0C0,
    "Or": 0xE6C200,
    "Platine": 0x3EB4C4,
    "Diamant": 0xB56EDC,
    "Ascendant": 0x2ECC71,
    "Immortal": 0xE0325B,
    "Radiant": 0xFFF176,
}

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def api_rank_to_fr(api_rank_name: Optional[str]) -> Optional[str]:
    """'Immortal 2' -> 'Immortal 2' ; 'Gold 3' -> 'Or 3' ; 'Unrated' -> None."""
    if not api_rank_name:
        return None
    parts = api_rank_name.strip().split()
    tier_en = parts[0]
    if tier_en in ("Unrated", "Unranked", "Unrankeds"):
        return None
    tier_fr = API_TIER_TO_FR.get(tier_en)
    if tier_fr is None:
        return None
    if tier_fr == "Radiant":
        return "Radiant"
    division = parts[1] if len(parts) > 1 else "1"
    candidate = f"{tier_fr} {division}"
    return candidate if candidate in RANK_VALUE_BY_NAME else None


def rank_display(tier_name: Optional[str], rr: Optional[int]) -> str:
    fr = api_rank_to_fr(tier_name) or (tier_name or "Non classé")
    if rr is None:
        return fr
    return f"{fr} | {rr}rr"


def compute_elo(tier_id: Optional[int], rr: Optional[int], elo: Optional[int]) -> int:
    if elo:
        return int(elo)
    return int(tier_id or 0) * 100 + int(rr or 0)


# ===================== RR TRACKER : API HENRIKDEV =====================
class ValorantAPIError(Exception):
    pass


class ValorantAPI:
    """Client de l'API communautaire HenrikDev (non officielle Riot)."""

    BASE = "https://api.henrikdev.xyz"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional["aiohttp.ClientSession"] = None
        self._lock = asyncio.Lock()

    async def session(self):
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    headers={"Authorization": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=20),
                )
            return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, path: str) -> dict:
        if not self.api_key:
            raise ValorantAPIError("Clé API HenrikDev manquante (HENRIK_API_KEY dans le .env).")
        session = await self.session()
        try:
            async with session.get(f"{self.BASE}{path}") as resp:
                try:
                    payload = await resp.json()
                except Exception:
                    payload = {}
                if resp.status == 401:
                    raise ValorantAPIError(
                        "Clé API HenrikDev refusée (401). Vérifie que HENRIK_API_KEY commence bien "
                        "par `HDEV-` et qu'elle est toujours active sur le Discord HenrikDev."
                    )
                if resp.status == 404:
                    raise ValorantAPIError("Joueur introuvable (vérifie le pseudo, le tag et la région).")
                if resp.status == 410:
                    raise ValorantAPIError(
                        f"Endpoint déprécié par HenrikDev : `{path}`. Le bot doit être mis à jour."
                    )
                if resp.status == 429:
                    retry = resp.headers.get("Retry-After", "?")
                    raise ValorantAPIError(
                        f"Limite de requêtes atteinte (429). Réessaie dans {retry}s, "
                        "ou augmente RR_POLL_INTERVAL."
                    )
                if resp.status == 403:
                    raise ValorantAPIError(
                        "Accès refusé (403) : soit maintenance côté Riot, soit protection anti-bot HenrikDev."
                    )
                if resp.status >= 400:
                    errors = payload.get("errors") or []
                    message = errors[0].get("message") if errors else f"Erreur API ({resp.status})"
                    raise ValorantAPIError(message)
                return payload
        except asyncio.TimeoutError:
            raise ValorantAPIError("L'API Valorant ne répond pas (timeout).")
        except aiohttp.ClientError as exc:
            raise ValorantAPIError(f"Erreur réseau vers l'API Valorant : {exc}")

    async def get_account(self, name: str, tag: str) -> dict:
        data = await self._get(f"/valorant/v2/account/{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}")
        return data.get("data") or {}

    async def get_account_by_puuid(self, puuid: str) -> dict:
        data = await self._get(f"/valorant/by-puuid/v2/account/{puuid}")
        return data.get("data") or {}

    async def get_mmr(self, region: str, puuid: str, platform: str = RR_DEFAULT_PLATFORM) -> dict:
        data = await self._get(f"/valorant/v3/by-puuid/mmr/{region}/{platform}/{puuid}")
        return data.get("data") or {}

    async def get_mmr_history(self, region: str, puuid: str, platform: str = RR_DEFAULT_PLATFORM) -> dict:
        data = await self._get(f"/valorant/v2/by-puuid/mmr-history/{region}/{platform}/{puuid}")
        return data.get("data") or {}

    async def get_matches(self, region: str, puuid: str, platform: str = RR_DEFAULT_PLATFORM,
                          mode: str = "competitive", size: int = 5) -> list:
        path = f"/valorant/v4/by-puuid/matches/{region}/{platform}/{puuid}?mode={mode}&size={size}"
        data = await self._get(path)
        return data.get("data") or []


valo_api = ValorantAPI(HENRIK_API_KEY)


# ===================== RR TRACKER : PARSING DES MATCHS =====================
def _extract_match_id(entry: dict) -> Optional[str]:
    for key in ("match_id", "matchid", "id"):
        if entry.get(key):
            return str(entry[key])
    meta = entry.get("metadata") or {}
    for key in ("match_id", "matchid"):
        if meta.get(key):
            return str(meta[key])
    return None


def _tier_from_entry(entry: dict) -> Tuple[Optional[int], Optional[str]]:
    tier = entry.get("tier")
    if isinstance(tier, dict):
        return tier.get("id"), tier.get("name")
    return entry.get("currenttier"), entry.get("currenttier_patched")


def _rr_from_entry(entry: dict) -> Tuple[Optional[int], Optional[int]]:
    """Retourne (rr_après, variation)."""
    rr = entry.get("rr")
    if rr is None:
        rr = entry.get("ranking_in_tier")
    change = entry.get("last_change")
    if change is None:
        change = entry.get("mmr_change_to_last_game")
    if change is None:
        change = entry.get("last_mmr_change")
    return rr, change


def _map_name_from_entry(entry: dict) -> Optional[str]:
    map_field = entry.get("map")
    if isinstance(map_field, dict):
        return map_field.get("name")
    if isinstance(map_field, str):
        return map_field
    meta = entry.get("metadata") or {}
    map_field = meta.get("map")
    if isinstance(map_field, dict):
        return map_field.get("name")
    if isinstance(map_field, str):
        return map_field
    return None


def _parse_match_date(entry: dict) -> Optional[datetime]:
    raw = entry.get("date") or entry.get("started_at") or (entry.get("metadata") or {}).get("started_at")
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    raw = entry.get("date_raw")
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    return None


def _find_match_details(matches: List[dict], match_id: str, puuid: str) -> dict:
    """Extrait score, agent et KDA d'une partie depuis la matchlist v4."""
    details: Dict[str, object] = {}
    target = None
    for match in matches:
        if _extract_match_id(match) == match_id:
            target = match
            break
    if target is None:
        return details

    details["map_name"] = _map_name_from_entry(target)

    players = target.get("players")
    if isinstance(players, dict):
        players = players.get("all_players") or []
    players = players or []

    me = None
    for player in players:
        if str(player.get("puuid", "")).lower() == puuid.lower():
            me = player
            break
    if me is None:
        return details

    agent = me.get("agent")
    if isinstance(agent, dict):
        details["agent_name"] = agent.get("name")
        details["agent_id"] = agent.get("id")
    else:
        details["agent_name"] = me.get("character") or agent
        details["agent_id"] = me.get("character_id")

    stats = me.get("stats") if isinstance(me.get("stats"), dict) else me
    details["kills"] = stats.get("kills")
    details["deaths"] = stats.get("deaths")
    details["assists"] = stats.get("assists")

    my_team = me.get("team_id") or me.get("team")
    teams = target.get("teams")
    won: Optional[bool] = None
    rounds_won = rounds_lost = None

    if isinstance(teams, list):
        for team in teams:
            team_id = team.get("team_id") or team.get("team")
            rounds = team.get("rounds") or {}
            if isinstance(rounds, dict):
                r_won = rounds.get("won")
                r_lost = rounds.get("lost")
            else:
                r_won = team.get("rounds_won")
                r_lost = team.get("rounds_lost")
            if str(team_id).lower() == str(my_team).lower():
                won = team.get("won")
                rounds_won, rounds_lost = r_won, r_lost
    elif isinstance(teams, dict):
        red = teams.get("red") or {}
        blue = teams.get("blue") or {}
        red_score = red.get("rounds_won", red) if isinstance(red, dict) else red
        blue_score = blue.get("rounds_won", blue) if isinstance(blue, dict) else blue
        if isinstance(red_score, dict):
            red_score = red_score.get("won")
        if isinstance(blue_score, dict):
            blue_score = blue_score.get("won")
        if str(my_team).lower() == "red":
            rounds_won, rounds_lost = red_score, blue_score
        else:
            rounds_won, rounds_lost = blue_score, red_score
        if rounds_won is not None and rounds_lost is not None:
            won = rounds_won > rounds_lost

    details["rounds_won"] = rounds_won
    details["rounds_lost"] = rounds_lost
    details["won"] = won
    return details


def agent_icon_url(agent_id: Optional[str]) -> Optional[str]:
    if not agent_id:
        return None
    return f"https://media.valorant-api.com/agents/{agent_id}/displayicon.png"


# ===================== RR TRACKER : RÔLES DE RANG =====================
def find_rank_role(guild: discord.Guild, rank_name: str) -> Optional[discord.Role]:
    """Retrouve le rôle d'un rang, même si son nom est décoré (ex: '👑・Immortal 2')."""
    exact = discord.utils.get(guild.roles, name=rank_name)
    if exact is not None:
        return exact
    wanted = slug(rank_name)
    for role in guild.roles:
        if slug(role.name) == wanted:
            return role
    # Rôle décoré, ex: "👑・Immortal 2" ou "『 Or 3 』"
    for role in guild.roles:
        if find_rank_role_name(role) == rank_name:
            return role
    return None


async def ensure_rank_role(guild: discord.Guild, rank_name: str) -> Optional[discord.Role]:
    """Retourne le rôle custom du rang, et le crée avec la bonne couleur s'il n'existe pas."""
    role = find_rank_role(guild, rank_name)
    if role is not None:
        return role
    tier = rank_name.split()[0]
    color = discord.Color(RANK_TIER_COLOR.get(tier, 0x99AAB5))
    try:
        return await guild.create_role(
            name=rank_name,
            color=color,
            hoist=False,
            mentionable=False,
            reason="Création automatique du rôle de rang",
        )
    except discord.Forbidden:
        print(f"[RR] Permissions insuffisantes pour créer le rôle {rank_name}")
        return None
    except discord.HTTPException as exc:
        print(f"[RR] Impossible de créer le rôle {rank_name} : {exc}")
        return None


async def sync_rank_role_from_api(member: discord.Member, api_tier_name: Optional[str]) -> Optional[str]:
    """Applique le rôle de rang correspondant au rang réel détecté via l'API."""
    if not RR_AUTO_SYNC_ROLES:
        return None
    fr_rank = api_rank_to_fr(api_tier_name)
    if fr_rank is None or fr_rank == "Radiant":
        return None
    current = [r.name for r in member.roles if r.name in RANK_VALUE_BY_NAME]
    if fr_rank in current:
        return None
    await apply_rank(member, fr_rank)
    return fr_rank


# ===================== RR TRACKER : SALON =====================
def get_rr_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    category = find_category(guild, RR_CATEGORY_NAME)
    channel = find_text_channel(guild, [RR_CHANNEL_NAME, "rr-check", "rr check"], category=category)
    if channel is None:
        channel = find_text_channel(guild, [RR_CHANNEL_NAME, "rr-check", "rr check"])
    return channel


async def ensure_rr_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Crée la catégorie NAKAMISE DORI et le salon rr-check si besoin."""
    category = find_category(guild, RR_CATEGORY_NAME)
    if category is None:
        try:
            category = await guild.create_category(RR_CATEGORY_NAME, reason="Setup RR tracker")
        except discord.Forbidden:
            return None

    channel = get_rr_channel(guild)
    if channel is None:
        try:
            channel = await guild.create_text_channel(
                name=RR_CHANNEL_NAME,
                category=category,
                topic="Suivi automatique des gains et pertes de RR des joueurs du serveur.",
                reason="Setup RR tracker",
            )
        except discord.Forbidden:
            return None
    elif channel.category != category:
        try:
            await channel.edit(category=category, reason="Rangement du salon RR")
        except (discord.Forbidden, discord.HTTPException):
            pass

    roles = await ensure_core_roles(guild)
    await _safe_set_permissions(channel, guild.default_role, view_channel=False)
    await _safe_set_permissions(channel, roles["non_verified"], view_channel=False)
    await _safe_set_permissions(
        channel, roles["member"],
        view_channel=True, send_messages=False, read_message_history=True, add_reactions=True,
    )
    await _safe_set_permissions(
        channel, roles["orga"],
        view_channel=True, send_messages=True, read_message_history=True, manage_messages=True,
    )
    return channel


# ===================== RR TRACKER : EMBEDS =====================
def build_match_embed(guild: discord.Guild, row: sqlite3.Row, entry: dict, details: dict,
                       rr_change: int, rr_after: Optional[int], tier_name: Optional[str]) -> discord.Embed:
    won = details.get("won")
    rounds_won = details.get("rounds_won")
    rounds_lost = details.get("rounds_lost")

    if won is None and rounds_won is not None and rounds_lost is not None:
        won = rounds_won > rounds_lost
    if won is None:
        won = rr_change > 0

    score_txt = f"{rounds_won} — {rounds_lost}" if rounds_won is not None else "—"

    if rounds_won is not None and rounds_lost is not None and rounds_won == rounds_lost:
        bandeau, couleur = "🟰  ÉGALITÉ", discord.Color(0x95A5A6)
    elif won:
        bandeau, couleur = "🟢  VICTOIRE", discord.Color(0x2ECC71)
    else:
        bandeau, couleur = "🔴  DÉFAITE", discord.Color(0xE74C3C)

    signe = "+" if rr_change >= 0 else ""
    emoji_rang = _rank_emoji_str(guild, tier_name)
    rang_txt = api_rank_to_fr(tier_name) or (tier_name or "Non classé")

    # Barre de progression dans le palier (0-100 RR)
    barre = ""
    if rr_after is not None:
        plein = max(0, min(10, round(rr_after / 10)))
        remplies = "▰" * plein
        vides = "▱" * (10 - plein)
        barre = f"\n`{remplies}{vides}`  {rr_after}/100 RR"

    embed = discord.Embed(
        title=bandeau,
        description=(
            f"### {row['riot_name']}  `{signe}{rr_change} RR`\n"
            f"{emoji_rang} **{rang_txt}**{barre}"
        ),
        color=couleur,
    )

    kills = details.get("kills")
    deaths = details.get("deaths")
    assists = details.get("assists")
    if kills is not None:
        kd = f"{kills / deaths:.2f}" if deaths else "∞"
        embed.add_field(name="K / D / A", value=f"`{kills}/{deaths}/{assists}`\nK/D **{kd}**", inline=True)
    embed.add_field(name="Score", value=f"`{score_txt}`", inline=True)

    map_name = details.get("map_name") or _map_name_from_entry(entry)
    agent_name = details.get("agent_name")
    embed.add_field(
        name="Partie",
        value=f"{map_name or 'Map ?'}\n{agent_name or 'Agent ?'}",
        inline=True,
    )

    icon = agent_icon_url(details.get("agent_id"))
    if icon:
        embed.set_thumbnail(url=icon)

    if row["discord_id"]:
        member = guild.get_member(int(row["discord_id"]))
        if member is not None:
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

    played = _parse_match_date(entry)
    embed.timestamp = played or datetime.now(timezone.utc)
    return embed


def _rank_emoji_str(guild: discord.Guild, tier_name: Optional[str]) -> str:
    """Emoji custom du serveur pour un rang, sinon pastille de tier."""
    fr = api_rank_to_fr(tier_name)
    if fr:
        emoji = rank_select_emoji(guild, fr)
        if isinstance(emoji, discord.Emoji):
            return str(emoji)
        return emoji
    return "❔"


def build_leaderboard_embed(guild: discord.Guild, rows: List[sqlite3.Row], page: int, pages: int) -> discord.Embed:
    embed = discord.Embed(
        title="🏆  Classement du serveur",
        color=discord.Color(0xFF69B4),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    start = page * RR_PAGE_SIZE
    lignes: List[str] = []

    for index, row in enumerate(rows[start:start + RR_PAGE_SIZE], start=start + 1):
        medal = MEDALS.get(index, f"`#{index:>2}`")
        emoji = _rank_emoji_str(guild, row["current_tier_name"])
        rang = api_rank_to_fr(row["current_tier_name"]) or "Non classé"
        rr = row["current_rr"]
        elo = compute_elo(row["current_tier_id"], rr, row["elo"])

        # Écart avec le joueur juste au-dessus
        ecart = ""
        if index > 1:
            prec = rows[index - 2]
            delta = compute_elo(prec["current_tier_id"], prec["current_rr"], prec["elo"]) - elo
            if delta > 0:
                ecart = f" · `-{delta} elo`"

        # Forme sur les 5 dernières parties
        hist = db.rr_player_history(row["puuid"], limit=5)
        forme = "".join("🟩" if h["rr_change"] >= 0 else "🟥" for h in hist) or "⬜"

        lien = f" <@{row['discord_id']}>" if row["discord_id"] else ""
        lignes.append(
            f"{medal} {emoji} **{row['riot_name']}**{lien}\n"
            f"└ {rang} · **{rr} RR**{ecart}\n"
            f"└ {forme}"
        )

    embed.description = "\n\n".join(lignes) if lignes else "Aucun joueur suivi pour le moment."
    embed.set_footer(text=f"Page {page + 1}/{max(pages, 1)} • 🟩 victoire · 🟥 défaite (5 dernières)")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def build_daily_embed(guild: discord.Guild, stats: List[dict], jour_label: str) -> discord.Embed:
    embed = discord.Embed(
        title="📅 Classement journalier — RR gagnés / perdus",
        description=f"Bilan des parties classées du **{jour_label}**.",
        color=discord.Color(0xF1C40F),
    )
    if not stats:
        embed.description += "\n\nAucune partie classée enregistrée aujourd'hui."
        embed.timestamp = datetime.now(timezone.utc)
        return embed

    lignes = []
    for index, item in enumerate(stats[:20], start=1):
        medal = MEDALS.get(index, f"`{index}.`")
        total = item["total"]
        signe = "+" if total >= 0 else ""
        lignes.append(
            f"{medal} **{item['name']}** — {signe}{total} RR "
            f"({item['wins']}V / {item['losses']}D sur {item['games']} game(s))"
        )
    embed.add_field(name="Classement", value="\n".join(lignes), inline=False)

    best = stats[0]
    worst = stats[-1]
    resume = f"🔥 Meilleur : **{best['name']}** ({'+' if best['total'] >= 0 else ''}{best['total']} RR)"
    if len(stats) > 1:
        resume += f"\n💀 Pire : **{worst['name']}** ({'+' if worst['total'] >= 0 else ''}{worst['total']} RR)"
    total_global = sum(item["total"] for item in stats)
    resume += f"\n📊 Bilan du serveur : {'+' if total_global >= 0 else ''}{total_global} RR"
    embed.add_field(name="Résumé", value=resume, inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    return embed


class LeaderboardView(discord.ui.View):
    def __init__(self, guild: discord.Guild, rows: List[sqlite3.Row], page: int = 0,
                 author_id: Optional[int] = None):
        super().__init__(timeout=180)
        self.guild = guild
        self.rows = rows
        self.page = page
        self.author_id = author_id
        self.pages = max(1, math.ceil(len(rows) / RR_PAGE_SIZE))
        self._refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Lance `/leaderboard` toi-même pour naviguer.", ephemeral=True
            )
            return False
        return True

    def _refresh_buttons(self) -> None:
        self.previous_page.disabled = self.page <= 0
        self.next_page.disabled = self.page >= self.pages - 1

    async def _update(self, interaction: discord.Interaction) -> None:
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=build_leaderboard_embed(self.guild, self.rows, self.page, self.pages),
            view=self,
        )

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.page = max(0, self.page - 1)
        await self._update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.page = min(self.pages - 1, self.page + 1)
        await self._update(interaction)


# ===================== RR TRACKER : BOUCLE DE SUIVI =====================
def _paris_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(RR_TIMEZONE))
    except Exception:
        return datetime.now(timezone.utc)


def _start_of_today_utc_iso() -> str:
    now = _paris_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).isoformat()


async def process_player(guild: discord.Guild, row: sqlite3.Row,
                          channel: Optional[discord.TextChannel]) -> None:
    puuid = row["puuid"]
    region = row["region"] or RR_DEFAULT_REGION
    platform = row["platform"] or RR_DEFAULT_PLATFORM

    try:
        history_data = await valo_api.get_mmr_history(region, puuid, platform)
    except ValorantAPIError as exc:
        print(f"[RR] {row['riot_name']}#{row['riot_tag']} : {exc}")
        return

    # Mise à jour automatique du pseudo Riot en cas de changement.
    account = history_data.get("account") or {}
    new_name = account.get("name")
    new_tag = account.get("tag")
    if new_name and new_tag and (new_name != row["riot_name"] or new_tag != row["riot_tag"]):
        db.rr_update_identity(puuid, new_name, new_tag)
        if channel is not None:
            try:
                await channel.send(
                    f"🔄 **{row['riot_name']}#{row['riot_tag']}** a changé de pseudo Riot "
                    f"→ **{new_name}#{new_tag}**. Le suivi est à jour."
                )
            except discord.HTTPException:
                pass
        row = db.rr_get_player(puuid) or row

    history = history_data.get("history") or history_data.get("data") or []
    if not isinstance(history, list) or not history:
        return

    last_known = row["last_match_id"]
    ids_presents = {_extract_match_id(e) for e in history}

    nouvelles: List[dict] = []
    if last_known and last_known not in ids_presents:
        # Historique désynchronisé (nouvelle saison, trop de parties d'écart).
        # On se recale sur la dernière partie sans rien réannoncer.
        print(f"[RR] Historique désynchronisé pour {row['riot_name']}, recalage silencieux.")
    else:
        for entry in history:
            match_id = _extract_match_id(entry)
            if not match_id:
                continue
            if last_known and match_id == last_known:
                break
            nouvelles.append(entry)

    latest = history[0]
    latest_tier_id, latest_tier_name = _tier_from_entry(latest)
    latest_rr, _ = _rr_from_entry(latest)
    latest_match_id = _extract_match_id(latest)

    # Premier passage : on enregistre l'état sans spammer l'historique.
    if not last_known:
        db.rr_update_state(puuid, latest_tier_id, latest_tier_name, latest_rr,
                           latest.get("elo"), latest_match_id)
        return

    if not nouvelles:
        db.rr_update_state(puuid, latest_tier_id, latest_tier_name, latest_rr,
                           latest.get("elo"), last_known)
        return

    # On récupère les détails (agent, KDA, score) une seule fois pour toutes les nouvelles games.
    matches: List[dict] = []
    try:
        matches = await valo_api.get_matches(region, puuid, platform, size=max(5, len(nouvelles)))
    except ValorantAPIError as exc:
        print(f"[RR] Détails de match indisponibles pour {row['riot_name']} : {exc}")

    for entry in reversed(nouvelles):  # de la plus ancienne à la plus récente
        match_id = _extract_match_id(entry)
        rr_after, rr_change = _rr_from_entry(entry)
        if rr_change is None:
            continue
        tier_id, tier_name = _tier_from_entry(entry)
        details = _find_match_details(matches, match_id, puuid)

        inserted = db.rr_add_history(
            puuid=puuid,
            guild_id=guild.id,
            match_id=match_id,
            rr_change=int(rr_change),
            rr_after=rr_after,
            tier_name=tier_name,
            map_name=details.get("map_name") or _map_name_from_entry(entry),
            agent=details.get("agent_name"),
            kills=details.get("kills"),
            deaths=details.get("deaths"),
            assists=details.get("assists"),
            rounds_won=details.get("rounds_won"),
            rounds_lost=details.get("rounds_lost"),
            played_at=(_parse_match_date(entry) or datetime.now(timezone.utc)).isoformat(),
        )
        if not inserted:
            continue  # déjà annoncé

        if channel is not None:
            try:
                await channel.send(embed=build_match_embed(
                    guild, row, entry, details, int(rr_change), rr_after, tier_name
                ))
            except discord.HTTPException as exc:
                print(f"[RR] Envoi du résultat impossible : {exc}")
        await asyncio.sleep(1)

    db.rr_update_state(puuid, latest_tier_id, latest_tier_name, latest_rr,
                       latest.get("elo"), latest_match_id)

    # Synchronisation du rôle de rang si le compte est lié à un membre Discord.
    if row["discord_id"]:
        member = guild.get_member(int(row["discord_id"]))
        if member is not None:
            try:
                await sync_rank_role_from_api(member, latest_tier_name)
            except discord.HTTPException:
                pass


@tasks.loop(seconds=RR_POLL_INTERVAL)
async def rr_tracker_loop() -> None:
    await bot.wait_until_ready()
    if not HENRIK_API_KEY:
        return
    for guild in bot.guilds:
        players = db.rr_list_players(guild.id)
        if not players:
            continue
        channel = get_rr_channel(guild)
        if channel is None:
            channel = await ensure_rr_channel(guild)
        for row in players:
            try:
                await process_player(guild, row, channel)
            except Exception as exc:  # on ne casse jamais la boucle
                print(f"[RR] Erreur inattendue sur {row['riot_name']} : {exc}")
            await asyncio.sleep(1.5)


@rr_tracker_loop.error
async def rr_tracker_loop_error(exc: Exception) -> None:
    print(f"[RR] La boucle de suivi a planté : {exc}")
    await asyncio.sleep(30)
    if not rr_tracker_loop.is_running():
        rr_tracker_loop.start()


_DERNIER_RECAP: Dict[int, str] = {}


@tasks.loop(minutes=5)
async def rr_daily_recap_loop() -> None:
    await bot.wait_until_ready()
    now = _paris_now()
    if now.hour != RR_DAILY_RECAP_HOUR:
        return

    jour = now.strftime("%Y-%m-%d")
    for guild in bot.guilds:
        # Un seul récap par jour et par serveur, quels que soient les redémarrages.
        if _DERNIER_RECAP.get(guild.id) == jour:
            continue
        if not db.rr_list_players(guild.id):
            continue
        channel = get_rr_channel(guild)
        if channel is None:
            continue
        stats = db.rr_daily_stats(guild.id, _start_of_today_utc_iso())
        if not stats:
            continue
        try:
            await channel.send(embed=build_daily_embed(guild, stats, now.strftime("%d/%m/%Y")))
            _DERNIER_RECAP[guild.id] = jour
        except discord.HTTPException:
            pass


# ===================== UI: TICKETS =====================
class TicketStaffView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Supprimer le ticket", style=discord.ButtonStyle.danger, custom_id="ticket:delete")
    async def delete_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return
        # Vérifie si le membre a les permissions Orga PP ou le rôle Metsuke
        if not has_orga_access(interaction.user) and not any(r.id == METSUKE_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Seul le staff peut supprimer définitivement le ticket.", ephemeral=True)
        
        await interaction.response.send_message("🗑️ Suppression du ticket dans 5 secondes...")
        await asyncio.sleep(5)
        try:
            if isinstance(interaction.channel, discord.TextChannel):
                await interaction.channel.delete(reason=f"Ticket supprimé par {interaction.user.display_name}")
        except discord.HTTPException:
            pass


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎟️ Créer un ticket", style=discord.ButtonStyle.primary, custom_id="ticket:create")
    async def create_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
            
        guild = interaction.guild
        user = interaction.user
        
        ticket_name = f"ticket-{slug(user.display_name).replace(' ', '-')}"
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_name)
        
        if existing_channel:
            return await interaction.response.send_message(f"Tu as déjà un ticket ouvert : {existing_channel.mention}", ephemeral=True)

        category = find_category(guild, TICKET_CATEGORY_NAME)
        if not category:
            return await interaction.response.send_message("La catégorie de tickets est introuvable. Demande à un administrateur de refaire le /setup_pp.", ephemeral=True)

        metsuke_role = guild.get_role(METSUKE_ROLE_ID)
        if not metsuke_role:
            return await interaction.response.send_message(f"Erreur : Le rôle Metsuke ({METSUKE_ROLE_ID}) n'a pas été trouvé. Demande à un admin.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            metsuke_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        }

        ticket_channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket de {user.id}"
        )

        await interaction.response.send_message(f"✅ Ticket créé avec succès : {ticket_channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title="🎟️ Ticket Ouvert",
            description=(
                f"Bienvenue {user.mention} !\n"
                f"Un membre du staff ({metsuke_role.mention}) va te répondre sous peu.\n\n"
                "Merci d'expliquer ta demande en détail (Recrutement Staff, Preuve pour le rôle Radiant, ou autre problème)."
            ),
            color=discord.Color.gold()
        )
        await ticket_channel.send(content=f"{user.mention} {metsuke_role.mention}", embed=embed, view=TicketActiveView())


class TicketActiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
            
        if not isinstance(interaction.channel, discord.TextChannel):
            return

        await interaction.response.send_message("🔒 Le ticket a été fermé. Il est maintenant masqué pour toi.", ephemeral=True)
        
        # Retire la permission de voir le salon à l'utilisateur
        try:
            await interaction.channel.set_permissions(interaction.user, view_channel=False)
        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="🔒 Ticket fermé",
            description=f"Le ticket a été fermé par {interaction.user.mention}.\nLe staff peut désormais consulter les logs ou le supprimer définitivement.",
            color=discord.Color.dark_gray()
        )
        # Permet au staff de supprimer définitivement
        await interaction.channel.send(embed=embed, view=TicketStaffView())


# ===================== UI: CAPTCHA / VERIFICATION =====================
class CaptchaView(discord.ui.View):
    def __init__(self, guild: Optional[discord.Guild] = None):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="✅ Je ne suis pas un robot", style=discord.ButtonStyle.success, custom_id="pp:verify:captcha")
    async def captcha_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        
        roles = await ensure_core_roles(interaction.guild)
        
        # Retire le rôle non vérifié et ajoute le rôle joueur (Pèlerin)
        try:
            if roles["non_verified"] in interaction.user.roles:
                await interaction.user.remove_roles(roles["non_verified"], reason="Captcha validé")
            if roles["player"] not in interaction.user.roles:
                await interaction.user.add_roles(roles["player"], reason="Captcha validé")
        except discord.Forbidden:
            return await interaction.response.send_message("Erreur de permissions pour t'attribuer le rôle.", ephemeral=True)
            
        await interaction.response.send_message(
            f"✅ **Vérification réussie !** Tu as obtenu le rôle {roles['player'].mention}.\n"
            f"N'oublie pas de te rendre dans le salon **{RANK_CHANNEL_NAME}** pour choisir ton grade.",
            ephemeral=True
        )


class RankSelect(discord.ui.Select):
    def __init__(self, guild: Optional[discord.Guild] = None):
        options = [
            discord.SelectOption(
                label=name,
                value=name,
                emoji=rank_select_emoji(guild, name),
                description=f"Attribue le rôle {name}",
            )
            for name, _ in RANK_OPTIONS if name != "Radiant"
        ]
        super().__init__(
            placeholder="Choisis ton rank Valorant",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="pp:verify:rank",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)

        chosen_rank = self.values[0]
        await apply_rank(interaction.user, chosen_rank)
        await interaction.response.send_message(
            f"✅ Rank enregistré : **{chosen_rank}**. Ton profil est à jour.",
            ephemeral=True,
        )


class VerificationView(discord.ui.View):
    def __init__(self, guild: Optional[discord.Guild] = None):
        super().__init__(timeout=None)
        self.add_item(RankSelect(guild))


# ===================== UI: /pp MATCH =====================
class PPStartModal(discord.ui.Modal, title="Lancer une partie perso"):
    party_code = discord.ui.TextInput(
        label="Party code Valorant",
        placeholder="Ex: ABCD-EFGH-IJKL",
        required=True,
        max_length=64,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)

        prep_channel = interaction.user.voice.channel if interaction.user.voice else None
        if not is_prep_voice(prep_channel):
            return await interaction.response.send_message(
                "Tu dois être connecté dans **Préparation 1-4** pour utiliser `/pp`.",
                ephemeral=True,
            )

        if load_match_state(prep_channel.id) is not None:
            return await interaction.response.send_message(
                f"Une partie est déjà active dans **{prep_channel.name}**. Termine-la ou utilise `/pp_cleanup`.",
                ephemeral=True,
            )

        state = MatchState(
            prep_channel_id=prep_channel.id,
            started_by_id=interaction.user.id,
            ui_message_id=0,
            party_code=str(self.party_code.value).strip(),
            map_name=pick_map(),
            attack_ids=[],
            defense_ids=[],
            map_yes=0,
            map_no=0,
            map_locked=False,
            map_voters={},
        )

        ui_message = await prep_channel.send(embeds=build_match_embeds(interaction.guild, state), view=PPMatchView())
        state.ui_message_id = ui_message.id
        persist_match_state(state)

        count = len(ordered_prep_members(prep_channel))
        await interaction.response.send_message(
            (
                f"✅ Partie créée dans le chat de **{prep_channel.name}**.\n"
                f"Map + vote dispo tout de suite. Équipes auto seulement à **10 joueurs** minimum.\n"
                f"Joueurs actuellement détectés : **{count}**."
            ),
            ephemeral=True,
        )


class PPMatchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _resolve(self, interaction: discord.Interaction) -> Tuple[Optional[discord.VoiceChannel], Optional[MatchState]]:
        channel = interaction.channel
        if not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("Ce panneau doit être utilisé dans le chat d'un vocal Préparation.", ephemeral=True)
            return None, None

        state = load_match_state(channel.id)
        if state is None:
            await interaction.response.send_message("Aucune partie active pour ce vocal.", ephemeral=True)
            return None, None

        if interaction.message and interaction.message.id != state.ui_message_id:
            await interaction.response.send_message("Ce panneau est obsolète. Utilise le plus récent.", ephemeral=True)
            return None, None

        return channel, state

    @discord.ui.button(label="✅ Oui", style=discord.ButtonStyle.success, custom_id="pp:match:yes", row=0)
    async def vote_yes(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        prep_channel, state = await self._resolve(interaction)
        if prep_channel is None or state is None:
            return
        if state.map_locked:
            return await interaction.response.send_message("La map est déjà acceptée.", ephemeral=True)

        voter_key = str(interaction.user.id)
        if voter_key in state.map_voters:
            return await interaction.response.send_message("Tu as déjà voté pour cette map.", ephemeral=True)

        state.map_voters[voter_key] = "yes"
        state.map_yes += 1
        if state.map_yes >= VOTE_THRESHOLD_ACCEPT:
            state.map_locked = True
        persist_match_state(state)
        await interaction.response.edit_message(embeds=build_match_embeds(interaction.guild, state), view=self)

    @discord.ui.button(label="❌ Non", style=discord.ButtonStyle.danger, custom_id="pp:match:no", row=0)
    async def vote_no(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        prep_channel, state = await self._resolve(interaction)
        if prep_channel is None or state is None:
            return
        if state.map_locked:
            return await interaction.response.send_message("La map est déjà acceptée.", ephemeral=True)

        voter_key = str(interaction.user.id)
        if voter_key in state.map_voters:
            return await interaction.response.send_message("Tu as déjà voté pour cette map.", ephemeral=True)

        state.map_voters[voter_key] = "no"
        state.map_no += 1
        note = None
        if state.map_no >= VOTE_THRESHOLD_REJECT:
            old_map = state.map_name
            state.map_name = pick_map(exclude=old_map)
            state.map_yes = 0
            state.map_no = 0
            state.map_locked = False
            state.map_voters = {}
            note = "❌ 5 votes non atteints : nouvelle map proposée."

        persist_match_state(state)
        await interaction.response.edit_message(embeds=build_match_embeds(interaction.guild, state), view=self)
        if note:
            await interaction.followup.send(note, ephemeral=True)

    @discord.ui.button(label="🎲 Relancer (Orga)", style=discord.ButtonStyle.secondary, custom_id="pp:match:reroll", row=0)
    async def reroll(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        prep_channel, state = await self._resolve(interaction)
        if prep_channel is None or state is None:
            return
        if not is_match_controller(interaction.user, state):
            return await interaction.response.send_message("Réservé au créateur de la partie, Orga PP ou admin.", ephemeral=True)

        state.map_name = pick_map(exclude=state.map_name)
        state.map_yes = 0
        state.map_no = 0
        state.map_locked = False
        state.map_voters = {}
        persist_match_state(state)
        await interaction.response.edit_message(embeds=build_match_embeds(interaction.guild, state), view=self)

    @discord.ui.button(label="🚀 Lancer la PP", style=discord.ButtonStyle.primary, custom_id="pp:match:launch", row=1)
    async def launch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        prep_channel, state = await self._resolve(interaction)
        if prep_channel is None or state is None:
            return
        if not is_match_controller(interaction.user, state):
            return await interaction.response.send_message("Réservé au créateur de la partie, Orga PP ou admin.", ephemeral=True)
        if state.attack_ids or state.defense_ids:
            return await interaction.response.send_message("La PP est déjà lancée pour ce vocal.", ephemeral=True)

        current_members = ordered_prep_members(prep_channel)
        if len(current_members) < 10:
            await interaction.response.edit_message(embeds=build_match_embeds(interaction.guild, state), view=self)
            return await interaction.followup.send(
                f"Il faut **10 joueurs** pour lancer la PP. Actuellement : **{len(current_members)}/10**.",
                ephemeral=True,
            )

        selected_members = current_members[:10]
        waiting_members = current_members[10:]
        attack, defense = split_balanced_teams(selected_members)
        await apply_team_roles(interaction.guild, attack, defense)
        await move_teams_if_possible(prep_channel, attack, defense)

        state.attack_ids = [member.id for member in attack]
        state.defense_ids = [member.id for member in defense]
        persist_match_state(state)
        await interaction.response.edit_message(embeds=build_match_embeds(interaction.guild, state), view=self)

        if waiting_members:
            await interaction.followup.send(
                "✅ PP lancée avec les **10 premiers arrivés**. Hors top 10 : " + ", ".join(member.display_name for member in waiting_members),
                ephemeral=True,
            )

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger, custom_id="pp:match:cancel", row=1)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        prep_channel, state = await self._resolve(interaction)
        if prep_channel is None or state is None:
            return
        if not is_match_controller(interaction.user, state):
            return await interaction.response.send_message("Réservé au créateur de la partie, Orga PP ou admin.", ephemeral=True)

        db.delete_active_match(prep_channel.id)
        members = [m for m in interaction.guild.members if m.id in state.attack_ids + state.defense_ids]
        await clear_team_roles(interaction.guild, members)
        await interaction.response.edit_message(content="❌ Partie annulée.", embed=None, view=None)
        try:
            await prep_channel.send("❌ La partie active a été annulée.")
        except (discord.Forbidden, discord.HTTPException):
            pass


class CustomVoiceRenameModal(discord.ui.Modal, title="Renommer le salon privé"):
    new_name = discord.ui.TextInput(label="Nouveau nom", max_length=100)

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel) or not can_manage_custom_voice(interaction.user, channel):
            return await interaction.response.send_message("Tu ne peux pas gérer ce salon.", ephemeral=True)
        name = str(self.new_name.value).strip()
        if len(name) < 2:
            return await interaction.response.send_message("Nom trop court.", ephemeral=True)
        await channel.edit(name=name, reason="Custom voice rename via UI")
        await refresh_custom_voice_panel(channel)
        await interaction.response.send_message(f"✏️ Salon renommé en **{name}**.", ephemeral=True)


class CustomVoiceLimitModal(discord.ui.Modal, title="Changer la limite de slots"):
    slots = discord.ui.TextInput(label="Nombre de places (0 = illimité)", max_length=2, placeholder="0-99")

    def __init__(self, channel_id: int):
        super().__init__()
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel) or not can_manage_custom_voice(interaction.user, channel):
            return await interaction.response.send_message("Tu ne peux pas gérer ce salon.", ephemeral=True)
        try:
            limit = max(0, min(99, int(str(self.slots.value).strip())))
        except ValueError:
            return await interaction.response.send_message("Entre un nombre valide entre 0 et 99.", ephemeral=True)
        await channel.edit(user_limit=limit, reason="Custom voice limit via UI")
        await refresh_custom_voice_panel(channel)
        shown = str(limit) if limit else "∞"
        await interaction.response.send_message(f"👥 Limite mise à **{shown}**.", ephemeral=True)


class CustomVoiceKickSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, requester_id: int):
        self.channel_id = channel.id
        self.requester_id = requester_id
        options = [
            discord.SelectOption(label=m.display_name[:100], value=str(m.id))
            for m in channel.members[:25]
            if not m.bot and m.id != requester_id
        ]
        super().__init__(placeholder="Choisis qui expulser", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            return await interaction.response.send_message("Cette sélection ne t’est pas destinée.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if not isinstance(channel, discord.VoiceChannel) or not can_manage_custom_voice(interaction.user, channel):
            return await interaction.response.send_message("Tu ne peux pas gérer ce salon.", ephemeral=True)
        member = interaction.guild.get_member(int(self.values[0])) if interaction.guild else None
        if member is None or not member.voice or member.voice.channel.id != channel.id:
            return await interaction.response.send_message("Ce membre n'est plus dans la voc.", ephemeral=True)
        try:
            await member.move_to(None, reason=f"Disconnected from private voice by {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            return await interaction.response.send_message("Impossible de déconnecter ce membre.", ephemeral=True)
        await refresh_custom_voice_panel(channel)
        await interaction.response.send_message(f"⛔ {member.mention} a été déconnecté.", ephemeral=True)


class CustomVoiceKickView(discord.ui.View):
    def __init__(self, channel: discord.VoiceChannel, requester_id: int):
        super().__init__(timeout=60)
        self.add_item(CustomVoiceKickSelect(channel, requester_id))


class CustomVoiceControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _resolve(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        channel = interaction.channel
        if not isinstance(channel, discord.VoiceChannel) or not is_custom_voice(channel):
            await interaction.response.send_message("Ce panneau doit être utilisé dans le chat d’une voc privée.", ephemeral=True)
            return None
        if not isinstance(interaction.user, discord.Member) or not can_manage_custom_voice(interaction.user, channel):
            await interaction.response.send_message("Réservé au propriétaire du salon, Orga PP ou admin.", ephemeral=True)
            return None
        return channel

    @discord.ui.button(label="🔒 Lock", style=discord.ButtonStyle.secondary, custom_id="cvoice:lock")
    async def lock_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self._resolve(interaction)
        if channel is None:
            return
        owner_id = db.get_custom_voice_owner(channel.id)
        owner = interaction.guild.get_member(owner_id) if owner_id else interaction.user
        await set_custom_voice_permissions(channel, owner=owner, locked=True)
        await refresh_custom_voice_panel(channel)
        await interaction.response.send_message("🔒 Salon verrouillé.", ephemeral=True)

    @discord.ui.button(label="🔓 Unlock", style=discord.ButtonStyle.success, custom_id="cvoice:unlock")
    async def unlock_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self._resolve(interaction)
        if channel is None:
            return
        owner_id = db.get_custom_voice_owner(channel.id)
        owner = interaction.guild.get_member(owner_id) if owner_id else interaction.user
        await set_custom_voice_permissions(channel, owner=owner, locked=False)
        await refresh_custom_voice_panel(channel)
        await interaction.response.send_message("🔓 Salon ouvert.", ephemeral=True)

    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.primary, custom_id="cvoice:rename")
    async def rename_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self._resolve(interaction)
        if channel is None:
            return
        await interaction.response.send_modal(CustomVoiceRenameModal(channel.id))

    @discord.ui.button(label="👥 Slots", style=discord.ButtonStyle.primary, custom_id="cvoice:slots")
    async def slots_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self._resolve(interaction)
        if channel is None:
            return
        await interaction.response.send_modal(CustomVoiceLimitModal(channel.id))

    @discord.ui.button(label="⛔ Expulser", style=discord.ButtonStyle.danger, custom_id="cvoice:kick")
    async def kick_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self._resolve(interaction)
        if channel is None:
            return
        eligible = [m for m in channel.members if not m.bot and m.id != interaction.user.id]
        if not eligible:
            return await interaction.response.send_message("Personne à expulser dans cette voc.", ephemeral=True)
        await interaction.response.send_message("Choisis un membre à déconnecter :", view=CustomVoiceKickView(channel, interaction.user.id), ephemeral=True)


# ===================== BOT =====================
class PPBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)
        self.invites_cache = {}

    async def setup_hook(self) -> None:
        self.add_view(CaptchaView())
        self.add_view(VerificationView())
        self.add_view(PPMatchView())
        self.add_view(CustomVoiceControlView())
        self.add_view(TicketPanelView())
        self.add_view(TicketActiveView())
        self.add_view(TicketStaffView())
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = PPBot()


# ===================== EVENTS =====================
@bot.event
async def on_ready() -> None:
    await seed_existing_prep_members(bot.guilds)
    
    # Cache invitations pour le tracker
    for guild in bot.guilds:
        try:
            bot.invites_cache[guild.id] = await guild.invites()
        except discord.Forbidden:
            pass

    # --- RR TRACKER ---
    for guild in bot.guilds:
        try:
            await ensure_rr_channel(guild)
        except discord.HTTPException as exc:
            print(f"[RR] Salon non configuré sur {guild.name} : {exc}")

    if HENRIK_API_KEY:
        if not rr_tracker_loop.is_running():
            rr_tracker_loop.start()
        if not rr_daily_recap_loop.is_running():
            rr_daily_recap_loop.start()
        print(f"[RR] Tracker actif — vérification toutes les {RR_POLL_INTERVAL}s.")
    else:
        print("[RR] HENRIK_API_KEY manquante : le tracker RR est désactivé.")

    print(f"[OK] Connecté en tant que {bot.user} ({bot.user.id})")


@bot.event
async def on_invite_create(invite: discord.Invite) -> None:
    try:
        bot.invites_cache[invite.guild.id] = await invite.guild.invites()
    except discord.Forbidden:
        pass


@bot.event
async def on_invite_delete(invite: discord.Invite) -> None:
    try:
        bot.invites_cache[invite.guild.id] = await invite.guild.invites()
    except discord.Forbidden:
        pass


@bot.event
async def on_member_join(member: discord.Member) -> None:
    roles = await ensure_core_roles(member.guild)
    try:
        await member.add_roles(roles["non_verified"], reason="PP new member verification")
    except discord.Forbidden:
        pass

    # ================= TRACKER INVITATION =================
    inviter_mention = "/asak"
    try:
        old_invites = bot.invites_cache.get(member.guild.id, [])
        new_invites = await member.guild.invites()
        for invite in new_invites:
            for old_invite in old_invites:
                if invite.code == old_invite.code and invite.uses > old_invite.uses:
                    if invite.inviter:
                        inviter_mention = invite.inviter.mention
                    break
        bot.invites_cache[member.guild.id] = new_invites
    except discord.Forbidden:
        pass

    welcome_channel = get_welcome_channel(member.guild)
    if welcome_channel is not None:
        msg_content = (
            f"⛩️ Bienvenue dans les ruelles d'Asakusa, {member.mention} !\n"
            f"Tu as été invité(e) par **{inviter_mention}**."
        )
        try:
            # Génération de l'image personnalisée
            img_buffer = await generate_welcome_card(member)
            file = discord.File(fp=img_buffer, filename="welcome.png")
            await welcome_channel.send(content=msg_content, file=file)
        except Exception as e:
            # Fallback en cas d'erreur de la librairie d'image
            embed = discord.Embed(
                title="⛩️ Bienvenue à Asakusa",
                description=(
                    f"{member.mention}, les portes du temple s'ouvrent devant toi.\n"
                    f"Tu as été invité(e) par **{inviter_mention}**.\n\n"
                    f"Passe d'abord par **{VERIFY_CHANNEL_NAME}** pour prouver que tu n'es pas un robot."
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Une fois vérifié, n'oublie pas de choisir ton rang !")
            try:
                await welcome_channel.send(content=member.mention, embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    if member.bot:
        return

    if isinstance(before.channel, discord.VoiceChannel):
        if is_prep_voice(before.channel) and (not after.channel or after.channel.id != before.channel.id):
            forget_member_from_prep(before.channel, member)
            if load_match_state(before.channel.id) is not None:
                await refresh_match_message(member.guild, before.channel.id)
        if is_custom_voice(before.channel) and (not after.channel or after.channel.id != before.channel.id):
            await refresh_custom_voice_panel(before.channel)
        if not after.channel or after.channel.id != before.channel.id:
            await cleanup_custom_voice_if_empty(before.channel)

    if isinstance(after.channel, discord.VoiceChannel):
        if is_create_voice_trigger(after.channel) and (not before.channel or before.channel.id != after.channel.id):
            if not is_verified_member(member):
                try:
                    await member.move_to(None, reason="Verification required before creating custom voice")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return
            created = await create_custom_voice_channel(
                member.guild,
                member,
                f"🎤 Salon de {member.display_name}",
                CUSTOM_VOICE_DEFAULT_LIMIT,
            )
            return

        if is_prep_voice(after.channel) and (not before.channel or before.channel.id != after.channel.id):
            remember_member_in_prep(after.channel, member)
            if load_match_state(after.channel.id) is not None:
                await refresh_match_message(member.guild, after.channel.id)
        if is_custom_voice(after.channel) and (not before.channel or before.channel.id != after.channel.id):
            await ensure_custom_voice_panel(after.channel)
            await refresh_custom_voice_panel(after.channel)

# ===================== COMMANDS =====================
@bot.tree.command(name="setup_pp", description="Configure les rôles, permissions et panneaux PP sur les salons de la catégorie PP.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_pp(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        return await interaction.response.send_message("Commande réservée aux admins du serveur.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)

    roles = await ensure_core_roles(guild)
    await set_verification_permissions(guild)

    verify_channel = get_verify_channel(guild)
    rank_channel = get_rank_channel(guild)
    missing: List[str] = []
    
    if verify_channel is None:
        missing.append(f"#{VERIFY_CHANNEL_NAME} (ou alias de vérification)")
    if rank_channel is None:
        missing.append(f"#{RANK_CHANNEL_NAME} (ou alias pour le rank)")
        
    for name in PREP_CHANNEL_NAMES:
        found = discord.utils.find(
            lambda c: isinstance(c, discord.VoiceChannel) and slug(c.name) == slug(name),
            guild.channels,
        )
        if found is None:
            missing.append(name)

    # Déploiement du message Captcha
    if verify_channel is not None:
        should_post = True
        async for msg in verify_channel.history(limit=20):
            if msg.author == guild.me and msg.components:
                should_post = False
                break
        if should_post:
            embed = discord.Embed(
                title="🛡️ Vérification de sécurité",
                description="Bienvenue à Asakusa ! Avant de pouvoir entrer et discuter, prouve que tu n'es pas un robot en cliquant sur le bouton ci-dessous.",
                color=discord.Color.green(),
            )
            await verify_channel.send(embed=embed, view=CaptchaView(guild))

    # Déploiement du message de choix de Rank
    if rank_channel is not None:
        should_post = True
        async for msg in rank_channel.history(limit=20):
            if msg.author == guild.me and msg.components:
                should_post = False
                break
        if should_post:
            embed = discord.Embed(
                title="🎭 Choix du Rank Valorant",
                description="Choisis ton **Peak Elo Valorant des 5 derniers actes** pour mettre à jour ton profil.\nLe salon est en **lecture seule** : tout se fait via le menu.",
                color=discord.Color.blurple(),
            )
            await rank_channel.send(embed=embed, view=VerificationView(guild))


    # === CRÉATION ET CONFIGURATION DES TICKETS ===
    ticket_category = find_category(guild, TICKET_CATEGORY_NAME)
    if not ticket_category:
        ticket_category = await guild.create_category(TICKET_CATEGORY_NAME)

    ticket_channel = find_text_channel(guild, [TICKET_CHANNEL_NAME], category=ticket_category)
    if not ticket_channel:
        ticket_channel = await guild.create_text_channel(
            name=TICKET_CHANNEL_NAME,
            category=ticket_category
        )

    await _safe_set_permissions(ticket_channel, guild.default_role, view_channel=False)
    await _safe_set_permissions(ticket_channel, roles["non_verified"], view_channel=False)
    await _safe_set_permissions(
        ticket_channel,
        roles["member"],
        view_channel=True, send_messages=False, add_reactions=False, read_message_history=True
    )
    await _safe_set_permissions(
        ticket_channel,
        roles["orga"],
        view_channel=True, send_messages=True, add_reactions=True, read_message_history=True, manage_messages=True
    )
    
    metsuke_role = guild.get_role(METSUKE_ROLE_ID)
    if metsuke_role:
        await _safe_set_permissions(
            ticket_channel,
            metsuke_role,
            view_channel=True, send_messages=True, add_reactions=True, read_message_history=True, manage_messages=True
        )

    should_post_ticket = True
    async for msg in ticket_channel.history(limit=20):
        if msg.author == guild.me and msg.components:
            should_post_ticket = False
            break

    if should_post_ticket:
        embed = discord.Embed(
            title="🎟️ Assistance & Requêtes",
            description=(
                "Bienvenue au comptoir d'assistance d'Asakusa !\n\n"
                "Clique sur le bouton ci-dessous pour ouvrir un ticket privé avec le staff.\n\n"
                "**Utilise ce système pour :**\n"
                "• 📝 Demander à être recruté dans le staff.\n"
                "• 🌟 Demander l'attribution du rôle **Radiant** (merci de fournir des preuves in-game).\n"
                "• ❓ Toute autre question, problème ou signalement."
            ),
            color=discord.Color.red()
        )
        await ticket_channel.send(embed=embed, view=TicketPanelView())

    # === CRÉATION DU SALON DE SUIVI RR ===
    rr_channel = await ensure_rr_channel(guild)

    text = "✅ Setup de la catégorie PP terminé.\n• Les autres salons du serveur ont été laissés indépendants.\n"
    if rr_channel is not None:
        text += f"• Salon de suivi RR : {rr_channel.mention} (catégorie **{RR_CATEGORY_NAME}**).\n"
    else:
        text += "• ⚠️ Salon de suivi RR non créé (permission **Gérer les salons** manquante).\n"
    if missing:
        text += "⚠️ Salons introuvables : " + ", ".join(missing)
    else:
        text += "Tous les salons requis ont été configurés avec succès."
    await interaction.followup.send(text, ephemeral=True)


@bot.tree.command(name="pp", description="Lance une partie perso depuis ton vocal Préparation.")
@app_commands.guild_only()
async def pp(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
    if not has_orga_access(interaction.user):
        return await interaction.response.send_message("Commande réservée aux **Orga PP** et admins.", ephemeral=True)
    prep_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not is_prep_voice(prep_channel):
        return await interaction.response.send_message(
            "Tu dois être connecté dans **Préparation 1, 2, 3 ou 4** pour lancer `/pp`.",
            ephemeral=True,
        )
    if load_match_state(prep_channel.id) is not None:
        return await interaction.response.send_message(
            f"Une partie est déjà active dans **{prep_channel.name}**. Termine-la avec les boutons du panneau ou `/pp_cleanup`.",
            ephemeral=True,
        )
    await interaction.response.send_modal(PPStartModal())


@bot.tree.command(name="pp_cleanup", description="Retire les rôles d'équipe et ferme la partie active du vocal où tu es.")
@app_commands.guild_only()
async def pp_cleanup(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Interaction invalide.", ephemeral=True)
    if not has_orga_access(interaction.user):
        return await interaction.response.send_message("Commande réservée aux **Orga PP** et admins.", ephemeral=True)

    prep_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not is_prep_voice(prep_channel):
        return await interaction.response.send_message("Connecte-toi dans un vocal Préparation.", ephemeral=True)

    state = load_match_state(prep_channel.id)
    if state is None:
        return await interaction.response.send_message("Aucune partie active dans ce vocal.", ephemeral=True)
    if not is_match_controller(interaction.user, state):
        return await interaction.response.send_message("Réservé au créateur de la partie, Orga PP ou admin.", ephemeral=True)

    members = [m for m in interaction.guild.members if m.id in state.attack_ids + state.defense_ids]
    await clear_team_roles(interaction.guild, members)
    db.delete_active_match(prep_channel.id)
    await interaction.response.send_message("✅ Partie active nettoyée.", ephemeral=True)


# ===================== RR TRACKER : COMMANDES =====================
def _parse_riot_id(riot_id: str) -> Optional[Tuple[str, str]]:
    """Accepte 'Pseudo#TAG' ou 'Pseudo #TAG'."""
    if "#" not in riot_id:
        return None
    name, _, tag = riot_id.rpartition("#")
    name, tag = name.strip(), tag.strip()
    if not name or not tag:
        return None
    return name, tag


def _can_manage_rr(member: discord.Member) -> bool:
    return is_admin(member) or has_orga_access(member)


@bot.tree.command(name="rr_setup", description="Crée la catégorie NAKAMISE DORI et le salon rr-check.")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def rr_setup(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        return await interaction.response.send_message("Commande réservée aux admins du serveur.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)

    channel = await ensure_rr_channel(interaction.guild)
    if channel is None:
        return await interaction.followup.send(
            "❌ Impossible de créer le salon : il manque la permission **Gérer les salons** au bot.",
            ephemeral=True,
        )

    etat = "✅ Clé API HenrikDev détectée." if HENRIK_API_KEY else (
        "⚠️ `HENRIK_API_KEY` absente du `.env` : le suivi automatique est désactivé."
    )
    await interaction.followup.send(
        f"✅ Salon {channel.mention} prêt dans **{RR_CATEGORY_NAME}**.\n{etat}\n"
        f"Ajoute des joueurs avec `/rr_add`, puis consulte `/leaderboard` et `/rr_help`.",
        ephemeral=True,
    )


@bot.tree.command(name="rr_add", description="Ajoute un joueur au suivi RR (pseudo au format Pseudo#TAG).")
@app_commands.guild_only()
@app_commands.describe(
    riot_id="Identifiant Riot complet, ex: Uncrowned king#EUW",
    membre="Membre Discord à lier à ce compte (optionnel).",
    region="Région du compte (eu par défaut).",
)
@app_commands.choices(region=[app_commands.Choice(name=r.upper(), value=r) for r in VALID_REGIONS])
async def rr_add(interaction: discord.Interaction, riot_id: str,
                 membre: Optional[discord.Member] = None,
                 region: Optional[app_commands.Choice[str]] = None) -> None:
    if not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Interaction invalide.", ephemeral=True)

    cible = membre or interaction.user
    if cible != interaction.user and not _can_manage_rr(interaction.user):
        return await interaction.response.send_message(
            "Seuls les orgas et les admins peuvent ajouter le compte d'un autre membre.", ephemeral=True
        )

    parsed = _parse_riot_id(riot_id)
    if parsed is None:
        return await interaction.response.send_message(
            "Format invalide. Utilise `Pseudo#TAG`, par exemple `Uncrowned king#EUW`.", ephemeral=True
        )
    name, tag = parsed
    region_value = region.value if region else RR_DEFAULT_REGION

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        account = await valo_api.get_account(name, tag)
        puuid = account.get("puuid")
        if not puuid:
            return await interaction.followup.send("❌ Compte introuvable.", ephemeral=True)
        detected_region = (account.get("region") or region_value or RR_DEFAULT_REGION).lower()
        if detected_region not in VALID_REGIONS:
            detected_region = region_value
        platform = RR_DEFAULT_PLATFORM
        mmr = await valo_api.get_mmr(detected_region, puuid, platform)

        current = mmr.get("current") or {}
        tier = current.get("tier") or {}
        tier_id, tier_name = tier.get("id"), tier.get("name")
        rr = current.get("rr")
        elo = current.get("elo")
        peak = mmr.get("peak") or {}
        peak_tier = peak.get("tier") or {}
        peak_tier_id, peak_tier_name = peak_tier.get("id"), peak_tier.get("name")
        real_name = (mmr.get("account") or {}).get("name") or account.get("name") or name
        real_tag = (mmr.get("account") or {}).get("tag") or account.get("tag") or tag

        db.rr_add_player(puuid, interaction.guild.id, cible.id, real_name, real_tag,
                         detected_region, platform, interaction.user.id)
        db.rr_update_state(puuid, tier_id, tier_name, rr, elo, None)
        db.rr_update_peak(puuid, peak_tier_id, peak_tier_name)

        applied = None
        if RR_AUTO_SYNC_ROLES:
            try:
                applied = await sync_rank_role_from_api(cible, peak_tier_name or tier_name)
            except discord.HTTPException:
                pass

        channel = get_rr_channel(interaction.guild) or await ensure_rr_channel(interaction.guild)
        message = (
            f"✅ **{real_name}#{real_tag}** est maintenant suivi.\n"
            f"• Rang actuel : **{rank_display(tier_name, rr)}**\n"
            f"• Région : `{detected_region}` · Lié à {cible.mention}\n"
        )
        if applied:
            message += f"• Rôle **{applied}** attribué automatiquement.\n"
        if channel:
            message += f"• Les résultats seront publiés dans {channel.mention}."
        await interaction.followup.send(message, ephemeral=True)

    except ValorantAPIError as exc:
        await interaction.followup.send(f"❌ {exc}", ephemeral=True)
    except Exception as exc:
        import traceback
        print(f"[RR] /rr_add a planté pour {riot_id} : {exc}")
        traceback.print_exc()
        await interaction.followup.send(
            f"❌ Erreur inattendue pendant l'ajout : `{exc}`\nRegarde les logs Render pour le détail complet.",
            ephemeral=True,
        )


@bot.tree.command(name="rr_remove", description="Retire un joueur du suivi RR.")
@app_commands.guild_only()
@app_commands.describe(riot_id="Identifiant Riot du joueur à retirer (Pseudo#TAG).")
async def rr_remove(interaction: discord.Interaction, riot_id: str) -> None:
    if not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Interaction invalide.", ephemeral=True)

    parsed = _parse_riot_id(riot_id)
    if parsed is None:
        return await interaction.response.send_message(
            "Format invalide. Utilise `Pseudo#TAG`.", ephemeral=True
        )
    name, tag = parsed
    row = db.rr_find_player(interaction.guild.id, name, tag)
    if row is None:
        return await interaction.response.send_message(
            f"❌ **{name}#{tag}** n'est pas dans la liste de suivi.", ephemeral=True
        )

    est_le_sien = row["discord_id"] and int(row["discord_id"]) == interaction.user.id
    if not est_le_sien and not _can_manage_rr(interaction.user):
        return await interaction.response.send_message(
            "Seuls les orgas et les admins peuvent retirer le compte d'un autre membre.", ephemeral=True
        )

    db.rr_remove_player(row["puuid"])
    await interaction.response.send_message(
        f"🗑️ **{row['riot_name']}#{row['riot_tag']}** a été retiré du suivi RR "
        f"(son historique a été supprimé).", ephemeral=True
    )


@bot.tree.command(name="rr_list", description="Affiche la liste des joueurs suivis par le tracker RR.")
@app_commands.guild_only()
async def rr_list(interaction: discord.Interaction) -> None:
    players = db.rr_list_players(interaction.guild.id)
    if not players:
        return await interaction.response.send_message(
            "Aucun joueur suivi pour l'instant. Ajoute-toi avec `/rr_add Pseudo#TAG`.", ephemeral=True
        )

    lignes = []
    for row in players:
        lien = f"<@{row['discord_id']}>" if row["discord_id"] else "*non lié*"
        lignes.append(
            f"• **{row['riot_name']}#{row['riot_tag']}** — {rank_display(row['current_tier_name'], row['current_rr'])} "
            f"· {lien} · `{row['region']}`"
        )

    embed = discord.Embed(
        title=f"🎯 Joueurs suivis ({len(players)})",
        description="\n".join(lignes)[:4000],
        color=discord.Color(0xFF69B4),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="leaderboard", description="Classement des joueurs suivis par RR.")
@app_commands.guild_only()
async def leaderboard(interaction: discord.Interaction) -> None:
    rows = db.rr_leaderboard(interaction.guild.id)
    if not rows:
        return await interaction.response.send_message(
            "Aucun joueur suivi pour l'instant. Ajoute-toi avec `/rr_add Pseudo#TAG`.", ephemeral=True
        )
    pages = max(1, math.ceil(len(rows) / RR_PAGE_SIZE))
    view = LeaderboardView(interaction.guild, rows, author_id=interaction.user.id) if pages > 1 else None
    await interaction.response.send_message(
        embed=build_leaderboard_embed(interaction.guild, rows, 0, pages), view=view
    )


@bot.tree.command(name="daily", description="Classement journalier des RR gagnés et perdus.")
@app_commands.guild_only()
async def daily(interaction: discord.Interaction) -> None:
    stats = db.rr_daily_stats(interaction.guild.id, _start_of_today_utc_iso())
    embed = build_daily_embed(interaction.guild, stats, _paris_now().strftime("%d/%m/%Y"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rr_stats", description="Statistiques RR détaillées d'un joueur suivi.")
@app_commands.guild_only()
@app_commands.describe(
    riot_id="Identifiant Riot (Pseudo#TAG). Laisse vide pour ton propre compte.",
    membre="Ou choisis directement un membre Discord.",
)
async def rr_stats(interaction: discord.Interaction, riot_id: Optional[str] = None,
                   membre: Optional[discord.Member] = None) -> None:
    row = None
    if riot_id:
        parsed = _parse_riot_id(riot_id)
        if parsed is None:
            return await interaction.response.send_message("Format invalide : `Pseudo#TAG`.", ephemeral=True)
        row = db.rr_find_player(interaction.guild.id, *parsed)
    else:
        cible = membre or interaction.user
        row = db.rr_find_by_discord(interaction.guild.id, cible.id)

    if row is None:
        return await interaction.response.send_message(
            "❌ Ce joueur n'est pas suivi. Ajoute-le avec `/rr_add Pseudo#TAG`.", ephemeral=True
        )

    jour = db.rr_period_stats(interaction.guild.id, row["puuid"], _start_of_today_utc_iso())
    semaine_iso = (_paris_now() - timedelta(days=7)).astimezone(timezone.utc).isoformat()
    semaine = db.rr_period_stats(interaction.guild.id, row["puuid"], semaine_iso)

    embed = discord.Embed(
        title=f"📊 {row['riot_name']}#{row['riot_tag']}",
        description=f"Rang actuel : **{rank_display(row['current_tier_name'], row['current_rr'])}**",
        color=discord.Color(0xFF69B4),
    )
    if row["discord_id"]:
        member = interaction.guild.get_member(int(row["discord_id"]))
        if member:
            embed.set_thumbnail(url=member.display_avatar.url)

    def _bloc(stats) -> str:
        if not stats or not stats["games"]:
            return "Aucune partie."
        total = stats["total"] or 0
        return (f"{'+' if total >= 0 else ''}{total} RR\n"
                f"{stats['wins']}V / {stats['losses']}D ({stats['games']} games)")

    embed.add_field(name="Aujourd'hui", value=_bloc(jour), inline=True)
    embed.add_field(name="7 derniers jours", value=_bloc(semaine), inline=True)

    historique = db.rr_player_history(row["puuid"], limit=5)
    if historique:
        lignes = []
        for h in historique:
            signe = "🟢 +" if h["rr_change"] >= 0 else "🔴 "
            score = f" ({h['rounds_won']}-{h['rounds_lost']})" if h["rounds_won"] is not None else ""
            agent = f" · {h['agent']}" if h["agent"] else ""
            lignes.append(f"{signe}{h['rr_change']} RR — {h['map_name'] or 'Map ?'}{score}{agent}")
        embed.add_field(name="5 dernières parties", value="\n".join(lignes), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rr_help", description="Aide complète sur le bot de suivi RR.")
@app_commands.guild_only()
async def rr_help(interaction: discord.Interaction) -> None:
    channel = get_rr_channel(interaction.guild)
    salon = channel.mention if channel else f"`{RR_CHANNEL_NAME}`"

    embed = discord.Embed(
        title="🏆 Aide — Suivi RR Valorant",
        description=(
            f"Le bot surveille les parties classées des joueurs enregistrés et publie "
            f"automatiquement le résultat dans {salon} (RR gagnés/perdus, score, agent, map).\n"
            f"Vérification toutes les **{RR_POLL_INTERVAL // 60} minutes** environ."
        ),
        color=discord.Color(0xFF69B4),
    )
    embed.add_field(
        name="➕ Ajouter un joueur",
        value=(
            "`/rr_add riot_id:Pseudo#TAG`\n"
            "Ajoute ton propre compte au suivi.\n\n"
            "`/rr_add riot_id:Pseudo#TAG membre:@Untel`\n"
            "Ajoute le compte d'un autre membre *(orga/admin uniquement)*.\n\n"
            "L'option `region` permet de préciser le serveur (eu par défaut)."
        ),
        inline=False,
    )
    embed.add_field(
        name="➖ Retirer un joueur",
        value=(
            "`/rr_remove riot_id:Pseudo#TAG`\n"
            "Retire le compte du suivi et supprime son historique. "
            "Chacun peut retirer son propre compte ; les orgas peuvent retirer n'importe qui."
        ),
        inline=False,
    )
    embed.add_field(
        name="📋 Consulter",
        value=(
            "`/leaderboard` — classement général par RR (avec pages)\n"
            "`/daily` — classement journalier des RR gagnés/perdus\n"
            "`/rr_list` — liste des comptes suivis\n"
            "`/rr_stats` — stats détaillées d'un joueur (jour, semaine, 5 dernières games)"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ Administration",
        value=(
            "`/rr_setup` — crée la catégorie et le salon de suivi\n"
            "`/rr_refresh` — force une vérification immédiate de tous les comptes"
        ),
        inline=False,
    )
    embed.add_field(
        name="ℹ️ Bon à savoir",
        value=(
            "• Un changement de pseudo Riot est détecté et mis à jour tout seul.\n"
            "• Le rôle de rang Discord est synchronisé automatiquement après chaque partie.\n"
            "• Le récap journalier est publié chaque soir à "
            f"{RR_DAILY_RECAP_HOUR}h.\n"
            "• Seules les parties **classées** sont prises en compte."
        ),
        inline=False,
    )
    embed.set_footer(text="Données fournies par l'API communautaire HenrikDev — non affiliée à Riot Games.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="rr_refresh", description="Force une vérification immédiate de tous les comptes suivis.")
@app_commands.guild_only()
async def rr_refresh(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member) or not _can_manage_rr(interaction.user):
        return await interaction.response.send_message(
            "Commande réservée aux orgas et aux admins.", ephemeral=True
        )
    if not HENRIK_API_KEY:
        return await interaction.response.send_message(
            "❌ `HENRIK_API_KEY` absente du `.env` : le suivi est désactivé.", ephemeral=True
        )

    await interaction.response.defer(ephemeral=True, thinking=True)
    players = db.rr_list_players(interaction.guild.id)
    if not players:
        return await interaction.followup.send("Aucun joueur suivi.", ephemeral=True)

    channel = get_rr_channel(interaction.guild) or await ensure_rr_channel(interaction.guild)
    erreurs = 0
    for row in players:
        try:
            await process_player(interaction.guild, row, channel)
        except Exception as exc:
            erreurs += 1
            print(f"[RR] refresh — erreur sur {row['riot_name']} : {exc}")
        await asyncio.sleep(1)

    texte = f"✅ Vérification terminée pour {len(players)} joueur(s)."
    if erreurs:
        texte += f"\n⚠️ {erreurs} compte(s) en erreur (voir les logs)."
    await interaction.followup.send(texte, ephemeral=True)


@bot.tree.command(name="rr_debug", description="Diagnostic complet du tracker RR (admin).")
@app_commands.guild_only()
@app_commands.describe(riot_id="Compte à tester (Pseudo#TAG). Vide = premier compte suivi.")
async def rr_debug(interaction: discord.Interaction, riot_id: Optional[str] = None) -> None:
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        return await interaction.response.send_message("Réservé aux admins.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    lignes: List[str] = []

    # --- 1. Configuration ---
    cle = HENRIK_API_KEY
    if not cle:
        lignes.append("❌ **HENRIK_API_KEY absente** → tracker totalement désactivé.")
    elif not cle.startswith("HDEV-"):
        lignes.append(f"⚠️ Clé présente mais ne commence pas par `HDEV-` (début : `{cle[:6]}…`).")
    else:
        lignes.append(f"✅ Clé présente (`{cle[:9]}…`, {len(cle)} caractères).")

    lignes.append(f"• Boucle de suivi active : **{rr_tracker_loop.is_running()}**")
    lignes.append(f"• Récap journalier actif : **{rr_daily_recap_loop.is_running()}**")
    lignes.append(f"• Intervalle : **{RR_POLL_INTERVAL}s**")

    channel = get_rr_channel(interaction.guild)
    lignes.append(f"• Salon RR : {channel.mention if channel else '❌ introuvable'}")

    players = db.rr_list_players(interaction.guild.id)
    lignes.append(f"• Comptes suivis : **{len(players)}**")

    # --- 2. Cible du test ---
    row = None
    if riot_id:
        parsed = _parse_riot_id(riot_id)
        if parsed:
            row = db.rr_find_player(interaction.guild.id, *parsed)
    elif players:
        row = players[0]

    if row is None:
        lignes.append("\n⚠️ Aucun compte à tester. Ajoute-en un avec `/rr_add`.")
        return await interaction.followup.send("\n".join(lignes)[:1900], ephemeral=True)

    lignes.append(f"\n**Test sur `{row['riot_name']}#{row['riot_tag']}`** (`{row['region']}`)")
    lignes.append(f"• last_match_id en base : `{row['last_match_id'] or 'aucun'}`")

    # --- 3. Appel réel à l'API ---
    try:
        data = await valo_api.get_mmr_history(row["region"], row["puuid"], row["platform"])
        lignes.append(f"✅ Appel mmr-history OK — clés : `{list(data.keys())}`")

        history = data.get("history") or []
        lignes.append(f"• Entrées d'historique : **{len(history)}**")

        if history:
            e0 = history[0]
            tier_id, tier_name = _tier_from_entry(e0)
            rr_after, change = _rr_from_entry(e0)
            mid = _extract_match_id(e0)
            lignes.append(
                f"• Dernière partie : `{mid}`\n"
                f"  tier=`{tier_name}` ({tier_id}) · rr=`{rr_after}` · change=`{change}`\n"
                f"  map=`{_map_name_from_entry(e0)}` · date=`{_parse_match_date(e0)}`"
            )
            if mid == row["last_match_id"]:
                lignes.append("  ↳ ✅ Déjà annoncée : comportement normal, rien à publier.")
            else:
                lignes.append("  ↳ ⚠️ **Non annoncée** alors qu'elle devrait l'être → bug de publication.")
            if change is None:
                lignes.append("  ↳ ❌ `last_change` absent : le parsing échoue, l'entrée est ignorée.")
        else:
            lignes.append("⚠️ Historique vide : aucune partie classée récente, ou saison réinitialisée.")

    except ValorantAPIError as exc:
        lignes.append(f"❌ **Échec de l'appel API** : {exc}")
    except Exception as exc:
        lignes.append(f"❌ **Exception inattendue** : `{type(exc).__name__}: {exc}`")

    # --- 4. Permissions d'écriture dans le salon ---
    if channel:
        perms = channel.permissions_for(interaction.guild.me)
        if not (perms.send_messages and perms.embed_links):
            lignes.append(
                f"\n❌ Le bot ne peut pas écrire dans {channel.mention} "
                f"(send_messages={perms.send_messages}, embed_links={perms.embed_links})."
            )
        else:
            lignes.append(f"\n✅ Droits d'écriture OK dans {channel.mention}.")

    await interaction.followup.send("\n".join(lignes)[:1900], ephemeral=True)


# ===================== RENDER WEB HEALTH SERVER =====================
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "10000")))


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = b"not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        return


def start_health_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HTTP] Health server listening on http://{WEB_HOST}:{WEB_PORT}")
    return server


# ===================== RUN =====================
def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN manquant dans le .env")
    start_health_server()
    try:
        bot.run(TOKEN)
    finally:
        try:
            asyncio.run(valo_api.close())
        except Exception:
            pass


if __name__ == "__main__":
    main()