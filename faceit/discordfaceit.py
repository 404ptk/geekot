import discord


async def get_discordfaceit_stats():
    import faceit_utils as fu

    player_stats = []
    # Load daily stats for comparison
    daily_data = fu.load_daily_stats()
    current_date = fu.datetime.now().strftime("%Y-%m-%d")
    is_same_day = daily_data.get("date") == current_date
    daily_start_map = daily_data.get("stats", {}) if is_same_day else {}

    previous_stats = fu.load_faceit_ranking()
    previous_positions = {player["nickname"]: i for i, player in enumerate(previous_stats)}
    previous_elo_map = {player["nickname"]: player["elo"] for player in previous_stats}

    for nickname in fu.player_nicknames:
        player_data = fu.get_faceit_player_data(nickname)
        if player_data:
            player_level = player_data.get("games", {}).get("cs2", {}).get("skill_level", 0)
            player_elo = player_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0)
            pid = player_data.get("player_id")

            # Fetch last 5 matches
            last_matches_str = "N/A"
            streak_emoji = ""
            if pid:
                matches = fu.get_faceit_player_matches(pid, limit=5)
                if matches:
                    outcomes = []
                    for match in matches:
                        result = match.get("stats", {}).get("Result")
                        if result == "1":
                            outcomes.append("🟢")
                        elif result == "0":
                            outcomes.append("🔴")
                        else:
                            outcomes.append("❓")
                    last_matches_str = "/".join(outcomes)

                    if len(outcomes) >= 3:
                        if outcomes[:3] == ["🟢", "🟢", "🟢"]:
                            streak_emoji = " 🔥"
                        elif outcomes[:3] == ["🔴", "🔴", "🔴"]:
                            streak_emoji = " 😭"

            # ELO Diff logic
            elo_diff = 0
            if nickname in previous_elo_map:
                elo_diff = player_elo - previous_elo_map[nickname]

            elo_change_str = f" ({'+' if elo_diff > 0 else ''}{elo_diff})" if elo_diff != 0 else ""
            elo_full_str = f"ELO: {player_elo}{elo_change_str}"

            player_stats.append(
                {
                    "nickname": nickname,
                    "level": player_level if isinstance(player_level, int) else 0,
                    "elo": player_elo if isinstance(player_elo, int) else 0,
                    "elo_full_str": elo_full_str,
                    "last_matches": last_matches_str,
                    "streak_emoji": streak_emoji,
                }
            )

    player_stats.sort(key=lambda x: (x["elo"], x["level"]), reverse=True)

    # Calculate max length for alignment
    max_elo_len = 0
    for player in player_stats:
        if len(player["elo_full_str"]) > max_elo_len:
            max_elo_len = len(player["elo_full_str"])

    embed = discord.Embed(
        title="📊 **Ranking Faceit**",
        description="🔹 Lista graczy uszeregowana według ELO Faceit.",
        color=discord.Color.orange(),
    )
    for index, player in enumerate(player_stats):
        rank_emoji = "🥇" if index == 0 else "🥈" if index == 1 else "🥉" if index == 2 else ""
        flag = "🇺🇦" if player["nickname"] == "PhesterM9" else "🇵🇱"

        position_change = ""
        if player["nickname"] in previous_positions:
            prev_pos = previous_positions[player["nickname"]]
            if prev_pos > index:
                position_change = "\t⬆️"
            elif prev_pos < index:
                position_change = "\t⬇️"
            else:
                position_change = "\t➖"

        # Daily difference
        daily_diff_str = ""
        if is_same_day:
            start_elo = daily_start_map.get(player["nickname"])
            if start_elo is not None:
                d_diff = player["elo"] - start_elo
                if d_diff != 0:
                    daily_diff_str = f" ``Dobowy: {'+' if d_diff > 0 else ''}{d_diff}``"

        padded_elo = player["elo_full_str"].ljust(max_elo_len)
        value_str = f"```\n{padded_elo} | LVL: {player['level']} | {player['last_matches']}{player['streak_emoji']}\n```" + daily_diff_str

        embed.add_field(
            name=f"{rank_emoji} **{player['nickname']}** {flag} {position_change}",
            value=value_str,
            inline=False,
        )
    embed.set_footer(text="📅 Ranking generowany automatycznie | Zmiany względem poprzedniego wywołania")

    # Save minimal stats for next comparison
    save_list = [{"nickname": p["nickname"], "level": p["level"], "elo": p["elo"]} for p in player_stats]
    fu.save_faceit_ranking(save_list)
    return embed


def register_discordfaceit_command(tree, guild):
    @tree.command(
        name="discordfaceit",
        description="Wyświetla ranking Faceit graczy z discorda",
        guild=guild,
    )
    async def discordfaceit(interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await get_discordfaceit_stats()
        await interaction.followup.send(embed=embed)
