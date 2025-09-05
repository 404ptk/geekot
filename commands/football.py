# table_str = "```" + "\n".join(lines) + "```"
import discord
from discord import app_commands, ui
import requests
from datetime import datetime, timedelta

GUILD_ID = 551503797067710504
API_KEY = "633cd6ec62e44a65a01979ad90e558ba"  # Twój klucz API z football-data.org

LEAGUE_IDS = {
    "premier_league": "PL",  # Premier League
    "laliga": "PD",          # Primera Division (La Liga)
    "bundesliga": "BL1",     # Bundesliga
    "serie_a": "SA",         # Serie A
    "ligue_1": "FL1"         # Ligue 1
}

LEAGUE_DISPLAY = {
    "premier_league": "Premier League",
    "laliga": "La Liga",
    "bundesliga": "Bundesliga",
    "serie_a": "Serie A",
    "ligue_1": "Ligue 1"
}

# Liczba meczów w sezonie dla każdej ligi (stała wartość dla głównych lig)
TOTAL_GAMES_PER_SEASON = {
    "premier_league": 38,  # Premier League
    "laliga": 38,          # La Liga
    "bundesliga": 34,      # Bundesliga
    "serie_a": 38,         # Serie A
    "ligue_1": 34          # Ligue 1
}

# Funkcja do formatowania daty z formatu YYYY-MM-DD na 'DD miesiąc'
def format_date_polish(date_str):
    months = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day = date_obj.day
        month = months[date_obj.month - 1]
        return f"{day} {month}"
    except Exception:
        return date_str

def create_nice_football_table_embed(league_name, standings, season, league_key):
    embed = discord.Embed(
        title=f"🏆 {league_name} – Tabela {season}",
        color=0x066fd1
    )
    embed.set_footer(text="Dane: football-data.org")

    if not standings or len(standings) == 0:
        embed.add_field(
            name="Tabela (top 10)",
            value="Brak danych o drużynach w tym sezonie.",
            inline=False
        )
        return embed

    header = f"{'Pos'} | {'Drużyna':15} | {'Pkt':>3} | {'M':>2} | {'W-D-R'}"
    lines = [header, "-" * len(header)]

    for team in standings[:10]:
        pos = str(team.get("position", "?")).rjust(2)
        full_name = team.get("team", {}).get("name", "Unknown")
        name_parts = full_name.split(" ")
        short_name = " ".join(name_parts[:2])[:15].ljust(15)
        pts = str(team.get("points", "?")).rjust(3)
        played = str(team.get("playedGames", "?")).rjust(2)
        won = str(team.get("won", "?"))
        drawn = str(team.get("draw", "?"))
        lost = str(team.get("lost", "?"))
        line = f"{pos} | {short_name} | {pts} | {played} | {won}-{drawn}-{lost}"
        lines.append(line)

    table_str = "```" + "\n".join(lines) + "```"

    embed.add_field(
        name="Tabela (top 10)",
        value=table_str,
        inline=False
    )

    if standings and len(standings) > 0:
        leader = standings[0]
        crest_url = leader.get("team", {}).get("crest", "")
        if crest_url:
            embed.set_thumbnail(url=crest_url)

        total_games = TOTAL_GAMES_PER_SEASON.get(league_key, 38)
        played_games = leader.get("playedGames", 0)
        remaining_games = total_games - played_games if played_games <= total_games else 0

        if remaining_games == 1:
            remaining_text = f"Do końca sezonu został {remaining_games} mecz."
        elif 2 <= remaining_games <= 4:
            remaining_text = f"Do końca sezonu zostały {remaining_games} mecze."
        else:
            remaining_text = f"Do końca sezonu zostało {remaining_games} meczów."

        champion_text = ""
        if len(standings) > 1:
            leader_points = leader.get("points", 0)
            second_team = standings[1]
            second_team_points = second_team.get("points", 0)
            second_team_played = second_team.get("playedGames", 0)
            second_team_remaining = total_games - second_team_played if second_team_played <= total_games else 0
            max_possible_points_second = second_team_points + (second_team_remaining * 3)

            if leader_points > max_possible_points_second:
                leader_name = " ".join(leader.get("team", {}).get("name", "Unknown").split(" ")[:2])
                champion_text = f"\n\n🏆 Mistrz kraju: {leader_name}"
            elif remaining_games == 0:
                leader_name = " ".join(leader.get("team", {}).get("name", "Unknown").split(" ")[:2])
                champion_text = f"\n\nMistrz kraju: {leader_name} 🏆"

        # Określ drużyny pewne spadku
        relegation_text = ""
        num_teams = len(standings)
        if num_teams > 3:  # Zakładamy, że w większości lig spada ostatnie 3 drużyny
            # Pozycja pierwszej drużyny poza strefą spadkową (np. 17. miejsce w lidze 20-drużynowej)
            safe_position = num_teams - 3
            if safe_position < len(standings):
                safe_team = standings[safe_position - 1]  # Drużyna na pozycji bezpiecznej
                safe_points = safe_team.get("points", 0)
                relegation_teams = []

                # Sprawdź drużyny w strefie spadkowej
                for team in standings[-3:]:  # Ostatnie 3 drużyny
                    team_points = team.get("points", 0)
                    team_played = team.get("playedGames", 0)
                    team_remaining = total_games - team_played if team_played <= total_games else 0
                    max_possible_points = team_points + (team_remaining * 3)

                    # Jeśli maksymalna możliwa liczba punktów jest mniejsza niż punkty bezpiecznej drużyny
                    if max_possible_points < safe_points:
                        team_name = " ".join(team.get("team", {}).get("name", "Unknown").split(" ")[:2])
                        relegation_teams.append(team_name)

                if relegation_teams:
                    relegation_text = "\n\n🔻 Pewne spadku: " + ", ".join(relegation_teams)

        embed.add_field(
            name="Pozostałe mecze",
            value=remaining_text + champion_text + relegation_text,
            inline=False
        )

    return embed

