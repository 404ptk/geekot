# Geekot Discord Bot

### 📅 Changelog (07.02.2026)
- **/discordfaceit**: Added form emojis (🔥/😭), improved table layout, added last 5 matches history (W/L).
- **/last**: Added ADR column, sorting by ADR (descending), reorganized columns.

**Geekot** is an advanced, multi-purpose Discord bot created for the community of gamers and enthusiasts of CS2, football, and streaming. The bot integrates with multiple external APIs (Faceit, Leetify, YouTube, Twitch/Kick, Football API), providing real-time statistics and notifications.

## Key Features

### Faceit & CS2 Integration
The most extensive module of the bot, offering deep insight into player statistics.
- **/faceit [nick]** - Detailed player statistics (ELO, level, recent matches).
- **/last [nick]** - Analysis of the last match with the result (e.g. 13:11), map, and player statistics.
- **/discordfaceit** - **Unique Server Ranking**. The bot tracks the progress of Discord players, sorts them by ELO and shows:
  - Rank position change (promotion/demotion).
  - ELO difference compared to the last check.
  - **Daily ELO gain** - automatic snapshot system that resets at midnight, showing "form of the day".
- **/masny** - Special counter for places taken by the local legend, Masny. Allows tracking his performance history.

### Leetify Advanced Statistics
- **/leetify [nick/steam_id]** - Fetches data from Leetify (even if the profile is hidden, provided the API has access).
- **Automatic Stats Ranking** - The bot caches statistics for a group of players once a day and upon command invocation awards medals or a "consolation prize" for specific statistics (Aim, Reaction, Preaim, Utility) against the friend group.

### Football (Football API)
Comprehensive tracking of favorite teams and league results.
- **/tabela**, **/liga** - Current league tables and statistics.
- **/ostatniemecze**, **/najblizszemecze** - Results and schedule for specific clubs.
- **/sklad** - Team squad information.

### Streaming Notifications & YouTube
- **YouTube Watcher** - Proprietary YouTube channel monitoring system based on RSS (without consuming Google API quotas). Automatically detects new videos, resolves custom channel URLs, and publishes elegant embeds on Discord.
- **/stan [twitch/kick]** - Quick check of streamer status on Twitch and Kick platforms.

### Entertainment and Organization
- **/wymowki** - Database of random excuses after a lost match (with user submission system and autocomplete).
- **/gry** - Management of games list to play together (Backlog).
- **/wyzwania** - Random CS2 challenges.
- **Presence Detection** - "Anti-Plaster" system that detects the appearance of a specific user online and counts their connections during the day.

## Technologies

The project is based on **Python 3** and the **discord.py** library. It uses modern Discord features:
- **Slash Commands** (app_commands) for intuitive usage.
- **Tasks & Loops** for background tasks (YouTube monitoring, daily stats reset).
- **Asynchronous** operations for fast performance without blocking threads.
- **JSON & TXT** as a lightweight database for configuration and state.

## Installation and Configuration

1. Clone the repository.
2. Install required libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. Fill the files in the `txt/` folder with appropriate API keys and tokens:
   - `discord_token.txt` (Bot Token)
   - `faceit_api.txt` (Faceit API Key)
   - `leetify_api.txt` (Leetify Token/Key)
   - `kick_client_id.txt` / `twitch_client_id.txt` (For streaming modules)
   - `football-api.txt` (API-Football)
4. Run the bot:
   ```bash
   python main.py
   ```

## Project Structure

- **main.py** - Main entry point, module loading, and event loop.
- **commands/** - Modules with slash commands (grouped by topic: football, youtube, fun, etc.).
- **utils.py** (faceit, leetify, masny...) - Business logic and external API integrations.
- **txt/** - Configuration files and databases (ignored in public repository for security).

---
