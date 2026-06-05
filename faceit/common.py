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


def _country_code_to_unicode_flag(country_code):
    code = country_code.strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(ord(char) + 127397) for char in code)


def get_country_flag_badge(guild, country_code):
    if not country_code or not isinstance(country_code, str):
        return ""

    emoji_text = get_guild_emoji_text(guild, f"flag_{country_code.lower()}")
    if emoji_text:
        return emoji_text

    return _country_code_to_unicode_flag(country_code)


def format_faceit_form(outcomes):
    if not outcomes:
        return "❓"

    emoji_map = {
        "W": "🟢",
        "L": "🔴",
        "?": "⚪",
    }
    return " ".join(emoji_map.get(outcome, "⚪") for outcome in outcomes)