def get_current_season_with_standings(league_code, api_key):
    url = f"https://api.football-data.org/v4/competitions/{league_code}"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        current_season = data.get("currentSeason", {})
        season_year = current_season.get("startDate", "").split("-")[0] if current_season else "Unknown"
        return season_year
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania sezonu: {e}")
    return None

def get_scorers(league_code, api_key, limit=10):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/scorers?limit={limit}"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        scorers = data.get("scorers", [])
        return scorers
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania strzelców: {e}")
        return []

def get_standings(league_code, api_key):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/standings"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("standings"):
            standings_data = data.get("standings", [])
            if standings_data and standings_data[0].get("table"):
                standings = standings_data[0]["table"]
                return standings
        return []
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania standings: {e}")
        return []

def get_teams_for_league(league_code, api_key):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/teams"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        teams = data.get("teams", [])
        return teams
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania klubów: {e}")
        return []

def get_last_matches(team_id, api_key, limit=10, offset=0):
    url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit={limit}&offset={offset}"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        matches = data.get("matches", [])
        return matches
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania meczów: {e}")
        return []

def get_upcoming_matches(team_id, api_key, limit=5):
    url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=SCHEDULED&limit={limit}"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        matches = data.get("matches", [])
        return matches
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania nadchodzących meczów: {e}")
        return []

