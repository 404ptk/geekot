import json
import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import discord
from discord import app_commands

GUILD_ID = 551503797067710504
RELATIONS_FILE = "txt/relations.json"
TEMP_RELATIONS_FILE = "txt/temp_relations.json"

ALLOWED_USERS = [
    "jaro",
    "mateuko",
    "radzio",
    "kuzia",
    "hubi",
    "plaster",
    "masny",
    "kajtek",
]
ALLOWED_USERS_SET = set(ALLOWED_USERS)

USER_ID_TO_ALIAS = {
    443406275716579348: "jaro",
    391289282125365248: "mateuko",
    389401523010142209: "radzio",
    337340399251357697: "kuzia",
    520184778016948225: "hubi",
    665272195806789664: "plaster",
    606785554918539275: "masny",
    326679825823563796: "kajtek",
}

USER_DATIVE_FORMS = {
    "jaro": "jarowi",
    "mateuko": "mateukowi",
    "radzio": "radziowi",
    "kuzia": "kuzi",
    "hubi": "hubiemu",
    "plaster": "plastrowi",
    "masny": "masnemu",
    "kajtek": "kajtkowi",
}

USER_INSTRUMENTAL_FORMS = {
    "jaro": "jarem",
    "mateuko": "mateukiem",
    "radzio": "radziem",
    "kuzia": "kuzią",
    "hubi": "hubim",
    "plaster": "plastrem",
    "masny": "masnym",
    "kajtek": "kajtkiem",
}

RELATION_ALIASES = {
    "zgoda": "zgoda",
    "zgody": "zgoda",
    "neutralne stosunki": "neutralne",
    "neutralne": "neutralne",
    "uklad": "uklad",
    "uklady": "uklad",
    "kosa": "kosa",
    "kosy": "kosa",
}

RELATION_LABELS = {
    "zgoda": "ZGODY",
    "neutralne": "NEUTRALNE STOSUNKI",
    "uklad": "UKLADY",
    "kosa": "KOSY",
}

RELATION_LABELS_SINGULAR = {
    "zgoda": "ZGODA",
    "neutralne": "NEUTRALNE STOSUNKI",
    "uklad": "UKŁAD",
    "kosa": "KOSA",
}

RELATION_EMOJIS = {
    "zgoda": "🤝",
    "neutralne": "😐",
    "uklad": "🫱‍🫲",
    "kosa": "⚔️",
}

RELATION_COLORS = {
    "zgoda": discord.Color.green(),
    "neutralne": discord.Color.gold(),
    "uklad": discord.Color.purple(),
    "kosa": discord.Color.red(),
}

RELATION_ACTIONS = {
    "zgoda": {
        "new": "zaczął trzymać zgodę z",
        "update": "od teraz trzyma zgodę z",
    },
    "neutralne": {
        "new": "zaczął mieć neutralne stosunki z",
        "update": "od teraz ma neutralne stosunki z",
    },
    "uklad": {
        "new": "zaczął mieć układy z",
        "update": "od teraz ma układy z",
    },
    "kosa": {
        "new": "wypowiedział kosę",
        "update": "od teraz ma kosę z",
    },
}

DISPLAY_RELATION_CHOICES = [
    "zgoda",
    "neutralne stosunki",
    "uklad",
    "kosa",
]

ACTIVE_TEMP_TASKS: Dict[str, asyncio.Task] = {}
TEMP_TASKS_STARTED = False


def normalize_nick(value: str) -> str:
    return value.strip().lower()


def normalize_relation(value: str) -> Optional[str]:
    cleaned = value.strip().lower().replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    return RELATION_ALIASES.get(cleaned)


def relation_label(value: Optional[str]) -> str:
    if not value:
        return "BRAK RELACJI"
    return RELATION_LABELS.get(value, value.upper())


def relation_label_singular(value: Optional[str]) -> str:
    if not value:
        return "BRAK RELACJI"
    return RELATION_LABELS_SINGULAR.get(value, value.upper())


def inflect_second_nick(alias: str) -> str:
    return USER_DATIVE_FORMS.get(alias, alias)


def inflect_second_nick_with_z(alias: str) -> str:
    return USER_INSTRUMENTAL_FORMS.get(alias, alias)


