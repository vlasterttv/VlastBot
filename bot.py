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
from collections import deque

import discord
from discord.ext import commands
from discord import app_commands

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

# --- Couleurs ---
# 0x000000 est traité comme "pas de couleur" par Discord -> on utilise 0x010101
C_ADMIN = 0x010101      # Noir
C_BOOSTER = 0xE74C3C    # Rouge
C_CLIENT = 0xF1C40F     # Jaune
C_MEMBRE = 0x5DADE2     # Bleu ciel
C_UNVERIFIED = 0x2B2D31 # Gris fondu

# --- Anti-raid ---
MIN_ACCOUNT_AGE_DAYS = 7     # Âge minimum du compte pour se vérifier
RAID_JOIN_COUNT = 8          # X arrivées...
RAID_JOIN_WINDOW = 20        # ...en Y secondes = lockdown
LOCKDOWN_DURATION = 300      # Durée du lockdown en secondes

DATA_FILE = "bot_data.json"

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
        self.add_view(TicketControlView())
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
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Je vérifie mon compte",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="persistent:verify",
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        role_membre = get_role(guild, R_MEMBRE)
        role_unverified = get_role(guild, R_UNVERIFIED)

        if role_membre is None:
            return await interaction.response.send_message(
                "⚠️ Le rôle membre est introuvable. Contacte un administrateur.",
                ephemeral=True,
            )

        if role_membre in member.roles:
            return await interaction.response.send_message(
                "✅ Tu es déjà vérifié.", ephemeral=True
            )

        # --- Lockdown anti-raid actif ---
        if bot.lockdown.get(guild.id, 0) > time.time():
            return await interaction.response.send_message(
                "🛡️ Le serveur est en **mode protection** suite à une vague de connexions "
                "suspectes. Réessaie dans quelques minutes.",
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
                f"🚫 Ton compte Discord est trop récent (**{age.days} jour(s)**).\n"
                f"Un minimum de **{MIN_ACCOUNT_AGE_DAYS} jours** est requis. "
                "Ouvre un ticket si tu penses que c'est une erreur.",
                ephemeral=True,
            )

        try:
            await member.add_roles(role_membre, reason="Vérification réussie")
            if role_unverified and role_unverified in member.roles:
                await member.remove_roles(role_unverified, reason="Vérification réussie")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "⚠️ Je n'ai pas les permissions nécessaires. Mon rôle doit être **au-dessus** "
                "des rôles que j'attribue.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "🎉 **Bienvenue !** Tu as maintenant accès à l'intégralité du serveur.\n"
            "Passe par la catégorie **Ticket Boost** pour commander.",
            ephemeral=True,
        )

        await log_event(
            guild,
            discord.Embed(
                title="✅ Nouveau membre vérifié",
                description=f"{member.mention} • `{member}`\nCompte créé il y a **{age.days} jours**.",
                colour=C_MEMBRE,
            ),
        )


# ======================================================================
#  VUES — TICKETS
# ======================================================================

TICKET_TYPES = {
    "boost": {
        "label": "Commander un boost",
        "emoji": "🚀",
        "desc": "Faire monter ton rang par un booster vérifié",
        "prefix": "boost",
        "intro": (
            "Merci pour ta commande ! Pour aller vite, indique-nous :\n"
            "> **1.** Le jeu concerné\n"
            "> **2.** Ton rang actuel et le rang visé\n"
            "> **3.** Ta région / serveur\n"
            "> **4.** Le mode souhaité (compte partagé ou duo)\n\n"
            "Un membre du staff arrive pour te chiffrer ça."
        ),
    },
    "booster": {
        "label": "Devenir Booster",
        "emoji": "💪",
        "desc": "Rejoindre l'équipe et gagner de l'argent",
        "prefix": "booster",
        "intro": (
            "Content de voir que tu veux rejoindre l'équipe. Envoie-nous :\n"
            "> **1.** Ton rang actuel + preuve (screenshot / tracker)\n"
            "> **2.** Ton historique de peak sur les dernières saisons\n"
            "> **3.** Tes disponibilités hebdomadaires\n"
            "> **4.** Tes éventuelles expériences de boost précédentes\n\n"
            "Un recruteur va prendre ton dossier en charge."
        ),
    },
    "staff": {
        "label": "Candidature Staff",
        "emoji": "🛡️",
        "desc": "Postuler pour un poste de modération / support",
        "prefix": "staff",
        "intro": (
            "Merci pour ta candidature. Détaille-nous :\n"
            "> **1.** Ton âge et ton fuseau horaire\n"
            "> **2.** Tes expériences de modération\n"
            "> **3.** Ton temps de présence quotidien estimé\n"
            "> **4.** Pourquoi toi plutôt qu'un autre\n\n"
            "Prends le temps de bien répondre, c'est ce qu'on regarde en premier."
        ),
    },
}