def get_team_info(team_id, api_key):
    url = f"https://api.football-data.org/v4/teams/{team_id}"
    headers = {"X-Auth-Token": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data
    except Exception as e:
        print(f"🛑 [DEBUG] Błąd pobierania informacji o drużynie: {e}")
        return {}

async def setup_football_commands(client: discord.Client, tree: app_commands.CommandTree, guild_id: int = None):
    guild = discord.Object(id=guild_id) if guild_id else discord.Object(id=GUILD_ID)

    @tree.command(
        name="liga",
        description="Wyświetla statystyki wybranej ligi piłkarskiej",
        guild=guild
    )
    @app_commands.describe(
        liga="Wybierz ligę",
        statystyka="Wybierz typ statystyki do wyświetlenia"
    )
    @app_commands.choices(
        liga=[
            app_commands.Choice(name="Premier League", value="premier_league"),
            app_commands.Choice(name="La Liga", value="laliga"),
            app_commands.Choice(name="Bundesliga", value="bundesliga"),
            app_commands.Choice(name="Serie A", value="serie_a"),
            app_commands.Choice(name="Ligue 1", value="ligue_1"),
        ],
        statystyka=[
            app_commands.Choice(name="Top strzelcy", value="bramki"),
        ]
    )
    async def liga(interaction: discord.Interaction, liga: app_commands.Choice[str],
                   statystyka: app_commands.Choice[str]):
        league_key = liga.value
        league_code = LEAGUE_IDS[league_key]
        league_name = LEAGUE_DISPLAY[league_key]
        stat_type = statystyka.value

        season = get_current_season_with_standings(league_code, API_KEY)
        if not season:
            await interaction.response.send_message(
                "Brak danych dla wybranej ligi lub sezonu.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📊 {league_name} – Statystyki {season} ({statystyka.name})",
            color=0x066fd1
        )
        embed.set_footer(text="⚠️ Ze względów na ograniczenia API, jedyne możliwe dane to bramki.\nDane: football-data.org")

        if (stat_type == "bramki"):
            scorers = get_scorers(league_code, API_KEY, limit=10)
            if not scorers:
                await interaction.response.send_message(
                    f"Brak danych o strzelcach dla ligi {league_name}.",
                    ephemeral=True
                )
                return

            header = f"{'Pos':>3} | {'Gracz':15} | {'Bramki':>6} | {'Mecze':>5} | {'Śr./mecz':>8}"
            lines = [header, "-" * len(header)]
            for idx, scorer in enumerate(scorers, 1):
                player_name_full = scorer.get("player", {}).get("name", "Unknown")
                # Skróć nazwę do formatu "R. Lewandowski"
                name_parts = player_name_full.split(" ")
                if len(name_parts) > 1:
                    shortened_name = f"{name_parts[0][0]}." if len(name_parts[0]) > 0 else ""
                    player_name = f"{shortened_name} {name_parts[-1]}"[:15].ljust(15)
                else:
                    player_name = player_name_full[:15].ljust(15)
                goals = str(scorer.get("goals", 0)).rjust(6)
                matches_played = str(scorer.get("playedMatches", 0)).rjust(5)
                avg_goals = f"{scorer.get('goals', 0) / (scorer.get('playedMatches', 1) or 1):.2f}".rjust(8)
                pos = str(idx).rjust(3)
                line = f"{pos} | {player_name} | {goals} | {matches_played} | {avg_goals}"
                lines.append(line)

            table_str = "```" + "\n".join(lines) + "```"
            embed.add_field(
                name="Top 10 strzelców",
                value=table_str,
                inline=False
            )

        await interaction.response.send_message(embed=embed)


    @tree.command(
        name="tabela",
        description="Wyświetla aktualną tabelę wybranej ligi piłkarskiej",
        guild=guild
    )
    @app_commands.describe(
        liga="Wybierz ligę: premier_league, laliga, bundesliga, serie_a, ligue_1"
    )
    @app_commands.choices(
        liga=[
            app_commands.Choice(name="Premier League", value="premier_league"),
            app_commands.Choice(name="La Liga", value="laliga"),
            app_commands.Choice(name="Bundesliga", value="bundesliga"),
            app_commands.Choice(name="Serie A", value="serie_a"),
            app_commands.Choice(name="Ligue 1", value="ligue_1"),
        ]
    )
    async def tabela(interaction: discord.Interaction, liga: app_commands.Choice[str]):
        league_key = liga.value
        league_code = LEAGUE_IDS[league_key]
        league_name = LEAGUE_DISPLAY[league_key]

        season = get_current_season_with_standings(league_code, API_KEY)
        if not season:
            print("🟥 [DEBUG] Brak sezonu z tabelą.")
            await interaction.response.send_message(
                "Brak danych w tabeli dla wybranej ligi lub sezonu (API nie udostępnia jeszcze tabeli).",
                ephemeral=True
            )
            return

        standings = get_standings(league_code, API_KEY)
        if not standings:
            print("🟥 [DEBUG] Brak danych standings dla tej ligi.")
            await interaction.response.send_message(
                "Brak danych w tabeli dla wybranej ligi lub sezonu.",
                ephemeral=True
            )
            return

        embed = create_nice_football_table_embed(league_name, standings, season, league_key)
        await interaction.response.send_message(embed=embed)

    @tree.command(
        name="ostatniemecze",
        description="Wyświetla ostatnie 10 meczów wybranego klubu z danej ligi",
        guild=guild
    )
    @app_commands.describe(
        liga="Wybierz ligę",
        klub="Wybierz klub z wybranej ligi"
    )
    @app_commands.choices(
        liga=[
            app_commands.Choice(name="Premier League", value="premier_league"),
            app_commands.Choice(name="La Liga", value="laliga"),
            app_commands.Choice(name="Bundesliga", value="bundesliga"),
            app_commands.Choice(name="Serie A", value="serie_a"),
            app_commands.Choice(name="Ligue 1", value="ligue_1"),
        ]
    )
    async def ostatniemecze(interaction: discord.Interaction, liga: app_commands.Choice[str], klub: str):
        league_key = liga.value
        league_code = LEAGUE_IDS[league_key]
        league_name = LEAGUE_DISPLAY[league_key]

        # Pobierz listę klubów dla wybranej ligi
        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            await interaction.response.send_message(
                "Brak danych o klubach dla wybranej ligi.",
                ephemeral=True
            )
            return

        # Znajdź ID klubu i logo na podstawie nazwy
        team_id = None
        team_crest = ""
        for team in teams:
            team_name = team.get("name", "").lower()
            if team_name.startswith(klub.lower()) or klub.lower() in team_name:
                team_id = team.get("id")
                klub = team.get("name")  # Aktualizuj nazwę do pełnej nazwy z API
                team_crest = team.get("crest", "")  # Pobierz URL logo drużyny
                break

        if not team_id:
            await interaction.response.send_message(
                f"Nie znaleziono klubu o nazwie {klub} w lidze {league_name}.",
                ephemeral=True
            )
            return

        # Pobierz ostatnie 10 meczów dla wybranego klubu
        matches = get_last_matches(team_id, API_KEY, limit=10)
        if not matches:
            await interaction.response.send_message(
                f"Brak danych o ostatnich meczach dla klubu {klub}.",
                ephemeral=True
            )
            return

        # Przygotuj embed z ostatnimi meczami w formacie tabeli
        embed = discord.Embed(
            title=f"⚽ Ostatnie mecze: {klub}",
            color=0x066fd1
        )
        embed.set_footer(text="⚠️ Ze względów na ograniczenia API, dane są tylko z ligi/LM.\nDane: football-data.org")

        # Dodaj logo drużyny jako miniaturkę, jeśli dostępne
        if team_crest:
            embed.set_thumbnail(url=team_crest)
        else:
            print("🟥 [DEBUG] Logo drużyny nie znalezione w danych API.")

        header = f"{'Data':>6} | {'H/A':4} | {'Wynik':5} | {'Przeciwnik':12} | {'Typ':4}"
        lines = [header, "-" * len(header)]

        # Odwróć kolejność meczów, aby najnowsze były na górze
        reversed_matches = list(reversed(matches))
        for match in reversed_matches:
            home_team_full = match.get("homeTeam", {}).get("name", "Unknown")
            away_team_full = match.get("awayTeam", {}).get("name", "Unknown")
            home_team_id = match.get("homeTeam", {}).get("id", None)
            # Określ, czy mecz był u siebie (H) czy na wyjeździe (A)
            location = "Home" if home_team_id == team_id else "Away"
            location = location.ljust(3)
            # Wybierz przeciwnika (drużyna przeciwna do wybranej)
            opponent_full = away_team_full if home_team_id == team_id else home_team_full
            opponent_parts = opponent_full.split(" ")[:3]
            opponent = max(opponent_parts, key=len, default="Unknown")[:12].ljust(12)

            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home", 0)
            away_goals = score.get("away", 0)
            result = f"{home_goals}-{away_goals}".center(5)

            date_raw = match.get("utcDate", "").split("T")[0] if match.get("utcDate") else "N/A"
            try:
                date_obj = datetime.strptime(date_raw, "%Y-%m-%d")
                date = f"{date_obj.day:02d}.{date_obj.month:02d}".rjust(6)
            except Exception:
                date = "N/A".rjust(6)

            # Pobierz nazwę rozgrywek i skróć do odpowiedniego skrótu
            competition_full = match.get("competition", {}).get("name", "Nieznane")
            if "Champions League" in competition_full:
                competition = "LM".ljust(4)
            elif "Europa League" in competition_full:
                competition = "LE".ljust(4)
            elif "Conference League" in competition_full:
                competition = "LKE".ljust(4)
            else:
                competition = "Liga".ljust(4)

            line = f"{date} | {location} | {result} | {opponent} | {competition}"
            # Sprawdź, czy dodanie nowej linii nie przekroczy limitu 1024 znaków
            if len("\n".join(lines) + "\n" + line + "``````") < 1024:
                lines.append(line)
            else:
                break  # Przestań dodawać mecze, jeśli limit znaków zostanie przekroczony

        table_str = "```" + "\n".join(lines) + "```"

        embed.add_field(
            name="Ostatnie 10 meczów",
            value=table_str,
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @ostatniemecze.autocomplete("klub")
    async def klub_autocomplete(interaction: discord.Interaction, current: str):
        # Pobierz opcje komendy z danych interakcji
        options = interaction.data.get('options', [])
        liga_option = None
        for opt in options:
            if (opt.get('name') == 'liga'):
                liga_option = opt
                break

        if not liga_option or 'value' not in liga_option:
            print("🟥 [DEBUG] Autocomplete: Brak wybranej ligi.")
            return []

        league_key = liga_option['value']
        league_code = LEAGUE_IDS[league_key]

        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            print("🟥 [DEBUG] Autocomplete: Brak klubów dla tej ligi.")
            return []

        filtered_teams = [
            app_commands.Choice(name=team.get("name", "Unknown"), value=team.get("name", "Unknown"))
            for team in teams
            if current.lower() in team.get("name", "Unknown").lower()
        ][:25]  # Ogranicz do 25 wyników, maksymalna liczba dla Discorda

        return filtered_teams

    @tree.command(
        name="najblizszemecze",
        description="Wyświetla najbliższe mecze wybranego klubu z danej ligi",
        guild=guild
    )
    @app_commands.describe(
        liga="Wybierz ligę",
        klub="Wybierz klub z wybranej ligi"
    )
    @app_commands.choices(
        liga=[
            app_commands.Choice(name="Premier League", value="premier_league"),
            app_commands.Choice(name="La Liga", value="laliga"),
            app_commands.Choice(name="Bundesliga", value="bundesliga"),
            app_commands.Choice(name="Serie A", value="serie_a"),
            app_commands.Choice(name="Ligue 1", value="ligue_1"),
        ]
    )
    async def najblizszemecze(interaction: discord.Interaction, liga: app_commands.Choice[str], klub: str):
        league_key = liga.value
        league_code = LEAGUE_IDS[league_key]
        league_name = LEAGUE_DISPLAY[league_key]

        # Pobierz listę klubów dla wybranej ligi
        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            await interaction.response.send_message(
                "Brak danych o klubach dla wybranej ligi.",
                ephemeral=True
            )
            return

        # Znajdź ID klubu i logo na podstawie nazwy
        team_id = None
        team_crest = ""
        for team in teams:
            team_name = team.get("name", "").lower()
            if team_name.startswith(klub.lower()) or klub.lower() in team_name:
                team_id = team.get("id")
                klub = team.get("name")  # Aktualizuj nazwę do pełnej nazwy z API
                team_crest = team.get("crest", "")  # Pobierz URL logo drużyny
                break

        if not team_id:
            await interaction.response.send_message(
                f"Nie znaleziono klubu o nazwie {klub} w lidze {league_name}.",
                ephemeral=True
            )
            return

        # Pobierz najbliższe 5 meczów dla wybranego klubu
        matches = get_upcoming_matches(team_id, API_KEY, limit=5)
        if not matches:
            await interaction.response.send_message(
                f"Brak danych o nadchodzących meczach dla klubu {klub}.",
                ephemeral=True
            )
            return

        # Przygotuj embed z nadchodzącymi meczami w formacie tabeli
        embed = discord.Embed(
            title=f"🗓️ Nadchodzące mecze: {klub}",
            color=0x066fd1
        )
        embed.set_footer(text="⚠️ Ze względów na ograniczenia API, dane są tylko z ligi/LM.\nDane: football-data.org")

        # Dodaj logo drużyny jako miniaturkę, jeśli dostępne
        if team_crest:
            embed.set_thumbnail(url=team_crest)
        else:
            print("🟥 [DEBUG] Logo drużyny nie znalezione w danych API.")

        header = f"{'Data':>11} | {'H/A':4} | {'Przeciwnik':12} | {'Typ':4}"
        lines = [header, "-" * len(header)]

        for match in matches:
            home_team_full = match.get("homeTeam", {}).get("name", "Unknown")
            away_team_full = match.get("awayTeam", {}).get("name", "Unknown")
            home_team_id = match.get("homeTeam", {}).get("id", None)
            # Określ, czy mecz był u siebie (H) czy na wyjeździe (A)
            location = "Home" if home_team_id == team_id else "Away"
            location = location.ljust(3)
            # Wybierz przeciwnika (drużyna przeciwna do wybranej)
            opponent_full = away_team_full if home_team_id == team_id else home_team_full
            opponent_parts = opponent_full.split(" ")[:3]
            opponent = max(opponent_parts, key=len, default="Unknown")[:12].ljust(12)

            date_raw = match.get("utcDate", "").split("T")[0] if match.get("utcDate") else "N/A"
            time_raw = match.get("utcDate", "").split("T")[1][:5] if match.get("utcDate") else ""
            try:
                date_obj = datetime.strptime(f"{date_raw} {time_raw}", "%Y-%m-%d %H:%M")
                # Dodaj 2 godziny dla czasu CEST
                date_obj = date_obj + timedelta(hours=2)
                date = f"{date_obj.day:02d}.{date_obj.month:02d} {date_obj.hour:02d}:{date_obj.minute:02d}".rjust(10)
            except Exception as e:
                print(f"🛑 [DEBUG] Błąd przetwarzania daty: {e}")
                date = "N/A".rjust(10)

            # Pobierz nazwę rozgrywek i skróć do odpowiedniego skrótu
            competition_full = match.get("competition", {}).get("name", "Nieznane")
            if "Champions League" in competition_full:
                competition = "LM".ljust(4)
            elif "Europa League" in competition_full:
                competition = "LE".ljust(4)
            elif "Conference League" in competition_full:
                competition = "LKE".ljust(4)
            else:
                competition = "Liga".ljust(4)

            line = f"{date} | {location} | {opponent} | {competition}"
            # Sprawdź, czy dodanie nowej linii nie przekroczy limitu 1024 znaków
            if len("\n".join(lines) + "\n" + line + "``````") < 1024:
                lines.append(line)
            else:
                break  # Przestań dodawać mecze, jeśli limit znaków zostanie przekroczony

        table_str = "```" + "\n".join(lines) + "```"

        embed.add_field(
            name="Nadchodzące mecze",
            value=table_str,
            inline=False
        )

        await interaction.response.send_message(embed=embed)

    @najblizszemecze.autocomplete("klub")
    async def klub_autocomplete_nadchodzace(interaction: discord.Interaction, current: str):
        # Pobierz opcje komendy z danych interakcji
        options = interaction.data.get('options', [])
        liga_option = None
        for opt in options:
            if opt.get('name') == 'liga':
                liga_option = opt
                break

        if not liga_option or 'value' not in liga_option:
            print("🟥 [DEBUG] Autocomplete: Brak wybranej ligi.")
            return []

        league_key = liga_option['value']
        league_code = LEAGUE_IDS[league_key]

        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            print("🟥 [DEBUG] Autocomplete: Brak klubów dla tej ligi.")
            return []

        filtered_teams = [
            app_commands.Choice(name=team.get("name", "Unknown"), value=team.get("name", "Unknown"))
            for team in teams
            if current.lower() in team.get("name", "Unknown").lower()
        ][:25]  # Ogranicz do 25 wyników, maksymalna liczba dla Discorda

        return filtered_teams

    @tree.command(
        name="sklad",
        description="Wyświetla skład i informacje o drużynie",
        guild=guild
    )
    @app_commands.describe(
        liga="Wybierz ligę",
        klub="Wybierz klub z wybranej ligi"
    )
    @app_commands.choices(
        liga=[
            app_commands.Choice(name="Premier League", value="premier_league"),
            app_commands.Choice(name="La Liga", value="laliga"),
            app_commands.Choice(name="Bundesliga", value="bundesliga"),
            app_commands.Choice(name="Serie A", value="serie_a"),
            app_commands.Choice(name="Ligue 1", value="ligue_1"),
        ]
    )
    async def sklad(interaction: discord.Interaction, liga: app_commands.Choice[str], klub: str):
        league_key = liga.value
        league_code = LEAGUE_IDS[league_key]
        league_name = LEAGUE_DISPLAY[league_key]

        # Pobierz listę klubów dla wybranej ligi
        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            await interaction.response.send_message(
                "Brak danych o klubach dla wybranej ligi.",
                ephemeral=True
            )
            return

        # Znajdź ID klubu na podstawie nazwy
        team_id = None
        team_data = None
        for team in teams:
            team_name = team.get("name", "").lower()
            if team_name.startswith(klub.lower()) or klub.lower() in team_name:
                team_id = team.get("id")
                team_data = team
                klub = team.get("name")  # Aktualizuj nazwę do pełnej nazwy z API
                break

        if not team_id:
            await interaction.response.send_message(
                f"Nie znaleziono klubu o nazwie {klub} w lidze {league_name}.",
                ephemeral=True
            )
            return

        # Pobierz szczegółowe informacje o drużynie
        team_info = get_team_info(team_id, API_KEY)
        if not team_info:
            await interaction.response.send_message(
                f"Brak danych o drużynie {klub}.",
                ephemeral=True
            )
            return

        # Przygotuj embed z informacjami o drużynie
        embed = discord.Embed(
            title=f"🧑‍🤝‍🧑 Informacje o drużynie: {klub}",
            color=0x066fd1
        )
        
        # Dodaj logo drużyny jako miniaturkę
        team_crest = team_info.get("crest", "")
        if team_crest:
            embed.set_thumbnail(url=team_crest)

        # Dodaj podstawowe informacje
        embed.add_field(name="Nazwa", value=team_info.get("name", "Nieznana"), inline=True)
        embed.add_field(name="Skrót", value=team_info.get("tla", "???"), inline=True)
        embed.add_field(name="Rok założenia", value=str(team_info.get("founded", "Nieznany")), inline=True)
        
        # Dodaj informacje o stadionie
        venue = team_info.get("venue", "Nieznany")
        embed.add_field(name="Stadion", value=venue, inline=True)
        
        # Dodaj informacje o adresie klubu
        address = team_info.get("address", "Nieznany")
        if address:
            embed.add_field(name="Adres", value=address, inline=True)
        
        # Strona klubu
        website = team_info.get("website", "Nieznana")
        if website:
            embed.add_field(name="Strona www", value=website, inline=True)
        
        # Skład drużyny
        squad = team_info.get("squad", [])
        if squad:
            # Podziel zawodników na bramkarzy, obrońców, pomocników i napastników
            goalkeepers = []
            defenders = []
            midfielders = []
            attackers = []
            others = []
            
            for player in squad:
                position = player.get("position", "").lower()
                name = player.get("name", "Nieznany")
                nationality = player.get("nationality", "?")[:3]  # Skrót kraju
                
                player_info = f"{name} ({nationality})"
                
                if "goalkeeper" in position:
                    goalkeepers.append(player_info)
                elif "defender" in position:
                    defenders.append(player_info)
                elif "midfielder" in position:
                    midfielders.append(player_info)
                elif "attacker" in position or "forward" in position:
                    attackers.append(player_info)
                else:
                    others.append(player_info)
            
            # Dodaj pola z zawodnikami do embeda
            if goalkeepers:
                embed.add_field(
                    name="🧤 Bramkarze",
                    value="\n".join(goalkeepers)[:1024],
                    inline=False
                )
            
            if defenders:
                embed.add_field(
                    name="🛡️ Obrońcy",
                    value="\n".join(defenders)[:1024],
                    inline=False
                )
            
            if midfielders:
                embed.add_field(
                    name="🏃 Pomocnicy",
                    value="\n".join(midfielders)[:1024],
                    inline=False
                )
            
            if attackers:
                embed.add_field(
                    name="⚽ Napastnicy",
                    value="\n".join(attackers)[:1024],
                    inline=False
                )
            
            if others:
                embed.add_field(
                    name="Inni zawodnicy",
                    value="\n".join(others)[:1024],
                    inline=False
                )
        else:
            embed.add_field(
                name="Skład",
                value="Brak danych o zawodnikach.",
                inline=False
            )
        
        embed.set_footer(text="Dane: football-data.org")
        
        await interaction.response.send_message(embed=embed)

    @sklad.autocomplete("klub")
    async def klub_autocomplete_sklad(interaction: discord.Interaction, current: str):
        # Pobierz opcje komendy z danych interakcji
        options = interaction.data.get('options', [])
        liga_option = None
        for opt in options:
            if opt.get('name') == 'liga':
                liga_option = opt
                break

        if not liga_option or 'value' not in liga_option:
            print("🟥 [DEBUG] Autocomplete: Brak wybranej ligi.")
            return []

        league_key = liga_option['value']
        league_code = LEAGUE_IDS[league_key]

        teams = get_teams_for_league(league_code, API_KEY)
        if not teams:
            print("🟥 [DEBUG] Autocomplete: Brak klubów dla tej ligi.")
            return []

        filtered_teams = [
            app_commands.Choice(name=team.get("name", "Unknown"), value=team.get("name", "Unknown"))
            for team in teams
            if current.lower() in team.get("name", "Unknown").lower()
        ][:25]  # Ogranicz do 25 wyników, maksymalna liczba dla Discorda

        return filtered_teams