def build_relation_embed(user_a: str, user_b: str, relation_key: str, existing_relation: Optional[str] = None) -> discord.Embed:
    action_type = "update" if existing_relation else "new"
    action_text = RELATION_ACTIONS[relation_key][action_type]
    emoji = RELATION_EMOJIS.get(relation_key, "✨")
    if relation_key == "kosa":
        user_b_form = inflect_second_nick(user_b)
    else:
        user_b_form = inflect_second_nick_with_z(user_b)

    sentence = f"**{user_a}** {action_text} **{user_b_form}**."

    embed = discord.Embed(
        title=sentence,
        color=RELATION_COLORS.get(relation_key, discord.Color.green()),
    )
    embed.add_field(name="Status", value=f"{emoji} **{relation_label_singular(relation_key)}**", inline=True)
    if existing_relation:
        embed.add_field(
            name="Poprzednio",
            value=f"{RELATION_EMOJIS.get(existing_relation, '✨')} **{relation_label_singular(existing_relation)}**",
            inline=True,
        )
    return embed


def build_relation_unchanged_embed(user_a: str, user_b: str, relation_key: str) -> discord.Embed:
    emoji = RELATION_EMOJIS.get(relation_key, "✨")
    if relation_key == "kosa":
        user_b_form = inflect_second_nick(user_b)
    else:
        user_b_form = inflect_second_nick_with_z(user_b)
    embed = discord.Embed(
        title=f"{emoji} Brak zmian",
        description=f"**{user_a}** już ma **{relation_label(relation_key)}** z **{user_b_form}**.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Status", value=f"{emoji} **{relation_label(relation_key)}**", inline=True)
    return embed


