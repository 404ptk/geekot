import json
import os
from datetime import datetime, timedelta

import discord

FACEIT_WEEKLY_STATS_FILE = "txt/faceit_weekly_stats.json"
# If the bot runs in a different timezone than desired, adjust weekly summary
WEEKLY_SEND_OFFSET_HOURS = 2


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

    limit = 20  # Reduced from 50 to avoid too many API calls
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


def calculate_weekly_metrics(matches, player_nickname=None):
    if not matches:
        return None

    count = len(matches)
    wins = 0
    total_kills = 0
    total_deaths = 0
    total_adr = 0.0
    total_clutch_count = 0
    total_clutch_wins = 0
    total_entry_count = 0
    total_entry_wins = 0

    from faceit_utils import get_faceit_match_details

    def _get_match_id_from_obj(m):
        if not isinstance(m, dict):
            return None

        # direct priority checks
        for key in ("match_id", "matchId", "matchID", "Match Id", "Match ID", "match id"):
            if key in m and m.get(key):
                return str(m.get(key))

        # normalized key lookup
        for key, value in m.items():
            normalized = str(key).lower().replace("_", "").replace("-", "").replace(" ", "")
            if normalized == "matchid" and value:
                return str(value)

        if m.get("id"):
            return str(m.get("id"))
        return None

    for match in matches:
        stats = match.get("stats", {})
        total_kills += int(stats.get("Kills", 0))
        total_deaths += int(stats.get("Deaths", 0))
        total_adr += float(stats.get("ADR", 0))
        if stats.get("Result") == "1":
            wins += 1
        # Prefer detailed per-player clutch/entry from match details (same as /faceit command)
        match_id = _get_match_id_from_obj(stats) or _get_match_id_from_obj(match) or _get_match_id_from_obj(match.get("match", {}))
        if match_id and player_nickname:
            try:
                details = get_faceit_match_details(match_id)
            except Exception:
                details = None
            if details:
                # find player in match details
                found = False
                for team_name, team_data in details.get("teams", {}).items():
                    for pl in team_data.get("players", []):
                        if pl.get("nickname") == player_nickname:
                            clutch = pl.get("clutch", {"count": 0, "wins": 0})
                            entry = pl.get("entry", {"count": 0, "wins": 0})
                            total_clutch_count += int(clutch.get("count", 0))
                            total_clutch_wins += int(clutch.get("wins", 0))
                            total_entry_count += int(entry.get("count", 0))
                            total_entry_wins += int(entry.get("wins", 0))
                            found = True
                            break
                    if found:
                        break
                if found:
                    continue

        # fallback: try to extract basic values directly from stats if details unavailable
        try:
            c1 = int(stats.get("1v1Count", 0))
        except Exception:
            c1 = 0
        try:
            c2 = int(stats.get("1v2Count", 0))
        except Exception:
            c2 = 0
        try:
            cw1 = int(stats.get("1v1Wins", 0))
        except Exception:
            cw1 = 0
        try:
            cw2 = int(stats.get("1v2Wins", 0))
        except Exception:
            cw2 = 0
        clutch_count = c1 + c2
        clutch_wins = cw1 + cw2
        total_clutch_count += clutch_count
        total_clutch_wins += clutch_wins

        try:
            entry_cnt = int(stats.get("Entry Count", stats.get("EntryCount", 0)))
        except Exception:
            entry_cnt = 0
        try:
            entry_w = int(stats.get("Entry Wins", stats.get("EntryWins", 0)))
        except Exception:
            entry_w = 0
        total_entry_count += entry_cnt
        total_entry_wins += entry_w

    losses = count - wins
    avg_kills = total_kills / count
    avg_adr = total_adr / count
    kd = total_kills / total_deaths if total_deaths > 0 else float(total_kills)
    winratio = (wins / count) * 100

    clutch_wr = (total_clutch_wins / total_clutch_count * 100) if total_clutch_count > 0 else 0
    entry_wr = (total_entry_wins / total_entry_count * 100) if total_entry_count > 0 else 0

    return {
        "count": count,
        "wins": wins,
        "losses": losses,
        "total_kills": total_kills,
        "avg_kills": avg_kills,
        "avg_adr": avg_adr,
        "kd": kd,
        "winratio": winratio,
        "clutch_count": total_clutch_count,
        "clutch_wins": total_clutch_wins,
        "clutch_wr": clutch_wr,
        "entry_count": total_entry_count,
        "entry_wins": total_entry_wins,
        "entry_wr": entry_wr,
    }


