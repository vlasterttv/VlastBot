"""
=======================================================================
  BOOST SERVER BOT — Setup complet + Vérification anti-raid + Tickets
=======================================================================
  Dépendances : discord.py >= 2.3.2
  Lancement   : python bot.py
  Variables   : DISCORD_TOKEN (obligatoire)
=======================================================================
"""

import os
import json
import time
import asyncio
import datetime
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer

import discord
from discord.ext import commands
from discord import app_commands

import aiohttp

# ======================================================================
#  CONFIGURATION
# ======================================================================

TOKEN = os.getenv("DISCORD_TOKEN")

# --- Noms des rôles (modifiables, mais garde la cohérence partout) ---
R_ADMIN = "👑 Administrateur"
R_BOOSTER = "🚀 Booster"
R_CLIENT = "💰 Client"
R_MEMBRE = "💬 Membre"
R_UNVERIFIED = "🔒 Non vérifié"
R_FR = "🇫🇷 Français"
R_EN = "🇬🇧 English"

# --- Couleurs ---
# 0x000000 est traité comme "pas de couleur" par Discord -> on utilise 0x010101
C_ADMIN = 0x010101      # Noir
C_BOOSTER = 0xE74C3C    # Rouge
C_CLIENT = 0xF1C40F     # Jaune
C_MEMBRE = 0x5DADE2     # Bleu ciel
C_UNVERIFIED = 0x2B2D31 # Gris fondu
C_FR = 0x8E9BFF         # Bleu-violet doux
C_EN = 0xB0B8C4         # Gris-bleu neutre

# --- Anti-raid ---
MIN_ACCOUNT_AGE_DAYS = 7     # Âge minimum du compte pour se vérifier
RAID_JOIN_COUNT = 8          # X arrivées...
RAID_JOIN_WINDOW = 20        # ...en Y secondes = lockdown
LOCKDOWN_DURATION = 300      # Durée du lockdown en secondes

DATA_FILE = "bot_data.json"

# --- Emojis du serveur (IDs récupérés via \:nom: dans Discord) ---------
EMO = {
    "iron1": "<:valorantiron1:1542912599161569280>",
    "iron2": "<:valorantiron2:1542912569860296805>",
    "iron3": "<:valorantiron3:1542912533705400400>",
    "bronze1": "<:valorantbronze1:1542912473575989268>",
    "bronze2": "<:valorantbronze2:1542912435714002994>",
    "bronze3": "<:valorantbronze3:1542912403098959954>",
    "silver1": "<:valorantsilver1:1542912358119378984>",
    "silver2": "<:valorantsilver2:1542912325386899507>",
    "silver3": "<:valorantsilver3:1542912283322351727>",
    "gold1": "<:valorantgold1:1542912240854769837>",
    "gold2": "<:valorantgold2:1542912212111327345>",
    "gold3": "<:valorantgold3:1542912184625930240>",
    "plat1": "<:valorantplatinum1:1542912150253605035>",
    "plat2": "<:valorantplatinum2:1542912120088297632>",
    "plat3": "<:valorantplatinum3:1542912075607842897>",
    "dia1": "<:valorantdiamond1:1542912049162756180>",
    "dia2": "<:valorantdiamond2:1542912005999169577>",
    "dia3": "<:valorantdiamond3:1542911979155497001>",
    "asc1": "<:valorantascendant1:1542911948105064468>",
    "asc2": "<:valorantascendant2:1542911922146648206>",
    "asc3": "<:valorantascendant3:1542911901519052900>",
    "immo1": "<:valorantimmortal1:1542911864659386398>",
    "immo2": "<:valorantimmortal2:1542911831847211070>",
    "immo3": "<:valorantimmortal3:1542911806832386129>",
    "radiant": "<:valorantradiant:1542911768190521427>",
    "paypal": "<:1716_PAYPAL:1542978995581100122>",
    "btc": "<:Bitcoin:1542978979483484190>",
    "eth": "<:18119ethereum:1542979675200950303>",
    "usdt": "<:7541tetherusdtCopie:1542978958600044634>",
}

# --- Paiements crypto (vérification manuelle assistée) -----------------
# Remplace ces adresses par les tiennes. Laisse vide "" pour désactiver
# une devise (la commande /request_payment ne la proposera plus).
WALLETS = {
    "BTC": "",              # ex: bc1qxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    "ETH": "",               # ex: 0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    "USDT_ERC20": "",        # même adresse ETH en général, mais séparée au cas où
}

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
USDT_CONTRACT = "0xdac17f958d2ee523a2206206994597c13d831ec"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

PAYMENT_TOLERANCE = 0.01        # 1% de marge (frais réseau, arrondis)
MIN_CONFIRMATIONS_BTC = 1
MIN_CONFIRMATIONS_ETH = 3

# ======================================================================
#  PERSISTANCE (compteur de tickets, salons de logs)
# ======================================================================


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"ticket_counter": 0, "guilds": {}}


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


DATA = load_data()

# ======================================================================
#  BOT
# ======================================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class BoostBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.join_log: dict[int, deque] = {}
        self.lockdown: dict[int, float] = {}

    async def setup_hook(self):
        # Vues persistantes : les boutons restent actifs après un redémarrage
        self.add_view(VerifyView())
        self.add_view(TicketPanelView())
        self.add_view(TicketPanelViewEN())
        self.add_view(TicketControlView())
        self.add_view(PaymentRequestView())
        self.add_view(PaymentConfirmView())
        await self.tree.sync()
        print("→ Commandes slash synchronisées.")


bot = BoostBot()


@bot.event
async def on_ready():
    print(f"→ Connecté en tant que {bot.user} ({bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="vos rangs monter 🚀"
        )
    )


# ======================================================================
#  HELPERS
# ======================================================================


def get_role(guild: discord.Guild, name: str) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=name)


def guild_conf(guild_id: int) -> dict:
    return DATA["guilds"].setdefault(str(guild_id), {})