def load_relations() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(RELATIONS_FILE):
        return {}

    try:
        with open(RELATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {RELATIONS_FILE}: {e}")

    return {}


def load_temp_relations() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(TEMP_RELATIONS_FILE):
        return {}

    try:
        with open(TEMP_RELATIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading {TEMP_RELATIONS_FILE}: {e}")

    return {}


def save_relations(data: Dict[str, Dict[str, str]]) -> None:
    with open(RELATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def save_temp_relations(data: Dict[str, Dict[str, str]]) -> None:
    with open(TEMP_RELATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def set_bidirectional_relation(data: Dict[str, Dict[str, str]], user_a: str, user_b: str, relation: str) -> None:
    data.setdefault(user_a, {})[user_b] = relation
    data.setdefault(user_b, {})[user_a] = relation


def remove_bidirectional_relation(data: Dict[str, Dict[str, str]], user_a: str, user_b: str) -> None:
    if user_a in data and user_b in data[user_a]:
        del data[user_a][user_b]
        if not data[user_a]:
            del data[user_a]

    if user_b in data and user_a in data[user_b]:
        del data[user_b][user_a]
        if not data[user_b]:
            del data[user_b]


def get_pair_key(user_a: str, user_b: str) -> str:
    return "|".join(sorted([user_a, user_b]))


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def resolve_actor_nick(interaction: discord.Interaction) -> Optional[str]:
    actor_id = getattr(interaction.user, "id", None)
    if isinstance(actor_id, int):
        alias = USER_ID_TO_ALIAS.get(actor_id)
        if alias:
            return alias

    candidates = [
        getattr(interaction.user, "display_name", ""),
        getattr(interaction.user, "global_name", ""),
        getattr(interaction.user, "name", ""),
    ]

    for candidate in candidates:
        normalized = normalize_nick(candidate)
        if normalized in ALLOWED_USERS_SET:
            return normalized

    return None


def parse_user_id_from_text(value: str) -> Optional[int]:
    raw = value.strip()
    if raw.startswith("<@") and raw.endswith(">"):
        raw = raw[2:-1]
        if raw.startswith("!"):
            raw = raw[1:]

    if raw.isdigit():
        return int(raw)

    return None


def resolve_alias_from_input(interaction: discord.Interaction, value: str) -> Optional[str]:
    normalized = normalize_nick(value)
    if normalized in ALLOWED_USERS_SET:
        return normalized

    parsed_id = parse_user_id_from_text(value)
    if parsed_id is not None:
        return USER_ID_TO_ALIAS.get(parsed_id)

    guild = interaction.guild
    if guild is None:
        return None

    for user_id, alias in USER_ID_TO_ALIAS.items():
        member = guild.get_member(user_id)
        if member is None:
            continue

        candidates = [
            getattr(member, "display_name", ""),
            getattr(member, "global_name", ""),
            getattr(member, "name", ""),
        ]

        discriminator = getattr(member, "discriminator", "")
        if discriminator and discriminator != "0":
            candidates.append(f"{member.name}#{discriminator}")

        for candidate in candidates:
            if normalize_nick(candidate) == normalized:
                return alias

    return None


def schedule_temp_expiry_task(client: discord.Client, pair_key: str) -> None:
    existing = ACTIVE_TEMP_TASKS.get(pair_key)
    if existing and not existing.done():
        existing.cancel()

    ACTIVE_TEMP_TASKS[pair_key] = asyncio.create_task(handle_temp_expiry(client, pair_key))


def start_temp_tasks(client: discord.Client) -> None:
    temp_data = load_temp_relations()
    for pair_key in temp_data.keys():
        schedule_temp_expiry_task(client, pair_key)


async def handle_temp_expiry(client: discord.Client, pair_key: str) -> None:
    current_task = asyncio.current_task()
    try:
        temp_data = load_temp_relations()
        record = temp_data.get(pair_key)
        if not record:
            return

        expires_at = parse_iso_datetime(record["expires_at"])
        now = datetime.now(timezone.utc)
        delay = (expires_at - now).total_seconds()

        if delay > 0:
            await asyncio.sleep(delay)

        temp_data = load_temp_relations()
        record = temp_data.get(pair_key)
        if not record:
            return

        expires_at = parse_iso_datetime(record["expires_at"])
        now = datetime.now(timezone.utc)
        if expires_at > now:
            # Relacja zostala przedluzona; scheduler uruchomiony na starej dacie moze sie tu pojawic.
            schedule_temp_expiry_task(client, pair_key)
            return

        user_a = record["user_a"]
        user_b = record["user_b"]
        previous_relation = record.get("previous_relation")

        relations_data = load_relations()
        if previous_relation:
            set_bidirectional_relation(relations_data, user_a, user_b, previous_relation)
        else:
            remove_bidirectional_relation(relations_data, user_a, user_b)
        save_relations(relations_data)

        current_relation = relations_data.get(user_a, {}).get(user_b)

        del temp_data[pair_key]
        save_temp_relations(temp_data)

        channel_id_raw = record.get("channel_id")
        try:
            channel_id = int(channel_id_raw)
        except (TypeError, ValueError):
            channel_id = 0

        channel = client.get_channel(channel_id) if channel_id else None
        if channel is None and channel_id:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception:
                channel = None

        if channel and hasattr(channel, "send"):
            embed = discord.Embed(
                title="Zgoda wygasla",
                description=(
                    f"Zgoda pomiedzy **{user_a}** a **{inflect_second_nick_with_z(user_b)}** wygasla po 24h.\n"
                    f"Aktualna relacja: **{relation_label(current_relation)}**"
                ),
                color=discord.Color.orange(),
            )
            await channel.send(embed=embed)

    except asyncio.CancelledError:
        return
    except Exception as e:
        print(f"Error in temp relation expiry task ({pair_key}): {e}")
    finally:
        active = ACTIVE_TEMP_TASKS.get(pair_key)
        if active is current_task:
            ACTIVE_TEMP_TASKS.pop(pair_key, None)


async def nick_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    current_lower = current.strip().lower()
    choices = [
        app_commands.Choice(name=user, value=user)
        for user in ALLOWED_USERS
        if current_lower in user.lower()
    ]
    return choices[:25]


async def relation_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    current_lower = current.strip().lower()
    choices = [
        app_commands.Choice(name=option, value=option)
        for option in DISPLAY_RELATION_CHOICES
        if current_lower in option.lower()
    ]
    return choices[:25]


async def setup_relations_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    global TEMP_TASKS_STARTED

    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    if not TEMP_TASKS_STARTED:
        start_temp_tasks(client)
        TEMP_TASKS_STARTED = True

    @tree.command(
        name="relacje",
        description="Pokazuje relacje wybranego użytkownika",
        guild=guild,
    )
    @app_commands.describe(nick="Nick użytkownika")
    @app_commands.autocomplete(nick=nick_autocomplete)
    async def relacje(interaction: discord.Interaction, nick: str):
        user = resolve_alias_from_input(interaction, nick)
        if user is None:
            await interaction.response.send_message(
                "Niepoprawny nick. Dozwoleni użytkownicy: " + ", ".join(ALLOWED_USERS),
                ephemeral=True,
            )
            return

        data = load_relations()
        user_relations = data.get(user, {})

        grouped = {
            "zgoda": [],
            "neutralne": [],
            "uklad": [],
            "kosa": [],
        }

        for other_user, relation_type in user_relations.items():
            if relation_type in grouped:
                grouped[relation_type].append(other_user)

        embed = discord.Embed(
            title=f"Relacje: {user}",
            color=discord.Color.blue(),
        )

        for key in ["zgoda", "neutralne", "uklad", "kosa"]:
            users = sorted(grouped[key])
            value = ", ".join(users) if users else "-"
            embed.add_field(name=RELATION_LABELS[key], value=value, inline=False)

        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="zgoda",
        description="Ustawia tymczasowa zgode miedzy toba a wybranym uzytkownikiem na 24h",
        guild=guild,
    )
    @app_commands.describe(nick="Nick użytkownika, z którym zawierasz zgodę")
    @app_commands.autocomplete(nick=nick_autocomplete)
    async def zgoda(interaction: discord.Interaction, nick: str):
        actor = resolve_actor_nick(interaction)
        if actor is None:
            await interaction.response.send_message(
                "Nie moge przypisac Twojego nicku do listy relacji. Ustaw nick zgodny z: " + ", ".join(ALLOWED_USERS),
                ephemeral=True,
            )
            return

        target = resolve_alias_from_input(interaction, nick)
        if target is None:
            await interaction.response.send_message(
                "Niepoprawny nick. Dozwoleni użytkownicy: " + ", ".join(ALLOWED_USERS),
                ephemeral=True,
            )
            return

        if actor == target:
            await interaction.response.send_message(
                "Nie mozna zawrzec zgody z samym soba.",
                ephemeral=True,
            )
            return

        relations_data = load_relations()
        current_relation = relations_data.get(actor, {}).get(target)
        pair_key = get_pair_key(actor, target)

        temp_data = load_temp_relations()
        existing_temp = temp_data.get(pair_key)
        previous_relation = existing_temp.get("previous_relation") if existing_temp else current_relation

        is_already_zgoda = current_relation == "zgoda"

        set_bidirectional_relation(relations_data, actor, target, "zgoda")
        save_relations(relations_data)

        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        temp_data[pair_key] = {
            "user_a": actor,
            "user_b": target,
            "previous_relation": previous_relation,
            "expires_at": expires_at.isoformat(),
            "channel_id": interaction.channel_id,
        }
        save_temp_relations(temp_data)
        schedule_temp_expiry_task(client, pair_key)

        embed = discord.Embed(
            title=f"{RELATION_EMOJIS['zgoda']} Tymczasowa zgoda",
            description=f"**{actor}** trzyma zgodę z **{inflect_second_nick_with_z(target)}** przez 24h.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Relacja", value=f"{RELATION_EMOJIS['zgoda']} **{relation_label('zgoda')}**", inline=True)
        embed.add_field(name="Wygasa", value=f"<t:{int(expires_at.timestamp())}:R>", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=is_already_zgoda)

    @tree.command(
        name="dodajrelacje",
        description="Dodaje relacje miedzy toba a drugim uzytkownikiem",
        guild=guild,
    )
    @app_commands.describe(
        relacja="Typ relacji: zgoda / neutralne stosunki / uklad / kosa",
        nick2="Drugi użytkownik",
    )
    @app_commands.autocomplete(relacja=relation_autocomplete, nick2=nick_autocomplete)
    async def dodajrelacje(interaction: discord.Interaction, relacja: str, nick2: str):
        user_a = resolve_actor_nick(interaction)
        if user_a is None:
            await interaction.response.send_message(
                "Nie moge przypisac Twojego nicku do listy relacji. Ustaw nick zgodny z: " + ", ".join(ALLOWED_USERS),
                ephemeral=True,
            )
            return

        user_b = resolve_alias_from_input(interaction, nick2)
        relation_key = normalize_relation(relacja)

        if user_b is None:
            await interaction.response.send_message(
                "Niepoprawny nick. Dozwoleni użytkownicy: " + ", ".join(ALLOWED_USERS),
                ephemeral=True,
            )
            return

        if user_a == user_b:
            await interaction.response.send_message(
                "Nie mozna dodac relacji uzytkownika z samym soba.",
                ephemeral=True,
            )
            return

        if not relation_key:
            await interaction.response.send_message(
                "Niepoprawny typ relacji. Uzyj: zgoda, neutralne stosunki, uklad lub kosa.",
                ephemeral=True,
            )
            return

        data = load_relations()
        existing_relation = data.get(user_a, {}).get(user_b)

        set_bidirectional_relation(data, user_a, user_b, relation_key)
        save_relations(data)

        if existing_relation == relation_key:
            await interaction.response.send_message(
                embed=build_relation_unchanged_embed(user_a, user_b, relation_key),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_relation_embed(user_a, user_b, relation_key, existing_relation)
        )
