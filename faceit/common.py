import discord


def get_guild_emoji_text(guild, emoji_name):
    if not guild:
        return ""

    emoji_obj = discord.utils.get(guild.emojis, name=emoji_name)
    return str(emoji_obj) if emoji_obj else ""


def get_faceit_level_badge(guild, level):
    if isinstance(level, int) and level > 0:
        emoji_text = get_guild_emoji_text(guild, f"faceit{level}")
        if emoji_text:
            return emoji_text
        return f"LVL {level}"
    return "❓"


def format_faceit_form(outcomes):
    if not outcomes:
        return "❓"

    emoji_map = {
        "W": "🟢",
        "L": "🔴",
        "?": "⚪",
    }
    return " ".join(emoji_map.get(outcome, "⚪") for outcome in outcomes)