async def log_event(guild: discord.Guild, embed: discord.Embed):
    """Envoie un embed dans le salon de logs s'il existe."""
    conf = guild_conf(guild.id)
    channel_id = conf.get("log_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


# ======================================================================
#  VUE — VÉRIFICATION
# ======================================================================


class VerifyView(discord.ui.View):
    """Vérification bilingue : le choix de la langue vaut validation."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _do_verify(self, interaction: discord.Interaction, lang: str):
        guild = interaction.guild
        member = interaction.user

        role_membre = get_role(guild, R_MEMBRE)
        role_unverified = get_role(guild, R_UNVERIFIED)
        role_lang = get_role(guild, R_FR if lang == "fr" else R_EN)
        role_other = get_role(guild, R_EN if lang == "fr" else R_FR)

        if role_membre is None or role_lang is None:
            return await interaction.response.send_message(
                "⚠️ Rôles introuvables. Un administrateur doit relancer `/setup`.\n"
                "⚠️ Roles not found. An administrator must run `/setup` again.",
                ephemeral=True,
            )

        if role_membre in member.roles:
            return await interaction.response.send_message(
                "✅ Tu es déjà vérifié. Utilise `/langue` pour changer de langue.\n"
                "✅ You are already verified. Use `/langue` to switch language.",
                ephemeral=True,
            )

        # --- Lockdown anti-raid actif ---
        if bot.lockdown.get(guild.id, 0) > time.time():
            return await interaction.response.send_message(
                "🛡️ Le serveur est en **mode protection**. Réessaie dans quelques minutes.\n"
                "🛡️ The server is in **protection mode**. Try again in a few minutes.",
                ephemeral=True,
            )

        # --- Contrôle de l'âge du compte ---
        age = discord.utils.utcnow() - member.created_at
        if age.days < MIN_ACCOUNT_AGE_DAYS:
            await log_event(
                guild,
                discord.Embed(
                    title="🚫 Vérification refusée",
                    description=f"{member.mention} — compte créé il y a **{age.days} jour(s)**.",
                    colour=C_BOOSTER,
                ),
            )
            return await interaction.response.send_message(
                f"🚫 Ton compte est trop récent (**{age.days}j**, minimum {MIN_ACCOUNT_AGE_DAYS}j).\n"
                f"🚫 Your account is too new (**{age.days}d**, minimum {MIN_ACCOUNT_AGE_DAYS}d).",
                ephemeral=True,
            )

        try:
            to_add = [role_membre, role_lang]
            await member.add_roles(*to_add, reason=f"Vérification réussie ({lang})")
            to_remove = [r for r in (role_unverified, role_other) if r and r in member.roles]
            if to_remove:
                await member.remove_roles(*to_remove, reason="Vérification réussie")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "⚠️ Permissions insuffisantes : mon rôle doit être **au-dessus** des autres.\n"
                "⚠️ Missing permissions: my role must be **above** the others.",
                ephemeral=True,
            )

        if lang == "fr":
            msg = (
                "🎉 **Bienvenue !** Tu as maintenant accès aux salons francophones.\n"
                "Passe par la catégorie **Ticket Boost** pour commander."
            )
        else:
            msg = (
                "🎉 **Welcome!** You now have access to the English channels.\n"
                "Head to the **Boost Tickets** category to place an order."
            )
        await interaction.response.send_message(msg, ephemeral=True)

        await log_event(
            guild,
            discord.Embed(
                title="✅ Nouveau membre vérifié",
                description=(
                    f"{member.mention} • `{member}`\n"
                    f"Langue : **{'Français' if lang == 'fr' else 'English'}**\n"
                    f"Compte créé il y a **{age.days} jours**."
                ),
                colour=C_MEMBRE,
            ),
        )

    @discord.ui.button(
        label="Français",
        emoji="🇫🇷",
        style=discord.ButtonStyle.primary,
        custom_id="persistent:verify_fr",
    )
    async def verify_fr(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._do_verify(interaction, "fr")

    @discord.ui.button(
        label="English",
        emoji="🇬🇧",
        style=discord.ButtonStyle.secondary,
        custom_id="persistent:verify_en",
    )
    async def verify_en(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._do_verify(interaction, "en")


# ======================================================================
#  VÉRIFICATION DE PAIEMENT CRYPTO
# ======================================================================


def extract_txid(raw: str) -> str:
    """Nettoie un lien d'explorateur pour n'en garder que le hash de tx."""
    raw = raw.strip()
    if "/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
    return raw.split("?")[0]


async def check_btc_tx(txid: str, expected_amount: float, wallet: str) -> dict:
    """Vérifie une transaction Bitcoin via l'API publique Blockstream."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://blockstream.info/api/tx/{txid}") as r:
            if r.status != 200:
                return {"ok": False, "reason": "Transaction introuvable. Vérifie le lien."}
            tx = await r.json()

        received = sum(
            vout["value"] for vout in tx.get("vout", [])
            if vout.get("scriptpubkey_address") == wallet
        ) / 1e8

        confirmations = 0
        if tx.get("status", {}).get("confirmed"):
            async with session.get("https://blockstream.info/api/blocks/tip/height") as r2:
                tip = await r2.json()
            confirmations = tip - tx["status"]["block_height"] + 1

    if received == 0:
        return {"ok": False, "reason": "Aucun montant envoyé à l'adresse attendue dans cette transaction."}

    if received < expected_amount * (1 - PAYMENT_TOLERANCE):
        return {
            "ok": False,
            "reason": f"Montant insuffisant : reçu **{received:.8f} BTC**, attendu **{expected_amount:.8f} BTC**.",
        }

    if confirmations < MIN_CONFIRMATIONS_BTC:
        return {
            "ok": False,
            "pending": True,
            "reason": f"Transaction détectée mais non confirmée ({confirmations} confirmation(s)). Réessaie dans quelques minutes.",
        }

    return {"ok": True, "amount": received, "confirmations": confirmations}


async def check_eth_tx(txid: str, expected_amount: float, wallet: str) -> dict:
    """Vérifie une transaction Ethereum native (ETH) via l'API Etherscan."""
    if not ETHERSCAN_API_KEY:
        return {"ok": False, "reason": "Vérification ETH indisponible : clé Etherscan non configurée."}

    base = "https://api.etherscan.io/api"
    async with aiohttp.ClientSession() as session:
        params = {
            "module": "proxy", "action": "eth_getTransactionByHash",
            "txhash": txid, "apikey": ETHERSCAN_API_KEY,
        }
        async with session.get(base, params=params) as r:
            data = await r.json()
        tx = data.get("result")
        if not tx:
            return {"ok": False, "reason": "Transaction introuvable. Vérifie le lien."}

        if (tx.get("to") or "").lower() != wallet.lower():
            return {"ok": False, "reason": "Cette transaction ne va pas vers l'adresse attendue."}

        received = int(tx["value"], 16) / 1e18

        async with session.get(base, params={
            "module": "proxy", "action": "eth_blockNumber", "apikey": ETHERSCAN_API_KEY
        }) as r2:
            current_block = int((await r2.json())["result"], 16)
        tx_block = int(tx["blockNumber"], 16) if tx.get("blockNumber") else None
        confirmations = (current_block - tx_block) if tx_block else 0

    if received < expected_amount * (1 - PAYMENT_TOLERANCE):
        return {
            "ok": False,
            "reason": f"Montant insuffisant : reçu **{received:.6f} ETH**, attendu **{expected_amount:.6f} ETH**.",
        }

    if confirmations < MIN_CONFIRMATIONS_ETH:
        return {
            "ok": False,
            "pending": True,
            "reason": f"Transaction détectée mais peu confirmée ({confirmations} bloc(s)). Réessaie dans quelques minutes.",
        }

    return {"ok": True, "amount": received, "confirmations": confirmations}


async def check_usdt_tx(txid: str, expected_amount: float, wallet: str) -> dict:
    """Vérifie un transfert de token USDT (ERC-20) via les logs de la transaction."""
    if not ETHERSCAN_API_KEY:
        return {"ok": False, "reason": "Vérification USDT indisponible : clé Etherscan non configurée."}

    base = "https://api.etherscan.io/api"
    async with aiohttp.ClientSession() as session:
        params = {
            "module": "proxy", "action": "eth_getTransactionReceipt",
            "txhash": txid, "apikey": ETHERSCAN_API_KEY,
        }
        async with session.get(base, params=params) as r:
            data = await r.json()
        receipt = data.get("result")
        if not receipt:
            return {"ok": False, "reason": "Transaction introuvable. Vérifie le lien."}

        received = 0.0
        found_wallet = False
        for log in receipt.get("logs", []):
            if log.get("address", "").lower() != USDT_CONTRACT:
                continue
            topics = log.get("topics", [])
            if len(topics) < 3 or topics[0].lower() != TRANSFER_TOPIC:
                continue
            to_addr = "0x" + topics[2][-40:]
            if to_addr.lower() != wallet.lower():
                continue
            found_wallet = True
            received += int(log["data"], 16) / 1e6  # USDT = 6 décimales

        if not found_wallet:
            return {"ok": False, "reason": "Aucun transfert USDT vers l'adresse attendue dans cette transaction."}

        status_ok = receipt.get("status") == "0x1"
        async with session.get(base, params={
            "module": "proxy", "action": "eth_blockNumber", "apikey": ETHERSCAN_API_KEY
        }) as r2:
            current_block = int((await r2.json())["result"], 16)
        tx_block = int(receipt["blockNumber"], 16) if receipt.get("blockNumber") else None
        confirmations = (current_block - tx_block) if tx_block else 0

    if not status_ok:
        return {"ok": False, "reason": "Cette transaction a échoué sur la blockchain (statut reverted)."}

    if received < expected_amount * (1 - PAYMENT_TOLERANCE):
        return {
            "ok": False,
            "reason": f"Montant insuffisant : reçu **{received:.2f} USDT**, attendu **{expected_amount:.2f} USDT**.",
        }

    if confirmations < MIN_CONFIRMATIONS_ETH:
        return {
            "ok": False,
            "pending": True,
            "reason": f"Transaction détectée mais peu confirmée ({confirmations} bloc(s)). Réessaie dans quelques minutes.",
        }

    return {"ok": True, "amount": received, "confirmations": confirmations}


CHECKERS = {"BTC": check_btc_tx, "ETH": check_eth_tx, "USDT_ERC20": check_usdt_tx}
CURRENCY_LABELS = {"BTC": "Bitcoin (BTC)", "ETH": "Ethereum (ETH)", "USDT_ERC20": "USDT (réseau ERC-20)"}


class PaymentModal(discord.ui.Modal, title="Confirmer mon paiement"):
    tx_link = discord.ui.TextInput(
        label="Lien ou hash de la transaction",
        placeholder="https://blockstream.info/tx/xxxxxxxx... ou juste le hash",
        style=discord.TextStyle.short,
        required=True,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        conf = guild_conf(interaction.guild.id)
        payment = conf.get("payments", {}).get(str(interaction.channel.id))
        if not payment:
            return await interaction.followup.send(
                "⚠️ Aucune demande de paiement active dans ce ticket. Un membre du staff doit "
                "d'abord utiliser `/request_payment`.",
                ephemeral=True,
            )

        currency = payment["currency"]
        expected = payment["amount"]
        wallet = WALLETS[currency]
        txid = extract_txid(self.tx_link.value)

        checker = CHECKERS[currency]
        try:
            result = await checker(txid, expected, wallet)
        except Exception as e:
            print(f"[ERREUR paiement] {e!r}")
            return await interaction.followup.send(
                "⚠️ Erreur lors de la vérification (API indisponible). Réessaie dans une minute "
                "ou attends la validation manuelle du staff.",
                ephemeral=True,
            )

        role_admin = get_role(interaction.guild, R_ADMIN)
        ping = role_admin.mention if role_admin else ""

        if result["ok"]:
            conf["payments"][str(interaction.channel.id)]["status"] = "verified"
            conf["payments"][str(interaction.channel.id)]["txid"] = txid
            save_data(DATA)

            e = discord.Embed(
                title="✅ Paiement vérifié automatiquement",
                description=(
                    f"**Devise :** {CURRENCY_LABELS[currency]}\n"
                    f"**Montant reçu :** `{result['amount']}` (attendu : `{expected}`)\n"
                    f"**Confirmations :** {result['confirmations']}\n"
                    f"**Transaction :** `{txid}`"
                ),
                colour=C_MEMBRE,
            )
            await interaction.followup.send(
                content=f"{ping} — paiement vérifié, il ne reste plus qu'à confirmer manuellement.",
                embed=e,
                view=PaymentConfirmView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            await log_event(
                interaction.guild,
                discord.Embed(
                    title="💰 Paiement crypto vérifié",
                    description=f"{interaction.user.mention} • {CURRENCY_LABELS[currency]} • `{result['amount']}`\n{interaction.channel.mention}",
                    colour=C_MEMBRE,
                ),
            )
        else:
            colour = 0xE67E22 if result.get("pending") else C_BOOSTER
            e = discord.Embed(
                title="⏳ En attente" if result.get("pending") else "❌ Vérification échouée",
                description=result["reason"],
                colour=colour,
            )
            await interaction.followup.send(embed=e)
            if not result.get("pending"):
                await interaction.channel.send(
                    f"{ping} — échec de vérification automatique, un contrôle manuel est nécessaire."
                )


class PaymentRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="J'ai payé",
        emoji="💸",
        style=discord.ButtonStyle.success,
        custom_id="persistent:payment_paid",
    )
    async def paid(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = guild_conf(interaction.guild.id)
        payment = conf.get("payments", {}).get(str(interaction.channel.id))
        if not payment:
            return await interaction.response.send_message(
                "⚠️ Aucune demande de paiement active ici.", ephemeral=True
            )
        if payment.get("status") == "confirmed":
            return await interaction.response.send_message(
                "✅ Ce paiement a déjà été confirmé par le staff.", ephemeral=True
            )
        await interaction.response.send_modal(PaymentModal())


class PaymentConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Confirmer et débloquer (staff)",
        emoji="🔓",
        style=discord.ButtonStyle.primary,
        custom_id="persistent:payment_confirm",
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_admin = get_role(interaction.guild, R_ADMIN)
        if not role_admin or role_admin not in interaction.user.roles:
            return await interaction.response.send_message(
                "⛔ Réservé au staff.", ephemeral=True
            )

        conf = guild_conf(interaction.guild.id)
        payment = conf.get("payments", {}).get(str(interaction.channel.id))
        if payment:
            payment["status"] = "confirmed"
            save_data(DATA)

        button.disabled = True
        button.label = f"Confirmé par {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            f"🔓 {interaction.user.mention} a confirmé le paiement. Le service peut démarrer."
        )


# ======================================================================
#  VUES — TICKETS
# ======================================================================

TICKET_TYPES = {
    "boost": {
        "label": "Commander un boost",
        "label_en": "Order a boost",
        "emoji": "🚀",
        "desc": "Faire monter ton rang par un booster vérifié",
        "desc_en": "Get your rank raised by a verified booster",
        "prefix": "boost",
        "intro": (
            "Merci pour ta commande ! Pour aller vite, indique-nous :\n"
            "> **1.** Le jeu concerné\n"
            "> **2.** Ton rang actuel et le rang visé\n"
            "> **3.** Ta région / serveur\n"
            "> **4.** Le mode souhaité (compte partagé ou duo)\n\n"
            "Un membre du staff arrive pour te chiffrer ça."
        ),
        "intro_en": (
            "Thanks for your order! To speed things up, please tell us:\n"
            "> **1.** The game\n"
            "> **2.** Your current rank and target rank\n"
            "> **3.** Your region / server\n"
            "> **4.** Preferred mode (account sharing or duo)\n\n"
            "A staff member will be with you shortly with a quote."
        ),
    },
    "booster": {
        "label": "Devenir Booster",
        "label_en": "Become a Booster",
        "emoji": "💪",
        "desc": "Rejoindre l'équipe et gagner de l'argent",
        "desc_en": "Join the team and earn money",
        "prefix": "booster",
        "intro": (
            "Content de voir que tu veux rejoindre l'équipe. Envoie-nous :\n"
            "> **1.** Ton rang actuel + preuve (screenshot / tracker)\n"
            "> **2.** Ton historique de peak sur les dernières saisons\n"
            "> **3.** Tes disponibilités hebdomadaires\n"
            "> **4.** Tes éventuelles expériences de boost précédentes\n\n"
            "Un recruteur va prendre ton dossier en charge."
        ),
        "intro_en": (
            "Glad you want to join the team. Please send us:\n"
            "> **1.** Your current rank + proof (screenshot / tracker)\n"
            "> **2.** Your peak history over recent seasons\n"
            "> **3.** Your weekly availability\n"
            "> **4.** Any previous boosting experience\n\n"
            "A recruiter will pick up your application."
        ),
    },
    "staff": {
        "label": "Candidature Staff",
        "label_en": "Staff Application",
        "emoji": "🛡️",
        "desc": "Postuler pour un poste de modération / support",
        "desc_en": "Apply for a moderation / support position",
        "prefix": "staff",
        "intro": (
            "Merci pour ta candidature. Détaille-nous :\n"
            "> **1.** Ton âge et ton fuseau horaire\n"
            "> **2.** Tes expériences de modération\n"
            "> **3.** Ton temps de présence quotidien estimé\n"
            "> **4.** Pourquoi toi plutôt qu'un autre\n\n"
            "Prends le temps de bien répondre, c'est ce qu'on regarde en premier."
        ),
        "intro_en": (
            "Thanks for applying. Please detail:\n"
            "> **1.** Your age and time zone\n"
            "> **2.** Your moderation experience\n"
            "> **3.** Your estimated daily availability\n"
            "> **4.** Why you rather than someone else\n\n"
            "Take your time answering — that's what we look at first."
        ),
    },
}


async def _create_ticket(interaction: discord.Interaction, kind: str, lang: str):
    """Logique commune de création de ticket, dans la langue demandée."""
    cfg = TICKET_TYPES[kind]
    guild = interaction.guild
    member = interaction.user
    is_fr = lang == "fr"

    existing = discord.utils.find(
        lambda c: c.topic == f"ticket-owner:{member.id}", guild.text_channels
    )
    if existing:
        return await interaction.followup.send(
            (f"⚠️ Tu as déjà un ticket ouvert : {existing.mention}" if is_fr
             else f"⚠️ You already have an open ticket: {existing.mention}"),
            ephemeral=True,
        )

    conf = guild_conf(guild.id)
    key = "ticket_category_fr" if is_fr else "ticket_category_en"
    category = guild.get_channel(conf.get(key, 0))
    if category is None:
        return await interaction.followup.send(
            ("⚠️ Catégorie de tickets introuvable. Relance `/setup`." if is_fr
             else "⚠️ Ticket category not found. Run `/setup` again."),
            ephemeral=True,
        )

    role_admin = get_role(guild, R_ADMIN)
    role_booster = get_role(guild, R_BOOSTER)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True
        ),
    }
    if role_admin:
        overwrites[role_admin] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_messages=True
        )
    if role_booster and kind == "boost":
        overwrites[role_booster] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True
        )

    DATA["ticket_counter"] += 1
    number = DATA["ticket_counter"]
    save_data(DATA)

    channel = await guild.create_text_channel(
        name=f"{cfg['emoji']}・{cfg['prefix']}-{number:04d}",
        category=category,
        overwrites=overwrites,
        topic=f"ticket-owner:{member.id}",
        reason=f"Ticket {kind} ({lang}) ouvert par {member}",
    )

    embed = discord.Embed(
        title=f"{cfg['emoji']}  {cfg['label'] if is_fr else cfg['label_en']}  •  Ticket #{number:04d}",
        description=cfg["intro"] if is_fr else cfg["intro_en"],
        colour=C_CLIENT,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(
        text=(f"Ouvert par {member}" if is_fr else f"Opened by {member}"),
        icon_url=member.display_avatar.url,
    )

    ping = role_admin.mention if role_admin else ""
    await channel.send(
        content=f"{member.mention} {ping}",
        embed=embed,
        view=TicketControlView(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )

    await interaction.followup.send(
        (f"✅ Ton ticket a été créé : {channel.mention}" if is_fr
         else f"✅ Your ticket has been created: {channel.mention}"),
        ephemeral=True,
    )

    await log_event(
        guild,
        discord.Embed(
            title="🎟️ Ticket ouvert",
            description=f"**{cfg['label']}** ({lang.upper()}) — {channel.mention}\nPar {member.mention}",
            colour=C_CLIENT,
        ),
    )


class TicketPanelView(discord.ui.View):
    """Panneau francophone."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="📩 Sélectionne le motif de ton ticket…",
        custom_id="persistent:ticket_select",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label=v["label"], value=k, emoji=v["emoji"], description=v["desc"]
            )
            for k, v in TICKET_TYPES.items()
        ],
    )
    async def select_ticket(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await _create_ticket(interaction, select.values[0], "fr")


class TicketPanelViewEN(discord.ui.View):
    """English panel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="📩 Select the reason for your ticket…",
        custom_id="persistent:ticket_select_en",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label=v["label_en"], value=k, emoji=v["emoji"], description=v["desc_en"]
            )
            for k, v in TICKET_TYPES.items()
        ],
    )
    async def select_ticket_en(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await _create_ticket(interaction, select.values[0], "en")


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Prendre en charge",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="persistent:ticket_claim",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_admin = get_role(interaction.guild, R_ADMIN)
        role_booster = get_role(interaction.guild, R_BOOSTER)
        allowed = {r for r in (role_admin, role_booster) if r}

        if not allowed & set(interaction.user.roles):
            return await interaction.response.send_message(
                "⛔ Réservé au staff et aux boosters.", ephemeral=True
            )

        button.disabled = True
        button.label = f"Pris en charge par {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            f"🙋 {interaction.user.mention} prend ce ticket en charge."
        )

    @discord.ui.button(
        label="Fermer le ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="persistent:ticket_close",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=discord.Embed(
                description="⚠️ **Confirmer la fermeture ?** Le salon sera supprimé dans 5 secondes.",
                colour=C_BOOSTER,
            ),
            view=ConfirmCloseView(interaction.user),
            ephemeral=False,
        )