def elo_to_faceit_level(elo):
    if not isinstance(elo, int):
        return None

    if elo >= 2001:
        return 10
    if elo >= 1751:
        return 9
    if elo >= 1531:
        return 8
    if elo >= 1351:
        return 7
    if elo >= 1201:
        return 6
    if elo >= 1051:
        return 5
    if elo >= 901:
        return 4
    if elo >= 751:
        return 3
    if elo >= 501:
        return 2
    return 1


def create_weekly_stats_embed(start_ts, end_ts, snapshot_elos, title, description, guild=None):
    import faceit_utils as fu
    from faceit.common import get_faceit_level_badge

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
    )
    # thumbnail from local images folder (sender must attach the file with name 'tygodniowka.png')
    embed.set_thumbnail(url="attachment://tygodniowka.png")

    # Cache for match details to avoid duplicate API calls
    _match_details_cache = {}

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
        metrics = calculate_weekly_metrics(matches, player_nickname=nickname)

        elo_diff_str = ""
        elo_diff_val = 0
        start_elo = snapshot_elos.get(nickname)
        if not isinstance(start_elo, int):
            start_elo = None

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
                "start_elo": start_elo,
                "current_elo": current_elo if isinstance(current_elo, int) else None,
                "matches": matches,
            }
        )

    player_stats_list.sort(key=lambda x: (x["metrics"]["count"] if x["metrics"] else -1), reverse=True)

    for player in player_stats_list:
        metrics = player["metrics"]
        if not metrics:
            continue

        # --- Premade calculation ---
        total = metrics['count']
        premade_count = 0
        per_partner = {}
        per_partner_wins = {}

        # helper to safely get match id from returned match object
        def _get_match_id(m):
            if not isinstance(m, dict):
                return None

            def _extract_from_dict(d):
                if not isinstance(d, dict):
                    return None
                # direct priority checks
                for key in ("match_id", "matchId", "matchID", "Match Id", "Match ID", "match id"):
                    if key in d and d.get(key):
                        return d.get(key)

                # normalized key lookup: supports e.g. "Match Id", "match-id", "MATCH_ID"
                for key, value in d.items():
                    normalized = str(key).lower().replace("_", "").replace("-", "").replace(" ", "")
                    if normalized == "matchid" and value:
                        return value

                # fallback: plain id (least specific)
                if d.get("id"):
                    return d.get("id")
                return None

            # top-level then nested objects commonly returned by Faceit endpoint
            for container in (m, m.get("match"), m.get("stats"), m.get("match_stats")):
                match_id = _extract_from_dict(container)
                if match_id:
                    return str(match_id)
            return None

        from faceit_utils import get_faceit_match_details

        canonical_map = {n.lower(): n for n in fu.player_nicknames}

        if total >= 1:
            matches_to_check = player.get('matches', [])[:15]
            for m in matches_to_check:
                match_id = _get_match_id(m)
                if not match_id:
                    continue
                try:
                    details = get_faceit_match_details(match_id)
                except Exception:
                    details = None
                if not details:
                    continue

                our_team_players = []
                for team in details.get('teams', {}).values():
                    for pl in team.get('players', []):
                        nick = (pl.get('nickname') or '').lower()
                        if nick == (player['nick'] or '').lower():
                            our_team_players = [p.get('nickname') for p in team.get('players', []) if p.get('nickname')]
                            break
                    if our_team_players:
                        break

                if not our_team_players:
                    continue

                partners = []
                for p in our_team_players:
                    plow = (p or '').lower()
                    if plow in canonical_map and plow != (player['nick'] or '').lower():
                        partners.append(canonical_map[plow])

                if partners:
                    premade_count += 1
                    is_win = str(m.get("stats", {}).get("Result", "")) == "1"
                    for partner in partners:
                        per_partner[partner] = per_partner.get(partner, 0) + 1
                        if is_win:
                            per_partner_wins[partner] = per_partner_wins.get(partner, 0) + 1

        premade_percent = (premade_count / total * 100) if total > 0 else 0

        partner_parts = []
        for partner, cnt in sorted(per_partner.items(), key=lambda x: x[1], reverse=True)[:2]:
            wins_with_partner = per_partner_wins.get(partner, 0)
            wr_with_partner = (wins_with_partner / cnt * 100) if cnt > 0 else 0
            partner_parts.append(f"{partner} ({cnt}) {wr_with_partner:.0f}%")

        if partner_parts:
            premade_line = f"PremQue: {premade_percent:.0f}% | " + " | ".join(partner_parts)
        else:
            premade_line = f"PremQue: {premade_percent:.0f}% |"

        level_change_str = ""
        start_level = elo_to_faceit_level(player.get("start_elo"))
        current_level = elo_to_faceit_level(player.get("current_elo"))
        if start_level and current_level and start_level != current_level:
            start_badge = get_faceit_level_badge(guild, start_level)
            current_badge = get_faceit_level_badge(guild, current_level)
            level_change_str = f" {start_badge} -> {current_badge}"

        line1 = f"ELO: {player['elo_str']} | Gier: {metrics['count']} | W: {metrics['wins']} L: {metrics['losses']}"
        line2 = f"Śr. K/D: {metrics['kd']:.2f} | Śr. kille: {metrics['avg_kills']:.1f} | Śr. ADR: {metrics['avg_adr']:.1f}"
        line3 = f"Clutche: {metrics.get('clutch_wr', 0):.0f}% ({metrics.get('clutch_count', 0)}) | Entry: {metrics.get('entry_wr', 0):.0f}% ({metrics.get('entry_count', 0)})"

        all_lines_to_measure = [line1, line2, line3, premade_line]
        computed_max = max((len(ln) for ln in all_lines_to_measure), default=0)
        MAX_LINE_LEN = 100
        global_max = min(computed_max, MAX_LINE_LEN)

        def _truncate(s):
            if len(s) <= global_max:
                return s
            return s[: max(0, global_max - 3)] + "..."

        def _pad_trail(s):
            return s + ' ' * (global_max - len(s))

        line1 = _pad_trail(_truncate(line1))
        line2 = _pad_trail(_truncate(line2))
        line3 = _pad_trail(_truncate(line3))
        premade_line = _pad_trail(_truncate(premade_line))

        value = (
            f"`{line1}`"
            f"\n`{line2}`"
            f"\n`{line3}`"
            f"\n`{premade_line}`"
        )
        embed.add_field(name=f"👤 {player['nick']}{level_change_str}", value=value, inline=False)

    embed.set_footer(text="• Aby być na liście, zagraj co najmniej jedną grę w tygodniu.")

    active_players = [player for player in player_stats_list if player["metrics"]]

    if active_players:
        def _player_score(p):
            m = p.get("metrics", {}) or {}
            return m.get("kd", 0) * 100 + m.get("avg_adr", 0) + m.get("avg_kills", 0) * 100

        goat = max(active_players, key=_player_score)
        embed.add_field(
            name="🐐 GOAT tygodnia",
            value=f"{goat['nick']} | K/D: {goat['metrics']['kd']:.2f} | ADR: {goat['metrics']['avg_adr']:.1f}",
            inline=True,
        )

        troll = min(active_players, key=_player_score)
        embed.add_field(
            name="🤡 Troll tygodnia",
            value=f"{troll['nick']} | K/D: {troll['metrics']['kd']:.2f} | ADR: {troll['metrics']['avg_adr']:.1f}",
            inline=True,
        )

        embed.add_field(name="", value="", inline=False)

        bezrobotny = max(active_players, key=lambda p: p["metrics"]["count"])
        embed.add_field(
            name="🛌 Bezrobotny tygodnia",
            value=f"{bezrobotny['nick']} | Gier: {bezrobotny['metrics']['count']}",
            inline=True,
        )

        negative_diffs = [player for player in active_players if player["elo_diff"] < 0]
        if negative_diffs:
            syzyf = min(negative_diffs, key=lambda p: p["elo_diff"])
            embed.add_field(
                name="🪨 Syzyf tygodnia",
                value=f"{syzyf['nick']} | {syzyf['elo_diff']}",
                inline=True,
            )
        else:
            embed.add_field(name="", value="", inline=True)

        embed.add_field(name="", value="", inline=False)

        best_adr = max(active_players, key=lambda p: p["metrics"]["avg_adr"])
        embed.add_field(
            name="🔫 Najlepszy ADR",
            value=f"{best_adr['nick']} | {best_adr['metrics']['avg_adr']:.1f}",
            inline=True,
        )

        most_kills_avg = max(active_players, key=lambda p: p["metrics"]["avg_kills"])
        embed.add_field(
            name="💀 Najwięcej zabójstw (śr.)",
            value=f"{most_kills_avg['nick']} | {most_kills_avg['metrics']['avg_kills']:.1f}",
            inline=True,
        )

        embed.add_field(name="", value="", inline=False)

        entry_fragging_players = [p for p in active_players if p["metrics"]["entry_count"] > 0]
        if entry_fragging_players:
            entry_fragger = max(entry_fragging_players, key=lambda p: p["metrics"]["entry_wr"] * p["metrics"]["entry_count"])
            embed.add_field(
                name="📍 Entry Fragger",
                value=f"{entry_fragger['nick']} | {entry_fragger['metrics']['entry_wr']:.0f}% ({entry_fragger['metrics']['entry_count']})",
                inline=True,
            )

        clutching_players = [p for p in active_players if p["metrics"]["clutch_count"] > 0]
        if clutching_players:
            clutcher = max(clutching_players, key=lambda p: p["metrics"]["clutch_wr"] * p["metrics"]["clutch_count"])
            embed.add_field(
                name="🔥 Clutcher",
                value=f"{clutcher['nick']} | {clutcher['metrics']['clutch_wr']:.0f}% ({clutcher['metrics']['clutch_count']})",
                inline=True,
            )

    return embed


