"""TMDb-first indexer for user requests.

The request API receives stable TMDb identities from compatible request
managers.  The legacy implementation discarded that information and required
Trakt to convert it to IMDb before indexing.  This indexer builds normal
Riven objects directly from TMDb, after which the usual scraper, downloader
and symlinker stages are unchanged.
"""

from datetime import datetime, time
from typing import Generator, Optional, Union

import requests
from loguru import logger

from program.media.item import Episode, MediaItem, Movie, Season, Show
from program.media.state import States
from program.services.indexers.tmdb import TMDB_READ_ACCESS_TOKEN


class TmdbRequestIndexer:
    key = "TmdbRequestIndexer"

    def __init__(self):
        self.key = "tmdbrequestindexer"
        self.initialized = True
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {TMDB_READ_ACCESS_TOKEN}"})

    def get(self, path: str, **params) -> dict:
        response = self.session.get(f"https://api.themoviedb.org/3{path}", params=params, timeout=20)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def date(value: Optional[str]) -> Optional[datetime]:
        try:
            return datetime.combine(datetime.strptime(value, "%Y-%m-%d").date(), time.min) if value else None
        except ValueError:
            return None

    @staticmethod
    def key_for(tmdb_id: str, suffix: str = "") -> str:
        # MediaItem primary keys derive from trakt_id. This is an internal,
        # namespaced stable value, never a real Trakt ID.
        return f"tmdb_{tmdb_id}{suffix}"

    def resolve(self, item: MediaItem) -> tuple[str, str, dict] | None:
        request = (item.aliases or {}).get("request", {})
        requested_type = item.type if item.type in {"movie", "show"} else request.get("type")
        if item.tmdb_id and requested_type:
            kind = "tv" if requested_type == "show" else "movie"
            return kind, str(item.tmdb_id), self.get(f"/{kind}/{item.tmdb_id}", append_to_response="external_ids")
        if not item.imdb_id:
            return None
        found = self.get(f"/find/{item.imdb_id}", external_source="imdb_id")
        choices = []
        if requested_type != "show":
            choices.extend(("movie", row) for row in found.get("movie_results", []))
        if requested_type != "movie":
            choices.extend(("tv", row) for row in found.get("tv_results", []))
        if len(choices) != 1:
            logger.error(f"TMDb could not resolve a unique item for {item.imdb_id}")
            return None
        kind, row = choices[0]
        return kind, str(row["id"]), self.get(f"/{kind}/{row['id']}", append_to_response="external_ids")

    @staticmethod
    def copy_request(source: MediaItem, target: MediaItem) -> None:
        for attr in ("requested_at", "requested_by", "requested_id", "overseerr_id", "is_anime"):
            setattr(target, attr, getattr(source, attr, None))
        target.aliases = dict(source.aliases or {})

    @staticmethod
    def selection(item: MediaItem) -> tuple[Optional[set[int]], dict[int, set[int]]]:
        request = (item.aliases or {}).get("request", {})
        try:
            episodes = {int(season): {int(episode) for episode in values} for season, values in request.get("episodes", {}).items()}
            seasons = {int(value) for value in request.get("seasons", [])} or set(episodes)
            return seasons or None, episodes
        except (AttributeError, TypeError, ValueError):
            logger.warning("Ignoring invalid request selection")
            return None, {}

    def make_movie(self, tmdb_id: str, data: dict) -> Movie:
        date = data.get("release_date")
        return Movie({"type": "movie", "trakt_id": self.key_for(tmdb_id), "tmdb_id": tmdb_id,
            "imdb_id": data.get("imdb_id"), "title": data.get("title") or data.get("original_title"),
            "year": int(date[:4]) if date else None, "aired_at": self.date(date),
            "genres": [genre["name"] for genre in data.get("genres", [])],
            "language": data.get("original_language")})

    def make_show(self, tmdb_id: str, data: dict, selection) -> Show:
        date = data.get("first_air_date")
        external = data.get("external_ids") or {}
        show = Show({"type": "show", "trakt_id": self.key_for(tmdb_id), "tmdb_id": tmdb_id,
            "imdb_id": external.get("imdb_id"), "title": data.get("name") or data.get("original_name"),
            "year": int(date[:4]) if date else None, "aired_at": self.date(date),
            "genres": [genre["name"] for genre in data.get("genres", [])],
            "language": data.get("original_language")})
        seasons, requested_episodes = selection
        for summary in data.get("seasons", []):
            number = summary.get("season_number")
            if number in (None, 0):
                continue
            number = int(number)
            season = Season({"type": "season", "trakt_id": self.key_for(tmdb_id, f"_s{number}"), "number": number,
                "title": summary.get("name"), "aired_at": self.date(summary.get("air_date"))})
            allowed = seasons is None or number in seasons
            only = requested_episodes.get(number)
            for row in self.get(f"/tv/{tmdb_id}/season/{number}").get("episodes", []):
                episode_number = int(row["episode_number"])
                episode = Episode({"type": "episode", "trakt_id": self.key_for(tmdb_id, f"_s{number}_e{episode_number}"), "number": episode_number,
                    "title": row.get("name"), "aired_at": self.date(row.get("air_date"))})
                if not allowed or (only and episode_number not in only):
                    episode.last_state = States.Paused
                season.add_episode(episode)
            if not allowed or (only and not any(item.number in only for item in season.episodes)):
                season.last_state = States.Paused
            show.add_season(season)
        show.propagate_attributes_to_childs()
        return show

    def run(self, incoming: MediaItem, log_msg: bool = True) -> Generator[Union[Movie, Show], None, None]:
        try:
            resolved = self.resolve(incoming)
        except requests.RequestException as exc:
            logger.error(f"TMDb request indexing failed: {exc}")
            return
        if not resolved:
            return
        kind, tmdb_id, data = resolved
        indexed = self.make_movie(tmdb_id, data) if kind == "movie" else self.make_show(tmdb_id, data, self.selection(incoming))
        self.copy_request(incoming, indexed)
        indexed.indexed_at = datetime.now()
        if log_msg:
            logger.info(f"Indexed TMDb id ({tmdb_id}) as {indexed.type.title()}: {indexed.log_string}")
        yield indexed