class ConfirmCloseView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.button(label="Confirmer", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🔒 Fermeture du ticket…", embed=None, view=None
        )
        await log_event(
            interaction.guild,
            discord.Embed(
                title="🔒 Ticket fermé",
                description=f"`#{interaction.channel.name}` fermé par {interaction.user.mention}",
                colour=C_ADMIN,
            ),
        )
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket fermé par {interaction.user}")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Annuler", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Fermeture annulée.", embed=None, view=None
        )


# ======================================================================
#  ÉVÉNEMENTS — ARRIVÉE / ANTI-RAID
# ======================================================================


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # --- Détection de vague d'arrivées ---
    log = bot.join_log.setdefault(guild.id, deque())
    now = time.time()
    log.append(now)
    while log and now - log[0] > RAID_JOIN_WINDOW:
        log.popleft()

    if len(log) >= RAID_JOIN_COUNT and bot.lockdown.get(guild.id, 0) < now:
        bot.lockdown[guild.id] = now + LOCKDOWN_DURATION
        await log_event(
            guild,
            discord.Embed(
                title="🛡️ LOCKDOWN ANTI-RAID ACTIVÉ",
                description=(
                    f"**{len(log)} arrivées** en {RAID_JOIN_WINDOW}s détectées.\n"
                    f"Vérifications bloquées pendant **{LOCKDOWN_DURATION // 60} minutes**.\n"
                    "Pense à passer le niveau de vérification du serveur sur `Élevé`."
                ),
                colour=C_BOOSTER,
            ),
        )

    # --- Attribution du rôle non vérifié ---
    role_unverified = get_role(guild, R_UNVERIFIED)
    if role_unverified:
        try:
            await member.add_roles(role_unverified, reason="Nouvelle arrivée")
        except discord.Forbidden:
            pass

    age = (discord.utils.utcnow() - member.created_at).days
    await log_event(
        guild,
        discord.Embed(
            title="📥 Arrivée",
            description=f"{member.mention} • `{member}`\nCompte âgé de **{age} jour(s)**.",
            colour=C_MEMBRE if age >= MIN_ACCOUNT_AGE_DAYS else 0xE67E22,
        ),
    )