async def generate_weekly_summary(client, channel_id=None, guild=None):
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
        guild=guild,
    )


async def run_weekly_summary_if_due(client, today=None):
    import faceit_utils as fu

    now = today or datetime.now()
    # Adjust current time by configured offset so we can trigger the summary
    # at a different server-local hour (e.g. server UTC, desired local midnight)
    adjusted = now + timedelta(hours=WEEKLY_SEND_OFFSET_HOURS)
    adjusted_date_str = adjusted.strftime("%Y-%m-%d")

    weekly_stats = load_weekly_stats()
    last_run_date = weekly_stats.get("last_run_date")

    # Run when the adjusted time falls on Monday (weekday==0) and we haven't
    # already run for that adjusted date.
    if adjusted.weekday() != 0 or last_run_date == adjusted_date_str:
        return

    target_channel_id = 1301248598108798996
    channel = client.get_channel(target_channel_id)
    if not channel:
        return

    last_snapshot_date_str = weekly_stats.get("date")
    try:
        start_dt = datetime.strptime(last_snapshot_date_str, "%Y-%m-%d") if last_snapshot_date_str else (adjusted - timedelta(days=7))
    except ValueError:
        start_dt = adjusted - timedelta(days=7)

    start_ts = start_dt.timestamp()
    # Use adjusted (shifted) time as the period end so the period matches the
    # user's local midnight boundary.
    end_ts = adjusted.timestamp()
    snapshot_elos = weekly_stats.get("stats", {})

    embed = create_weekly_stats_embed(
        start_ts,
        end_ts,
        snapshot_elos,
        "📅 **Podsumowanie Tygodnia Faceit**",
        f"Statystyki za okres: {start_dt.strftime('%d-%m-%Y')} - {adjusted_date_str}",
        guild=channel.guild,
    )

    if not embed:
        return

    try:
        await channel.send(file=discord.File('images/ranking/tygodniowka.png'), embed=embed)
    except Exception:
        await channel.send(embed=embed)

    new_snapshot = {}
    for nick in fu.player_nicknames:
        p_data = fu.get_faceit_player_data(nick)
        if p_data:
            elo = p_data.get("games", {}).get("cs2", {}).get("faceit_elo")
            if isinstance(elo, int):
                new_snapshot[nick] = elo

    weekly_stats["stats"] = new_snapshot
    # Save date corresponding to the adjusted (local) date boundary
    weekly_stats["date"] = adjusted_date_str
    weekly_stats["last_run_date"] = adjusted_date_str
    save_weekly_stats(weekly_stats)