class TicketPanelView(discord.ui.View):
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
    async def select_ticket(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        kind = select.values[0]
        cfg = TICKET_TYPES[kind]
        guild = interaction.guild
        member = interaction.user

        # --- Un seul ticket ouvert à la fois ---
        existing = discord.utils.find(
            lambda c: c.topic == f"ticket-owner:{member.id}",
            guild.text_channels,
        )
        if existing:
            return await interaction.followup.send(
                f"⚠️ Tu as déjà un ticket ouvert : {existing.mention}", ephemeral=True
            )

        conf = guild_conf(guild.id)
        category = guild.get_channel(conf.get("ticket_category", 0))
        if category is None:
            return await interaction.followup.send(
                "⚠️ Catégorie de tickets introuvable. Relance `/setup`.", ephemeral=True
            )

        role_admin = get_role(guild, R_ADMIN)
        role_booster = get_role(guild, R_BOOSTER)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }
        if role_admin:
            overwrites[role_admin] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )
        # Les boosters ne voient que les tickets de commande
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
            reason=f"Ticket {kind} ouvert par {member}",
        )

        embed = discord.Embed(
            title=f"{cfg['emoji']}  {cfg['label']}  •  Ticket #{number:04d}",
            description=cfg["intro"],
            colour=C_CLIENT,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Ouvert par {member}", icon_url=member.display_avatar.url)

        ping = role_admin.mention if role_admin else ""
        await channel.send(
            content=f"{member.mention} {ping}",
            embed=embed,
            view=TicketControlView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )

        await interaction.followup.send(
            f"✅ Ton ticket a été créé : {channel.mention}", ephemeral=True
        )

        await log_event(
            guild,
            discord.Embed(
                title="🎟️ Ticket ouvert",
                description=f"**{cfg['label']}** — {channel.mention}\nPar {member.mention}",
                colour=C_CLIENT,
            ),
        )


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

    ow_public_read = {guild.default_role: DENY, r_unverif: DENY, r_membre: READONLY, r_admin: STAFF}
    ow_public_talk = {guild.default_role: DENY, r_unverif: DENY, r_membre: TALK, r_admin: STAFF}
    ow_verify = {
        guild.default_role: DENY,
        r_unverif: discord.PermissionOverwrite(
            view_channel=True, read_message_history=True, send_messages=False
        ),
        r_membre: DENY,
        r_admin: SEE,
    }
    ow_tickets = {
        guild.default_role: DENY,
        r_unverif: DENY,
        r_membre: READONLY,
        r_booster: SEE,
        r_admin: STAFF,
    }
    ow_admin = {
        guild.default_role: DENY,
        r_unverif: DENY,
        r_membre: DENY,
        r_client: DENY,
        r_booster: DENY,
        r_admin: STAFF,
    }

    # ------------------------------------------------------------------
    #  4. CATÉGORIES & SALONS
    # ------------------------------------------------------------------
    async def make_category(name, overwrites):
        existing = discord.utils.get(guild.categories, name=name)
        if existing:
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

    # --- 🔐 VÉRIFICATION ---
    cat_verif = await make_category("🔐・VÉRIFICATION", ow_verify)
    ch_verif = await make_text(cat_verif, "╰✅・vérification", ow_verify)

    # --- 📋 INFORMATION ---
    cat_info = await make_category("📋・INFORMATION", ow_public_read)
    ch_welcome = await make_text(cat_info, "├👋・bienvenue", ow_public_read)
    ch_rules = await make_text(cat_info, "├📜・règlement", ow_public_read)
    ch_vouches = await make_text(cat_info, "╰⭐・vouches", ow_public_read)

    # --- 💬 GÉNÉRAL ---
    cat_gen = await make_category("💬・GÉNÉRAL", ow_public_talk)
    await make_text(cat_gen, "├🗨️・discussion", ow_public_talk)
    await make_text(cat_gen, "├📸・média", ow_public_talk)
    await make_text(cat_gen, "╰🌐・réseaux", ow_public_read)

    # --- 🎫 TICKET BOOST ---
    cat_ticket = await make_category("🎫・TICKET BOOST", ow_tickets)
    ch_price = await make_text(cat_ticket, "├💲・tarification", ow_tickets)
    ch_open = await make_text(cat_ticket, "╰🎟️・créer-un-ticket", ow_tickets)

    # --- 🛠️ ADMIN ---
    cat_admin = await make_category("🛠️・ADMIN", ow_admin)
    ch_staff = await make_text(cat_admin, "├🔒・staff-chat", ow_admin)
    ch_logs = await make_text(cat_admin, "├📊・logs", ow_admin)
    await make_voice(cat_admin, "╰🔊・Vocal Staff", ow_admin)

    # ------------------------------------------------------------------
    #  5. SAUVEGARDE DE LA CONFIG
    # ------------------------------------------------------------------
    conf = guild_conf(guild.id)
    conf.update(
        {
            "ticket_category": cat_ticket.id,
            "log_channel": ch_logs.id,
            "verify_channel": ch_verif.id,
            "welcome_channel": ch_welcome.id,
        }
    )
    save_data(DATA)

    # ------------------------------------------------------------------
    #  6. MESSAGES
    # ------------------------------------------------------------------

    # --- Vérification ---
    e = discord.Embed(
        title="🔐  VÉRIFICATION OBLIGATOIRE",
        description=(
            f"Bienvenue sur **{guild.name}**.\n\n"
            "Ce serveur est protégé contre les raids. Pour accéder au reste des salons, "
            "clique simplement sur le bouton ci-dessous.\n\n"
            f"> ⏳ Ton compte Discord doit avoir au moins **{MIN_ACCOUNT_AGE_DAYS} jours**.\n"
            "> 🛡️ En cas d'affluence anormale, la vérification est temporairement suspendue.\n"
            "> ❓ Un souci ? Attends quelques minutes puis réessaie."
        ),
        colour=C_MEMBRE,
    )
    e.set_footer(text="Système de protection automatique")
    await ch_verif.send(embed=e, view=VerifyView())

    # --- Bienvenue ---
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
            f"> **1.** Lis le {ch_rules.mention}\n"
            f"> **2.** Consulte les tarifs dans {ch_price.mention}\n"
            f"> **3.** Ouvre un ticket dans {ch_open.mention}\n\n"
            "Bon boost. 🏆"
        ),
        colour=C_MEMBRE,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    await ch_welcome.send(embed=e)

    # --- Règlement ---
    e = discord.Embed(
        title="📜  RÈGLEMENT DU SERVEUR",
        description="Le fait de rester sur le serveur vaut acceptation de ces règles.",
        colour=C_ADMIN,
    )
    e.add_field(
        name="1️⃣  Respect",
        value="Aucune insulte, aucun propos discriminatoire, aucun harcèlement. Sanction immédiate.",
        inline=False,
    )
    e.add_field(
        name="2️⃣  Pas de spam",
        value="Ni en salon, ni en MP. La pub pour d'autres services est bannissable.",
        inline=False,
    )
    e.add_field(
        name="3️⃣  Transactions en ticket uniquement",
        value=(
            "Toute commande passe par un ticket officiel. Un paiement effectué en dehors "
            "d'un ticket **ne sera jamais couvert** par le staff."
        ),
        inline=False,
    )
    e.add_field(
        name="4️⃣  Méfie-toi des usurpateurs",
        value=(
            "Le staff ne te contactera **jamais en premier** en MP pour te réclamer un paiement. "
            "Vérifie systématiquement le rôle de ton interlocuteur."
        ),
        inline=False,
    )
    e.add_field(
        name="5️⃣  Litiges",
        value="Un désaccord se règle dans le ticket concerné, calmement, avec le staff. Pas en public.",
        inline=False,
    )
    e.add_field(
        name="6️⃣  CGU Discord",
        value="Les [Conditions d'utilisation](https://discord.com/terms) s'appliquent. 13 ans minimum.",
        inline=False,
    )
    e.set_footer(text="Le staff se réserve le droit de sanctionner tout comportement nuisible.")
    await ch_rules.send(embed=e)

    # --- Vouches ---
    e = discord.Embed(
        title="⭐  VOUCHES & RETOURS CLIENTS",
        description=(
            "Ce salon regroupe les retours de nos clients.\n\n"
            "**Format attendu après une commande :**\n"
            "```\n"
            "Booster  : @pseudo\n"
            "Service  : Boost Or 3 → Platine 2\n"
            "Durée    : 2 jours\n"
            "Note     : ⭐⭐⭐⭐⭐\n"
            "Avis     : Rapide et propre, aucun souci.\n"
            "```\n"
            "🚫 Tout faux vouch entraîne un bannissement définitif."
        ),
        colour=C_CLIENT,
    )
    await ch_vouches.send(embed=e)

    # --- Tarification ---
    e = discord.Embed(
        title="💲  GRILLE TARIFAIRE",
        description=(
            "Tarifs indicatifs. Le prix exact dépend de ton rang de départ, du rang visé "
            "et de ta région. Un devis précis t'est donné dans ton ticket.\n"
            "*(Modifie ces valeurs selon tes propres tarifs.)*"
        ),
        colour=C_CLIENT,
    )
    e.add_field(
        name="🥉  Rangs bas",
        value="`Fer → Bronze` **5€**\n`Bronze → Argent` **8€**\n`Argent → Or` **12€**",
        inline=True,
    )
    e.add_field(
        name="🥈  Rangs moyens",
        value="`Or → Platine` **18€**\n`Platine → Diamant` **30€**\n`Diamant → Ascendant` **50€**",
        inline=True,
    )
    e.add_field(
        name="🥇  Haut elo",
        value="`Ascendant → Immortel` **90€**\n`Immortel → Radiant` **sur devis**",
        inline=True,
    )
    e.add_field(
        name="➕  Options",
        value=(
            "> 🤝 **Duo boost** : +40 %\n"
            "> ⚡ **Priorité express** : +20 %\n"
            "> 📺 **Stream privé de la session** : +10 %\n"
            "> 🎯 **Choix des agents / champions** : offert"
        ),
        inline=False,
    )
    e.add_field(
        name="💳  Paiements acceptés",
        value="PayPal (G&S) • Carte bancaire • Crypto • Virement",
        inline=False,
    )
    e.set_footer(text="Aucun paiement en dehors d'un ticket officiel.")
    await ch_price.send(embed=e)

    # --- Panneau de tickets ---
    e = discord.Embed(
        title="🎟️  OUVRIR UN TICKET",
        description=(
            "**C'est ici que tout commence.**\n\n"
            "Que tu viennes acheter un boost, rejoindre l'équipe ou postuler au staff, "
            "sélectionne simplement ton motif dans le menu ci-dessous. "
            "Un salon privé sera créé instantanément entre toi et le staff.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🚀 **Commander un boost**\n"
            "> Tu veux monter de rang. Prépare ton rang actuel, le rang visé et ta région, "
            "on te chiffre ça en quelques minutes.\n\n"
            "💪 **Devenir Booster**\n"
            "> Tu es haut elo et tu veux monétiser ton niveau. Prépare tes preuves de rang "
            "et tes disponibilités.\n\n"
            "🛡️ **Candidature Staff**\n"
            "> Tu veux nous aider à gérer la boutique et la communauté. Prépare ton expérience "
            "et ta motivation.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "> ⏱️ Réponse moyenne : **moins de 30 minutes** en journée\n"
            "> 🔒 Ton ticket est visible uniquement par toi et le staff\n"
            "> ⚠️ Un seul ticket ouvert à la fois — les tickets vides sont supprimés"
        ),
        colour=C_BOOSTER,
    )
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Sélectionne un motif dans le menu déroulant ci-dessous ⬇️")
    await ch_open.send(embed=e, view=TicketPanelView())

    # --- Staff chat ---
    await ch_staff.send(
        embed=discord.Embed(
            title="🔒  Salon staff",
            description=(
                "Coordination interne uniquement.\n\n"
                "**Commandes utiles :**\n"
                "`/setup` — reconstruit le serveur (idempotent)\n"
                "`/panel` — renvoie le panneau de tickets dans le salon courant\n"
                "`/verifypanel` — renvoie le panneau de vérification\n"
                "`/lockdown` — active/désactive le mode protection manuellement\n"
                "`/add @membre` — ajoute quelqu'un au ticket courant"
            ),
            colour=C_ADMIN,
        )
    )

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

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ La variable d'environnement DISCORD_TOKEN est manquante.")
    bot.run(TOKEN)