# ======================================================================
#  COMMANDE /setup — CONSTRUCTION COMPLÈTE DU SERVEUR
# ======================================================================


@bot.tree.command(name="setup", description="Construit l'intégralité du serveur de boost.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.send_message(
        "⚙️ Construction du serveur en cours, patiente…", ephemeral=True
    )

    # ------------------------------------------------------------------
    #  1. RÔLES
    # ------------------------------------------------------------------
    perms_admin = discord.Permissions(administrator=True)
    perms_booster = discord.Permissions(
        view_channel=True, send_messages=True, read_message_history=True,
        attach_files=True, embed_links=True, add_reactions=True,
        connect=True, speak=True, manage_messages=True,
    )
    perms_membre = discord.Permissions(
        view_channel=True, send_messages=True, read_message_history=True,
        attach_files=True, embed_links=True, add_reactions=True,
        connect=True, speak=True,
    )
    perms_none = discord.Permissions.none()

    role_specs = [
        (R_ADMIN, C_ADMIN, perms_admin, True),
        (R_BOOSTER, C_BOOSTER, perms_booster, True),
        (R_CLIENT, C_CLIENT, perms_membre, True),
        (R_MEMBRE, C_MEMBRE, perms_membre, False),
        (R_FR, C_FR, perms_none, False),
        (R_EN, C_EN, perms_none, False),
        (R_UNVERIFIED, C_UNVERIFIED, perms_none, False),
    ]

    roles: dict[str, discord.Role] = {}
    for name, colour, perms, hoist in role_specs:
        existing = get_role(guild, name)
        if existing:
            roles[name] = existing
            continue
        roles[name] = await guild.create_role(
            name=name,
            colour=discord.Colour(colour),
            permissions=perms,
            hoist=hoist,
            mentionable=True,
            reason="Setup automatique",
        )
        await asyncio.sleep(0.3)

    r_admin = roles[R_ADMIN]
    r_booster = roles[R_BOOSTER]
    r_client = roles[R_CLIENT]
    r_membre = roles[R_MEMBRE]
    r_fr = roles[R_FR]
    r_en = roles[R_EN]
    r_unverif = roles[R_UNVERIFIED]

    # ------------------------------------------------------------------
    #  2. @everyone verrouillé
    # ------------------------------------------------------------------
    try:
        await guild.default_role.edit(
            permissions=discord.Permissions(
                view_channel=False,
                read_message_history=False,
                send_messages=False,
                connect=False,
            ),
            reason="Setup : verrouillage global",
        )
    except discord.Forbidden:
        pass

    # ------------------------------------------------------------------
    #  3. MODÈLES DE PERMISSIONS
    # ------------------------------------------------------------------
    DENY = discord.PermissionOverwrite(view_channel=False)
    SEE = discord.PermissionOverwrite(view_channel=True, read_message_history=True)
    TALK = discord.PermissionOverwrite(
        view_channel=True, read_message_history=True, send_messages=True,
        attach_files=True, embed_links=True, add_reactions=True,
    )
    READONLY = discord.PermissionOverwrite(
        view_channel=True, read_message_history=True, send_messages=False,
        add_reactions=True,
    )
    STAFF = discord.PermissionOverwrite(
        view_channel=True, read_message_history=True, send_messages=True,
        manage_messages=True, connect=True, speak=True,
    )

    def lang_ow(role_lang, mode):
        """Construit les permissions d'une catégorie réservée à une langue."""
        perm = {"read": READONLY, "talk": TALK, "see": SEE}[mode]
        return {
            guild.default_role: DENY,
            r_unverif: DENY,
            r_fr: DENY,
            r_en: DENY,
            role_lang: perm,
            r_admin: STAFF,
        }

    ow_verify = {
        guild.default_role: DENY,
        r_unverif: discord.PermissionOverwrite(
            view_channel=True, read_message_history=True, send_messages=False
        ),
        r_fr: DENY,
        r_en: DENY,
        r_admin: SEE,
    }
    ow_admin = {
        guild.default_role: DENY,
        r_unverif: DENY, r_membre: DENY, r_client: DENY,
        r_fr: DENY, r_en: DENY, r_booster: DENY,
        r_admin: STAFF,
    }

    def ticket_ow(role_lang):
        ow = lang_ow(role_lang, "read")
        ow[r_booster] = SEE
        return ow

    # ------------------------------------------------------------------
    #  4. CATÉGORIES & SALONS
    # ------------------------------------------------------------------
    async def make_category(name, overwrites):
        existing = discord.utils.get(guild.categories, name=name)
        if existing:
            await existing.edit(overwrites=overwrites)
            return existing
        cat = await guild.create_category(name, overwrites=overwrites, reason="Setup")
        await asyncio.sleep(0.3)
        return cat

    async def make_text(category, name, overwrites, topic=None):
        existing = discord.utils.get(guild.text_channels, name=name.lower())
        if existing:
            return existing
        ch = await guild.create_text_channel(
            name, category=category, overwrites=overwrites, topic=topic, reason="Setup"
        )
        await asyncio.sleep(0.3)
        return ch

    async def make_voice(category, name, overwrites):
        existing = discord.utils.get(guild.voice_channels, name=name)
        if existing:
            return existing
        ch = await guild.create_voice_channel(
            name, category=category, overwrites=overwrites, reason="Setup"
        )
        await asyncio.sleep(0.3)
        return ch

    # --- 🔐 VÉRIFICATION (commun, visible par les non vérifiés) ---
    cat_verif = await make_category("🔐・VERIFICATION", ow_verify)
    ch_verif = await make_text(cat_verif, "╰✅・vérification-verification", ow_verify)

    # ================= FRANÇAIS =================
    cat_info_fr = await make_category("📋・INFORMATION [FR]", lang_ow(r_fr, "read"))
    ch_welcome_fr = await make_text(cat_info_fr, "├👋・bienvenue", lang_ow(r_fr, "read"))
    ch_rules_fr = await make_text(cat_info_fr, "├📜・règlement", lang_ow(r_fr, "read"))
    ch_vouch_fr = await make_text(cat_info_fr, "╰⭐・vouches-fr", lang_ow(r_fr, "read"))

    cat_gen_fr = await make_category("💬・GÉNÉRAL [FR]", lang_ow(r_fr, "talk"))
    await make_text(cat_gen_fr, "├🗨️・discussion", lang_ow(r_fr, "talk"))
    await make_text(cat_gen_fr, "├📸・média", lang_ow(r_fr, "talk"))
    await make_text(cat_gen_fr, "╰🌐・réseaux", lang_ow(r_fr, "read"))

    cat_ticket_fr = await make_category("🎫・TICKET BOOST [FR]", ticket_ow(r_fr))
    ch_price_fr = await make_text(cat_ticket_fr, "├💲・tarification", ticket_ow(r_fr))
    ch_open_fr = await make_text(cat_ticket_fr, "╰🎟️・créer-un-ticket", ticket_ow(r_fr))

    # ================= ENGLISH =================
    cat_info_en = await make_category("📋・INFORMATION [EN]", lang_ow(r_en, "read"))
    ch_welcome_en = await make_text(cat_info_en, "├👋・welcome", lang_ow(r_en, "read"))
    ch_rules_en = await make_text(cat_info_en, "├📜・rules", lang_ow(r_en, "read"))
    ch_vouch_en = await make_text(cat_info_en, "╰⭐・vouches-en", lang_ow(r_en, "read"))

    cat_gen_en = await make_category("💬・GENERAL [EN]", lang_ow(r_en, "talk"))
    await make_text(cat_gen_en, "├🗨️・chat", lang_ow(r_en, "talk"))
    await make_text(cat_gen_en, "├📸・media", lang_ow(r_en, "talk"))
    await make_text(cat_gen_en, "╰🌐・socials", lang_ow(r_en, "read"))

    cat_ticket_en = await make_category("🎫・BOOST TICKETS [EN]", ticket_ow(r_en))
    ch_price_en = await make_text(cat_ticket_en, "├💲・pricing", ticket_ow(r_en))
    ch_open_en = await make_text(cat_ticket_en, "╰🎟️・open-a-ticket", ticket_ow(r_en))

    # ================= ADMIN (français uniquement) =================
    cat_admin = await make_category("🛠️・ADMIN", ow_admin)
    ch_staff = await make_text(cat_admin, "├🔒・staff-chat", ow_admin)
    ch_logs = await make_text(cat_admin, "├📊・logs", ow_admin)
    await make_voice(cat_admin, "╰🔊・Vocal Staff", ow_admin)

    # ------------------------------------------------------------------
    #  5. SAUVEGARDE DE LA CONFIG
    # ------------------------------------------------------------------
    conf = guild_conf(guild.id)
    conf.update({
        "ticket_category_fr": cat_ticket_fr.id,
        "ticket_category_en": cat_ticket_en.id,
        "log_channel": ch_logs.id,
        "verify_channel": ch_verif.id,
    })
    save_data(DATA)

    # ------------------------------------------------------------------
    #  6. MESSAGES
    # ------------------------------------------------------------------

    # --- Vérification (bilingue) ---
    e = discord.Embed(
        title="🔐  VÉRIFICATION  •  VERIFICATION",
        description=(
            f"**🇫🇷 Bienvenue sur {guild.name}**\n"
            "Choisis ta langue ci-dessous pour accéder au serveur. "
            "Tu ne verras que les salons de la langue choisie.\n"
            f"> ⏳ Ton compte doit avoir au moins **{MIN_ACCOUNT_AGE_DAYS} jours**.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"**🇬🇧 Welcome to {guild.name}**\n"
            "Pick your language below to unlock the server. "
            "You will only see the channels for the language you choose.\n"
            f"> ⏳ Your account must be at least **{MIN_ACCOUNT_AGE_DAYS} days** old."
        ),
        colour=C_MEMBRE,
    )
    e.set_footer(text="Protection anti-raid active • Anti-raid protection enabled")
    await ch_verif.send(embed=e, view=VerifyView())

    # --- Bienvenue FR ---
    e = discord.Embed(
        title=f"👋  Bienvenue sur {guild.name}",
        description=(
            "Tu viens d'arriver dans **le serveur de boost de rang** le plus direct du marché.\n\n"
            "**Ce qu'on fait ici :**\n"
            "> 🚀 Boost de rang par des joueurs vérifiés, en compte partagé ou en duo\n"
            "> ⚡ Prise en charge rapide, suivi en direct dans ton ticket\n"
            "> 🔒 Discrétion totale sur chaque commande\n"
            "> ⭐ Des dizaines de vouches consultables publiquement\n\n"
            "**Pour démarrer :**\n"
            f"> **1.** Lis le {ch_rules_fr.mention}\n"
            f"> **2.** Consulte les tarifs dans {ch_price_fr.mention}\n"
            f"> **3.** Ouvre un ticket dans {ch_open_fr.mention}\n\n"
            "Bon boost. 🏆"
        ),
        colour=C_MEMBRE,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    await ch_welcome_fr.send(embed=e)

    # --- Welcome EN ---
    e = discord.Embed(
        title=f"👋  Welcome to {guild.name}",
        description=(
            "You've just joined the most straightforward **rank boosting server** around.\n\n"
            "**What we do here:**\n"
            "> 🚀 Rank boosting by verified players, account sharing or duo\n"
            "> ⚡ Fast pickup, live updates inside your ticket\n"
            "> 🔒 Full discretion on every order\n"
            "> ⭐ Dozens of publicly available vouches\n\n"
            "**Getting started:**\n"
            f"> **1.** Read the {ch_rules_en.mention}\n"
            f"> **2.** Check the rates in {ch_price_en.mention}\n"
            f"> **3.** Open a ticket in {ch_open_en.mention}\n\n"
            "Enjoy the climb. 🏆"
        ),
        colour=C_MEMBRE,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    await ch_welcome_en.send(embed=e)

    # --- Règlement FR ---
    e = discord.Embed(
        title="📜  RÈGLEMENT DU SERVEUR",
        description="Le fait de rester sur le serveur vaut acceptation de ces règles.",
        colour=C_ADMIN,
    )
    e.add_field(name="1️⃣  Respect", value="Aucune insulte, aucun propos discriminatoire, aucun harcèlement. Sanction immédiate.", inline=False)
    e.add_field(name="2️⃣  Pas de spam", value="Ni en salon, ni en MP. La pub pour d'autres services est bannissable.", inline=False)
    e.add_field(name="3️⃣  Transactions en ticket uniquement", value="Toute commande passe par un ticket officiel. Un paiement effectué en dehors d'un ticket **ne sera jamais couvert** par le staff.", inline=False)
    e.add_field(name="4️⃣  Méfie-toi des usurpateurs", value="Le staff ne te contactera **jamais en premier** en MP pour te réclamer un paiement.", inline=False)
    e.add_field(name="5️⃣  Litiges", value="Un désaccord se règle dans le ticket concerné, calmement, avec le staff. Pas en public.", inline=False)
    e.add_field(name="6️⃣  CGU Discord", value="Les [Conditions d'utilisation](https://discord.com/terms) s'appliquent. 13 ans minimum.", inline=False)
    await ch_rules_fr.send(embed=e)

    # --- Rules EN ---
    e = discord.Embed(
        title="📜  SERVER RULES",
        description="Staying on this server means you accept these rules.",
        colour=C_ADMIN,
    )
    e.add_field(name="1️⃣  Respect", value="No insults, no discriminatory language, no harassment. Immediate sanction.", inline=False)
    e.add_field(name="2️⃣  No spam", value="Neither in channels nor in DMs. Advertising other services is a bannable offence.", inline=False)
    e.add_field(name="3️⃣  Tickets only for transactions", value="Every order goes through an official ticket. Any payment made outside a ticket **will never be covered** by staff.", inline=False)
    e.add_field(name="4️⃣  Beware of impersonators", value="Staff will **never DM you first** asking for a payment. Always check the person's role.", inline=False)
    e.add_field(name="5️⃣  Disputes", value="Disagreements are settled inside the relevant ticket, calmly, with staff. Not in public.", inline=False)
    e.add_field(name="6️⃣  Discord ToS", value="Discord's [Terms of Service](https://discord.com/terms) apply. 13+ only.", inline=False)
    await ch_rules_en.send(embed=e)

    # --- Vouches FR / EN ---
    await ch_vouch_fr.send(embed=discord.Embed(
        title="⭐  VOUCHES & RETOURS CLIENTS",
        description=(
            "Ce salon regroupe les retours de nos clients.\n\n"
            "**Format attendu après une commande :**\n"
            "```\nBooster  : @pseudo\nService  : Boost Or 3 → Platine 2\nDurée    : 2 jours\n"
            "Note     : ⭐⭐⭐⭐⭐\nAvis     : Rapide et propre, aucun souci.\n```\n"
            "🚫 Tout faux vouch entraîne un bannissement définitif."
        ),
        colour=C_CLIENT,
    ))
    await ch_vouch_en.send(embed=discord.Embed(
        title="⭐  VOUCHES & CUSTOMER FEEDBACK",
        description=(
            "This channel collects feedback from our customers.\n\n"
            "**Expected format after an order:**\n"
            "```\nBooster  : @username\nService  : Boost Gold 3 → Platinum 2\nDuration : 2 days\n"
            "Rating   : ⭐⭐⭐⭐⭐\nReview   : Fast and clean, no issues.\n```\n"
            "🚫 Any fake vouch results in a permanent ban."
        ),
        colour=C_CLIENT,
    ))

    # --- Tarification FR ---
    e = discord.Embed(
        title="💲  GRILLE TARIFAIRE",
        description=(
            "Les tarifs sont calculés en fonction du **nombre de RR** à parcourir "
            "entre ton rang actuel et ton objectif.\n"
            "Un devis exact t'est donné dans ton ticket, options comprises.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        colour=C_CLIENT,
    )
    e.add_field(
        name="🥉  Fer • Bronze • Argent",
        value=(
            f"{EMO['iron1']}{EMO['iron2']}{EMO['iron3']}"
            f"{EMO['bronze1']}{EMO['bronze2']}{EMO['bronze3']}"
            f"{EMO['silver1']}{EMO['silver2']}{EMO['silver3']}\n"
            "```\n"
            "Fer 1    → Bronze 1    15e\n"
            "Bronze 1 → Argent 1    18e\n"
            "Argent 1 → Or 1        24e\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="🥈  Or • Platine • Diamant",
        value=(
            f"{EMO['gold1']}{EMO['gold2']}{EMO['gold3']}"
            f"{EMO['plat1']}{EMO['plat2']}{EMO['plat3']}"
            f"{EMO['dia1']}{EMO['dia2']}{EMO['dia3']}\n"
            "```\n"
            "Or 1      → Platine 1   36e\n"
            "Platine 1 → Diamant 1   54e\n"
            "Diamant 1 → Ascendant 1 72e\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="🥇  Ascendant • Immortel • Radiant",
        value=(
            f"{EMO['asc1']}{EMO['asc2']}{EMO['asc3']}"
            f"{EMO['immo1']}{EMO['immo2']}{EMO['immo3']}{EMO['radiant']}\n"
            "```\n"
            "Ascendant 1 → Immortel 1  90e\n"
            "Immortel 1  → Immortel 3  90e\n"
            "Immortel 3  → Radiant     sur devis\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="➕  Options",
        value=(
            "> 🤝 **Duo boost** — +40 %\n"
            "> ⚡ **Priorité express** — +20 %\n"
            "> 📺 **Stream privé de la session** — +10 %\n"
            "> 🎯 **Choix des agents** — offert"
        ),
        inline=False,
    )
    e.add_field(
        name="💳  Paiements acceptés",
        value=(
            f"> {EMO['paypal']} **PayPal** — Amis & Famille uniquement\n"
            f"> {EMO['btc']} **Bitcoin** (BTC)\n"
            f"> {EMO['eth']} **Ethereum** (ETH)\n"
            f"> {EMO['usdt']} **USDT** — réseau ERC-20 uniquement"
        ),
        inline=False,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Aucun paiement en dehors d'un ticket officiel • Prix indicatifs")
    await ch_price_fr.send(embed=e)

    # --- Pricing EN ---
    e = discord.Embed(
        title="💲  PRICING",
        description=(
            "Prices are based on the **amount of RR** between your current rank "
            "and your target.\n"
            "You'll get an exact quote inside your ticket, options included.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        colour=C_CLIENT,
    )
    e.add_field(
        name="🥉  Iron • Bronze • Silver",
        value=(
            f"{EMO['iron1']}{EMO['iron2']}{EMO['iron3']}"
            f"{EMO['bronze1']}{EMO['bronze2']}{EMO['bronze3']}"
            f"{EMO['silver1']}{EMO['silver2']}{EMO['silver3']}\n"
            "```\n"
            "Iron 1   → Bronze 1   17,5usd\n"
            "Bronze 1 → Silver 1   20,5usd\n"
            "Silver 1 → Gold 1     27,5usd\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="🥈  Gold • Platinum • Diamond",
        value=(
            f"{EMO['gold1']}{EMO['gold2']}{EMO['gold3']}"
            f"{EMO['plat1']}{EMO['plat2']}{EMO['plat3']}"
            f"{EMO['dia1']}{EMO['dia2']}{EMO['dia3']}\n"
            "```\n"
            "Gold 1     → Platinum 1  41,5usd\n"
            "Platinum 1 → Diamond 1   62,5usd\n"
            "Diamond 1  → Ascendant 1 83,5usd\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="🥇  Ascendant • Immortal • Radiant",
        value=(
            f"{EMO['asc1']}{EMO['asc2']}{EMO['asc3']}"
            f"{EMO['immo1']}{EMO['immo2']}{EMO['immo3']}{EMO['radiant']}\n"
            "```\n"
            "Ascendant 1 → Immortal 1  104usd\n"
            "Immortal 1  → Immortal 3  104usd\n"
            "Immortal 3  → Radiant     on request\n"
            "```"
        ),
        inline=False,
    )
    e.add_field(
        name="➕  Options",
        value=(
            "> 🤝 **Duo boost** — +40 %\n"
            "> ⚡ **Express priority** — +20 %\n"
            "> 📺 **Private stream of the session** — +10 %\n"
            "> 🎯 **Agent selection** — free"
        ),
        inline=False,
    )
    e.add_field(
        name="💳  Accepted payments",
        value=(
            f"> {EMO['paypal']} **PayPal** — Friends & Family only\n"
            f"> {EMO['btc']} **Bitcoin** (BTC)\n"
            f"> {EMO['eth']} **Ethereum** (ETH)\n"
            f"> {EMO['usdt']} **USDT** — ERC-20 network only"
        ),
        inline=False,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="No payment outside an official ticket • Indicative prices")
    await ch_price_en.send(embed=e)

    # --- Panneau tickets FR ---
    e = discord.Embed(
        title="🎟️  OUVRIR UN TICKET",
        description=(
            "**C'est ici que tout commence.**\n\n"
            "Sélectionne ton motif dans le menu ci-dessous. Un salon privé sera créé "
            "instantanément entre toi et le staff.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🚀 **Commander un boost**\n"
            "> Prépare ton rang actuel, le rang visé et ta région.\n\n"
            "💪 **Devenir Booster**\n"
            "> Prépare tes preuves de rang et tes disponibilités.\n\n"
            "🛡️ **Candidature Staff**\n"
            "> Prépare ton expérience et ta motivation.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "> 🔒 Ton ticket est visible uniquement par toi et le staff\n"
            "> ⚠️ Un seul ticket ouvert à la fois"
        ),
        colour=C_BOOSTER,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Sélectionne un motif dans le menu ci-dessous ⬇️")
    await ch_open_fr.send(embed=e, view=TicketPanelView())

    # --- Ticket panel EN ---
    e = discord.Embed(
        title="🎟️  OPEN A TICKET",
        description=(
            "**This is where it all starts.**\n\n"
            "Pick your reason from the menu below. A private channel will be created "
            "instantly between you and the staff.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🚀 **Order a boost**\n"
            "> Have your current rank, target rank and region ready.\n\n"
            "💪 **Become a Booster**\n"
            "> Have your rank proof and availability ready.\n\n"
            "🛡️ **Staff Application**\n"
            "> Have your experience and motivation ready.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "> 🔒 Your ticket is only visible to you and the staff\n"
            "> ⚠️ One open ticket at a time"
        ),
        colour=C_BOOSTER,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Select a reason from the menu below ⬇️")
    await ch_open_en.send(embed=e, view=TicketPanelViewEN())

    # --- Staff chat ---
    await ch_staff.send(embed=discord.Embed(
        title="🔒  Salon staff",
        description=(
            "Coordination interne uniquement.\n\n"
            "**Commandes utiles :**\n"
            "`/setup` — reconstruit le serveur (idempotent)\n"
            "`/panel` — panneau de tickets FR • `/panel_en` — panneau EN\n"
            "`/verifypanel` — panneau de vérification bilingue\n"
            "`/langue` — change la langue d'un membre\n"
            "`/request_payment` — demande de paiement crypto\n"
            "`/lockdown` — mode protection anti-raid\n"
            "`/add @membre` — ajoute quelqu'un au ticket courant"
        ),
        colour=C_ADMIN,
    ))

    await interaction.followup.send(
        "✅ **Serveur construit.**\n\n"
        "**Dernière étape indispensable :** va dans *Paramètres du serveur → Rôles* et "
        f"place le rôle du bot **au-dessus** de {r_admin.mention}, sinon il ne pourra pas "
        "attribuer les rôles.\n"
        f"Pense aussi à passer le *niveau de vérification* du serveur sur **Moyen** ou **Élevé**.",
        ephemeral=True,
    )


# ======================================================================
#  COMMANDES UTILITAIRES
# ======================================================================


@bot.tree.command(name="panel", description="Renvoie le panneau de tickets ici.")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    e = discord.Embed(
        title="🎟️  OUVRIR UN TICKET",
        description="Sélectionne ton motif dans le menu ci-dessous pour ouvrir un salon privé avec le staff.",
        colour=C_BOOSTER,
    )
    await interaction.channel.send(embed=e, view=TicketPanelView())
    await interaction.response.send_message("✅ Panneau envoyé.", ephemeral=True)


@bot.tree.command(name="panel_en", description="Sends the English ticket panel here.")
@app_commands.checks.has_permissions(administrator=True)
async def panel_en(interaction: discord.Interaction):
    e = discord.Embed(
        title="🎟️  OPEN A TICKET",
        description="Pick your reason from the menu below to open a private channel with the staff.",
        colour=C_BOOSTER,
    )
    await interaction.channel.send(embed=e, view=TicketPanelViewEN())
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)


@bot.tree.command(name="langue", description="Change la langue d'un membre (FR / EN).")
@app_commands.describe(membre="Le membre concerné", langue="Nouvelle langue")
@app_commands.choices(langue=[
    app_commands.Choice(name="🇫🇷 Français", value="fr"),
    app_commands.Choice(name="🇬🇧 English", value="en"),
])
async def langue(
    interaction: discord.Interaction,
    langue: app_commands.Choice[str],
    membre: discord.Member = None,
):
    target = membre or interaction.user
    role_admin = get_role(interaction.guild, R_ADMIN)
    is_staff = role_admin and role_admin in interaction.user.roles

    if membre and membre != interaction.user and not is_staff:
        return await interaction.response.send_message(
            "⛔ Seul le staff peut changer la langue d'un autre membre.", ephemeral=True
        )

    r_new = get_role(interaction.guild, R_FR if langue.value == "fr" else R_EN)
    r_old = get_role(interaction.guild, R_EN if langue.value == "fr" else R_FR)

    if r_new is None:
        return await interaction.response.send_message(
            "⚠️ Rôles de langue introuvables. Relance `/setup`.", ephemeral=True
        )

    try:
        await target.add_roles(r_new, reason="Changement de langue")
        if r_old and r_old in target.roles:
            await target.remove_roles(r_old, reason="Changement de langue")
    except discord.Forbidden:
        return await interaction.response.send_message(
            "⚠️ Permissions insuffisantes.", ephemeral=True
        )

    await interaction.response.send_message(
        f"✅ Langue de {target.mention} → **{langue.name}**", ephemeral=True
    )


@bot.tree.command(name="verifypanel", description="Renvoie le panneau de vérification ici.")
@app_commands.checks.has_permissions(administrator=True)
async def verifypanel(interaction: discord.Interaction):
    e = discord.Embed(
        title="🔐  VÉRIFICATION OBLIGATOIRE",
        description="Clique sur le bouton ci-dessous pour accéder au serveur.",
        colour=C_MEMBRE,
    )
    await interaction.channel.send(embed=e, view=VerifyView())
    await interaction.response.send_message("✅ Panneau envoyé.", ephemeral=True)


@bot.tree.command(name="request_payment", description="Ouvre une demande de paiement crypto dans ce ticket.")
@app_commands.describe(montant="Montant attendu", devise="Devise du paiement")
@app_commands.choices(devise=[
    app_commands.Choice(name="Bitcoin (BTC)", value="BTC"),
    app_commands.Choice(name="Ethereum (ETH)", value="ETH"),
    app_commands.Choice(name="USDT (ERC-20)", value="USDT_ERC20"),
])
async def request_payment(
    interaction: discord.Interaction, montant: float, devise: app_commands.Choice[str]
):
    role_admin = get_role(interaction.guild, R_ADMIN)
    if not role_admin or role_admin not in interaction.user.roles:
        return await interaction.response.send_message("⛔ Réservé au staff.", ephemeral=True)

    if not (interaction.channel.topic or "").startswith("ticket-owner:"):
        return await interaction.response.send_message(
            "⛔ Cette commande ne fonctionne que dans un ticket.", ephemeral=True
        )

    wallet = WALLETS.get(devise.value, "")
    if not wallet:
        return await interaction.response.send_message(
            f"⚠️ Aucune adresse configurée pour {devise.name}. Renseigne-la dans WALLETS en haut de bot.py.",
            ephemeral=True,
        )

    conf = guild_conf(interaction.guild.id)
    conf.setdefault("payments", {})[str(interaction.channel.id)] = {
        "currency": devise.value,
        "amount": montant,
        "status": "pending",
    }
    save_data(DATA)

    e = discord.Embed(
        title="💸  Demande de paiement",
        description=(
            f"**Montant :** `{montant}` {devise.name}\n"
            f"**Adresse :**\n```\n{wallet}\n```\n\n"
            "Une fois le paiement envoyé, clique sur le bouton ci-dessous et colle le lien "
            "de ta transaction (Blockstream, Etherscan…) ou simplement son hash."
        ),
        colour=C_CLIENT,
    )
    e.set_footer(text="Vérification automatique, confirmation finale par le staff.")
    await interaction.response.send_message(embed=e, view=PaymentRequestView())


@bot.tree.command(name="add", description="Ajoute un membre au ticket courant.")
@app_commands.describe(membre="Le membre à ajouter")
async def add(interaction: discord.Interaction, membre: discord.Member):
    if not (interaction.channel.topic or "").startswith("ticket-owner:"):
        return await interaction.response.send_message(
            "⛔ Cette commande ne fonctionne que dans un ticket.", ephemeral=True
        )
    await interaction.channel.set_permissions(
        membre, view_channel=True, send_messages=True, read_message_history=True
    )
    await interaction.response.send_message(f"✅ {membre.mention} a été ajouté au ticket.")


@bot.tree.command(name="lockdown", description="Active ou désactive le mode protection anti-raid.")
@app_commands.checks.has_permissions(administrator=True)
async def lockdown_cmd(interaction: discord.Interaction):
    gid = interaction.guild.id
    if bot.lockdown.get(gid, 0) > time.time():
        bot.lockdown[gid] = 0
        await interaction.response.send_message("🔓 Mode protection **désactivé**.", ephemeral=True)
    else:
        bot.lockdown[gid] = time.time() + LOCKDOWN_DURATION
        await interaction.response.send_message(
            f"🛡️ Mode protection **activé** pour {LOCKDOWN_DURATION // 60} minutes.",
            ephemeral=True,
        )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "⛔ Tu n'as pas la permission d'utiliser cette commande."
    else:
        msg = f"⚠️ Une erreur est survenue : `{type(error).__name__}`"
        print(f"[ERREUR] {error!r}")
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ======================================================================

#  SERVEUR HTTP KEEPALIVE (obligatoire pour le plan gratuit Render)
# ======================================================================
#  Render exige qu'un Web Service écoute sur un port, sinon il tue le
#  service. Ce mini serveur répond simplement "OK" et sert de cible au
#  pinger externe (UptimeRobot) qui empêche la mise en veille.
# ======================================================================


class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        status = "en ligne" if bot.is_ready() else "démarrage"
        body = f"Bot Discord : {status}".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, *args):
        pass  # On évite de polluer les logs Render avec chaque ping


def start_keepalive():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"→ Serveur keepalive démarré sur le port {port}")


# ======================================================================

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ La variable d'environnement DISCORD_TOKEN est manquante.")
    start_keepalive()
    bot.run(TOKEN)
