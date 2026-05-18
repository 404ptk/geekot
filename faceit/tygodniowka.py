import json
import os
from datetime import datetime, timedelta

import discord

FACEIT_WEEKLY_STATS_FILE = "txt/faceit_weekly_stats.json"


def load_weekly_stats():
    if os.path.exists(FACEIT_WEEKLY_STATS_FILE):
        try:
            with open(FACEIT_WEEKLY_STATS_FILE, "r") as file:
                return json.load(file)
        except Exception:
            pass
    return {}


def save_weekly_stats(data):
    with open(FACEIT_WEEKLY_STATS_FILE, "w") as file:
        json.dump(data, file, indent=4)


def get_matches_in_period(player_id, start_ts, end_ts):
    """
    Fetches matches for a player and filters them by timestamp.
    start_ts and end_ts are in seconds.
    """
    import faceit_utils as fu

    limit = 50
    matches = fu.get_faceit_player_matches(player_id, limit=limit)

    if not matches:
        return []

    filtered_matches = []
    for match in matches:
        match_stats = match.get("stats", {})
        finished_at_ms = match_stats.get("Match Finished At")

        if finished_at_ms:
            finished_at_sec = int(finished_at_ms) / 1000.0
            if start_ts <= finished_at_sec <= end_ts:
                filtered_matches.append(match)

    return filtered_matches


def calculate_weekly_metrics(matches):
    if not matches:
        return None

    count = len(matches)
    wins = 0
    total_kills = 0
    total_deaths = 0
    total_adr = 0.0

    for match in matches:
        stats = match.get("stats", {})
        total_kills += int(stats.get("Kills", 0))
        total_deaths += int(stats.get("Deaths", 0))
        total_adr += float(stats.get("ADR", 0))
        if stats.get("Result") == "1":
            wins += 1

    losses = count - wins
    avg_kills = total_kills / count
    avg_adr = total_adr / count
    kd = total_kills / total_deaths if total_deaths > 0 else float(total_kills)
    winratio = (wins / count) * 100

    return {
        "count": count,
        "wins": wins,
        "losses": losses,
        "total_kills": total_kills,
        "avg_kills": avg_kills,
        "avg_adr": avg_adr,
        "kd": kd,
        "winratio": winratio,
    }


def create_weekly_stats_embed(start_ts, end_ts, snapshot_elos, title, description):
    import faceit_utils as fu

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
    )

    player_stats_list = []

    for nickname in fu.player_nicknames:
        player_data = fu.get_faceit_player_data(nickname)
        if not player_data:
            continue

        pid = player_data.get("player_id")
        current_elo = player_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0)

        if not pid:
            continue

        matches = get_matches_in_period(pid, start_ts, end_ts)
        metrics = calculate_weekly_metrics(matches)

        elo_diff_str = ""
        elo_diff_val = 0
        start_elo = snapshot_elos.get(nickname)
        if start_elo is not None and isinstance(current_elo, int):
            diff = current_elo - start_elo
            elo_diff_val = diff
            elo_diff_str = f"{start_elo} -> {current_elo} ({'+' if diff > 0 else ''}{diff})"
        else:
            elo_diff_str = f"{current_elo}"

        player_stats_list.append(
            {
                "nick": nickname,
                "metrics": metrics,
                "elo_str": elo_diff_str,
                "elo_diff": elo_diff_val,
            }
        )

    player_stats_list.sort(key=lambda x: (x["metrics"]["count"] if x["metrics"] else -1), reverse=True)

    for player in player_stats_list:
        metrics = player["metrics"]
        if not metrics:
            continue

        value = (
            f"```ELO: {player['elo_str']} | Gier: {metrics['count']}```"
            f"```Śr. K/D: {metrics['kd']:.2f} | Śr. kille: {metrics['avg_kills']:.1f} | Śr. ADR: {metrics['avg_adr']:.1f}```"
        )
        embed.add_field(name=f"👤 {player['nick']}", value=value, inline=False)

    embed.set_footer(text="Jeśli nie ma cię na liście, to znaczy że nie rozegrałeś żadnego meczu w tym tygodniu.")

    active_players = [player for player in player_stats_list if player["metrics"]]

    if active_players:
        embed.add_field(name="", value="Statystyki specjalne:", inline=False)

        goat = max(active_players, key=lambda p: p["metrics"]["kd"] * 100 + p["metrics"]["avg_adr"])
        embed.add_field(
            name="🐐 GOAT tygodnia",
            value=f"{goat['nick']} | K/D: {goat['metrics']['kd']:.2f} | ADR: {goat['metrics']['avg_adr']:.1f}",
            inline=False,
        )

        troll = min(active_players, key=lambda p: p["metrics"]["kd"] * 100 + p["metrics"]["avg_adr"])
        embed.add_field(
            name="🤡 Troll tygodnia",
            value=f"{troll['nick']} | K/D: {troll['metrics']['kd']:.2f} | ADR: {troll['metrics']['avg_adr']:.1f}",
            inline=False,
        )

        bezrobotny = max(active_players, key=lambda p: p["metrics"]["count"])
        embed.add_field(
            name="🛌 Bezrobotny tygodnia",
            value=f"{bezrobotny['nick']} | Gier: {bezrobotny['metrics']['count']}",
            inline=False,
        )

        negative_diffs = [player for player in active_players if player["elo_diff"] < 0]
        if negative_diffs:
            syzyf = min(negative_diffs, key=lambda p: p["elo_diff"])
            embed.add_field(
                name="🪨 Syzyf tygodnia",
                value=f"{syzyf['nick']} | {syzyf['elo_diff']}",
                inline=False,
            )

        best_adr = max(active_players, key=lambda p: p["metrics"]["avg_adr"])
        embed.add_field(
            name="🔫 Najlepszy ADR",
            value=f"{best_adr['nick']} | {best_adr['metrics']['avg_adr']:.1f}",
            inline=False,
        )

        most_kills_avg = max(active_players, key=lambda p: p["metrics"]["avg_kills"])
        embed.add_field(
            name="💀 Najwięcej zabójstw (śr.)",
            value=f"{most_kills_avg['nick']} | {most_kills_avg['metrics']['avg_kills']:.1f}",
            inline=False,
        )

    return embed


async def generate_weekly_summary(client, channel_id=None):
    """
    Generates the weekly summary embed.
    If run automatically (Monday), it compares with saved snapshot.
    """
    weekly_stats = load_weekly_stats()

    if not weekly_stats:
        return None

    last_snapshot_date_str = weekly_stats.get("date")
    snapshot_elos = weekly_stats.get("stats", {})

    if last_snapshot_date_str:
        try:
            start_dt = datetime.strptime(last_snapshot_date_str, "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.now() - timedelta(days=7)
    else:
        start_dt = datetime.now() - timedelta(days=7)

    end_dt = datetime.now()
    start_ts = start_dt.timestamp()
    end_ts = end_dt.timestamp()

    return create_weekly_stats_embed(
        start_ts,
        end_ts,
        snapshot_elos,
        "📅 **Podsumowanie Tygodnia Faceit**",
        f"Statystyki za okres: {start_dt.strftime('%Y-%m-%d')} - {end_dt.strftime('%Y-%m-%d')}",
    )
