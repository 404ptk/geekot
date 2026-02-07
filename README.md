# 🤖 Geekot Discord Bot

**Geekot** to zaawansowany, wielofunkcyjny bot Discord stworzony z myślą o społeczności graczy i entuzjastów CS2, piłki nożnej oraz streamingu. Bot integruje się z wieloma zewnętrznymi API (Faceit, Leetify, YouTube, Twitch/Kick, Football API), dostarczając statystyki i powiadomienia w czasie rzeczywistym.

## Kluczowe Funkcjonalności

### Integracja z Faceit & CS2
Najbardziej rozbudowany moduł bota, oferujący głęboki wgląd w statystyki graczy.
- **/faceit [nick]** – Szczegółowe statystyki gracza (ELO, poziom, ostatnie mecze).
- **/last [nick]** – Analiza ostatniego meczu wraz z wynikiem (np. 13:11), mapą i statystykami gracza.
- **/discordfaceit** – **Unikalny Ranking Serwera**. Bot śledzi postępy graczy z Discorda, sortuje ich wg ELO i pokazuje:
  - Zmianę pozycji w rankingu (awans/spadek).
  - Różnicę ELO względem ostatniego sprawdzenia.
  - **Dobowy przyrost ELO** – automatyczny system snapshotów, który resetuje się o północy, pokazując "formę dnia".
- **/masny** – Specjalny licznik miejsc zajmowanych przez lokalną legendę, Masnego. Pozwala śledzić historię jego występów.

### Zaawansowane Statystyki Leetify
- **/leetify [nick/steam_id]** – Pobiera dane z Leetify (nawet jeśli profil jest ukryty, o ile API ma dostęp).
- **Automatyczny Ranking Statystyk** – Bot cache'uje statystyki całej grupy graczy raz dziennie i przy każdym wywołaniu komendy przyznaje medale (🥇, 🥈, 🥉) lub "nagrodę pocieszenia" (💩) za konkretne statystyki (Aim, Reakcja, Preaim, Utility) na tle grupy znajomych.

### Piłka Nożna (Football API)
Kompleksowe śledzenie wyników ulubionych drużyn i lig.
- **/tabela**, **/liga** – Aktualne tabele i statystyki ligowe.
- **/ostatniemecze**, **/najblizszemecze** – Wyniki i terminarz konkretnych klubów.
- **/sklad** – Informacje o składzie drużyny.

### Powiadomienia Streamingowe & YouTube
- **YouTube Watcher** – Autorski system monitorowania kanałów YouTube oparty na RSS (bez zużywania limitów API Google). Automatycznie wykrywa nowe filmy, rozwiązuje niestandardowe URL kanałów i publikuje eleganckie embedy na Discordzie.
- **/stan [twitch/kick]** – Szybkie sprawdzanie statusu streamera na platformach Twitch i Kick.

### Rozrywka i Organizacja
- **/wymowki** – Baza losowych wymówek po przegranym meczu (z systemem dodawania przez użytkowników i autouzupełnianiem).
- **/gry** – Zarządzanie listą gier do wspólnego ogrania (Backlog).
- **/wyzwania** – Losowanie wyzwań do CS2.
- **Detekcja obecności** – System "Anti-Plaster", który wykrywa pojawienie się konkretnego użytkownika online i zlicza jego połączenia w ciągu dnia.

## Technologie

Projekt oparty jest na **Python 3** i bibliotece **discord.py**. Wykorzystuje nowoczesne funkcje Discorda:
- **Slash Commands** (app_commands) dla intuicyjnej obsługi.
- **Tasks & Loops** do zadań w tle (monitorowanie YouTube, resetowanie statystyk dobowych).
- **Asynchroniczność** dla szybkiego działania bez blokowania wątków.
- **JSON & TXT** jako lekka baza danych dla konfiguracji i stanu.

## Instalacja i Konfiguracja

1. Sklonuj repozytorium.
2. Zainstaluj wymagane biblioteki:
   ```bash
   pip install -r requirements.txt
   ```
3. Uzupełnij pliki w folderze `txt/` odpowiednimi kluczami API i tokenami:
   - `discord_token.txt` (Token bota)
   - `faceit_api.txt` (Klucz API Faceit)
   - `leetify_api.txt` (Token/Klucz Leetify)
   - `kick_client_id.txt` / `twitch_client_id.txt` (Dla modułów streamingowych)
   - `football-api.txt` (API-Football)
4. Uruchom bota:
   ```bash
   python main.py
   ```

## Struktura Projektu

- **main.py** – Główny plik startowy, ładowanie modułów i pętla zdarzeń.
- **commands/** – Moduły z komendami slash (podzielone tematycznie: football, youtube, fun, etc.).
- **utils.py** (faceit, leetify, masny...) – Logika biznesowa i integracje z API zewnętrznymi.
- **txt/** – Pliki konfiguracyjne i bazy danych (ignorowane w repozytorium publicznym dla bezpieczeństwa).

---
