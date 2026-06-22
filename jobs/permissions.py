import discord


def has_high_tier_guard(member: discord.Member) -> bool:
    return any(role.name.lower() == "high tier guard" for role in getattr(member, "roles", []))
