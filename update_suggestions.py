#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOVIES_FILE = ROOT / "movies.json"
SUGGESTIONS_FILE = ROOT / "suggestions.json"
TMDB_BASE = "https://api.themoviedb.org/3"

GENRE_IDS = {
    28: "Action", 12: "Abenteuer", 16: "Animation", 35: "Komödie",
    80: "Krimi", 99: "Dokumentation", 18: "Drama", 10751: "Familie",
    14: "Fantasy", 36: "Historie", 27: "Horror", 10402: "Musik",
    9648: "Mystery", 10749: "Romantik", 878: "Sci-Fi",
    53: "Thriller", 10752: "Krieg", 37: "Western"
}
DISCOVERY_GENRES = [28,18,53,80,9648,27,878,35,10749,10751,16,14,12,10402]

def normalize_title(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii","ignore").decode("ascii")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-zA-Z0-9]+", " ", value).lower()
    return " ".join(value.split())

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def existing_titles():
    data = read_json(MOVIES_FILE)
    rows = data.get("movies", data if isinstance(data, list) else [])
    out = set()
    for row in rows:
        if isinstance(row, dict):
            t = row.get("title", "")
        else:
            t = str(row)
        if t:
            out.add(normalize_title(t))
    return out

def tmdb_get(path, params, api_key):
    q = dict(params)
    q["api_key"] = api_key
    url = TMDB_BASE + path + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent":"Maeuse-Filmliste-Sonderedition/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def collect(api_key):
    pool = {}
    common = {
        "language": "de-DE",
        "include_adult": "false",
        "include_video": "false",
        "sort_by": "popularity.desc",
        "vote_count.gte": 120,
        "vote_average.gte": 6.3
    }
    for genre in DISCOVERY_GENRES:
        for page in (1,2):
            params = dict(common)
            params.update({"with_genres": genre, "page": page})
            try:
                data = tmdb_get("/discover/movie", params, api_key)
            except Exception as exc:
                print(f"WARN: TMDB-Abfrage Genre {genre}, Seite {page}: {exc}", file=sys.stderr)
                continue
            for m in data.get("results", []):
                if m.get("adult") or not m.get("title"):
                    continue
                pool[m["id"]] = m
            time.sleep(0.08)
    return list(pool.values())

def make_item(m, kind):
    date = m.get("release_date") or ""
    year = int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None
    return {
        "id": f"tmdb-{m['id']}",
        "title": m.get("title") or m.get("original_title") or "",
        "year": year,
        "genres": [GENRE_IDS[g] for g in m.get("genre_ids", []) if g in GENRE_IDS],
        "rating": round(float(m.get("vote_average") or 0), 1),
        "description": (m.get("overview") or "").strip(),
        "kind": kind,
        "tmdb_id": m["id"]
    }

def choose(pool, existing):
    fresh = [m for m in pool if normalize_title(m.get("title")) not in existing]
    # Geheimtipps: solide bewertet, genügend Stimmen, aber nicht nur die allergrößten Popularitätswerte.
    gems = sorted(
        [m for m in fresh if (m.get("vote_count") or 0) >= 250 and (m.get("vote_average") or 0) >= 6.7],
        key=lambda m: ((m.get("vote_average") or 0) * 12 + min(m.get("vote_count") or 0, 5000)/700 - (m.get("popularity") or 0)/250),
        reverse=True
    )
    selected, ids = [], set()
    for m in gems:
        if m["id"] in ids: continue
        selected.append(make_item(m, "Geheimtipp"))
        ids.add(m["id"])
        if len(selected) == 12: break

    # Blockbuster/Trend: Popularität + viele Stimmen, getrennt von den Geheimtipps.
    trends = sorted(
        fresh,
        key=lambda m: ((m.get("popularity") or 0), (m.get("vote_count") or 0), (m.get("vote_average") or 0)),
        reverse=True
    )
    for m in trends:
        if m["id"] in ids: continue
        if (m.get("vote_count") or 0) < 500: continue
        selected.append(make_item(m, "Blockbuster / Trend"))
        ids.add(m["id"])
        if len(selected) == 20: break
    return selected

def validate():
    movies = read_json(MOVIES_FILE)
    suggestions = read_json(SUGGESTIONS_FILE)
    rows = movies.get("movies", [])
    sug = suggestions.get("movies", [])
    assert isinstance(rows, list) and len(rows) == 200, f"movies.json: erwartet 200, gefunden {len(rows)}"
    assert isinstance(sug, list), "suggestions.json: 'movies' muss eine Liste sein"
    for item in sug:
        for key in ("id","title","genres","description"):
            assert key in item, f"suggestions.json: Feld '{key}' fehlt"
    print(f"OK: movies.json={len(rows)} Filme, suggestions.json={len(sug)} Vorschläge")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    if args.validate_only:
        validate()
        return

    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("TMDB_API_KEY fehlt. In GitHub unter Settings > Secrets and variables > Actions als Repository secret anlegen.")

    existing = existing_titles()
    pool = collect(api_key)
    chosen = choose(pool, existing)
    if len(chosen) < 10:
        raise SystemExit(f"Zu wenige neue Vorschläge von TMDB erhalten ({len(chosen)}). suggestions.json bleibt unverändert.")

    doc = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "TMDB",
        "count": len(chosen),
        "movies": chosen
    }
    SUGGESTIONS_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"suggestions.json aktualisiert: {len(chosen)} Vorschläge")
    validate()

if __name__ == "__main__":
    main()
