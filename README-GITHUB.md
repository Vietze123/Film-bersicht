# Deine persönliche Filmliste – Sonderedition

Dieses Paket ist für das separate GitHub-Repository der Sonderedition gedacht.

## Enthalten
- `index.html` – Sonderedition ohne Designmodus, 200 Filme
- `movies.json` – dieselben 200 Filme im von der App erwarteten JSON-Format
- `suggestions.json` – Startbestand für „Neue Filme“
- `scripts/update_suggestions.py` – automatische TMDB-Suche
- `.github/workflows/update-movie-suggestions.yml` – wöchentlich + manuell
- `manifest.webmanifest`, `sw.js`, Icons – PWA/GitHub-Pages-Dateien

## Einmalig in GitHub einrichten
1. Alle Dateien und Ordner in die Repository-Wurzel übernehmen.
2. Unter **Settings → Secrets and variables → Actions** ein Repository Secret namens `TMDB_API_KEY` anlegen.
3. Unter **Settings → Actions → General → Workflow permissions** muss der Workflow Schreibrechte auf Repository-Inhalte erhalten können. Das Workflow-YAML setzt `contents: write`.
4. GitHub Pages wie gewohnt auf `main` / `/(root)` stellen.
5. Unter **Actions → Neue Filmvorschläge aktualisieren → Run workflow** einmal manuell testen.

Der Workflow läuft außerdem montags um 05:20 UTC automatisch.

## Wichtig
`suggestions.json` hat absichtlich die Struktur `{ "movies": [...] }`, weil genau diese Struktur von „Neue Filme“ in der HTML gelesen wird.
`movies.json` verwendet ebenfalls `{ "movies": [...] }`, passend zum bestehenden Datenbank-Loader.
