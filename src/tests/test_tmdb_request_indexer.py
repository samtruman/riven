from program.media.item import MediaItem
from program.media.state import States
from program.services.indexers.tmdb_request import TmdbRequestIndexer


def test_indexes_movie_from_tmdb_without_trakt(monkeypatch):
    indexer = TmdbRequestIndexer()
    monkeypatch.setattr(indexer, "get", lambda *_args, **_kwargs: {
        "title": "Example", "release_date": "2020-01-02", "imdb_id": "tt0000001",
        "genres": [], "original_language": "en",
    })
    item = next(indexer.run(MediaItem({"tmdb_id": "1", "requested_by": "test", "aliases": {"request": {"type": "movie"}}})))
    assert item.tmdb_id == "1"
    assert item.imdb_id == "tt0000001"
    assert item.id == "movie_tmdb_1"


def test_keeps_episode_selection_paused(monkeypatch):
    indexer = TmdbRequestIndexer()

    def tmdb(path, **_kwargs):
        if path == "/tv/2":
            return {"name": "Example", "first_air_date": "2020-01-02", "external_ids": {}, "genres": [], "seasons": [{"season_number": 1, "name": "Season 1", "air_date": "2020-01-02"}]}
        return {"episodes": [{"episode_number": 1, "name": "One", "air_date": "2020-01-02"}, {"episode_number": 2, "name": "Two", "air_date": "2020-01-02"}]}

    monkeypatch.setattr(indexer, "get", tmdb)
    request = MediaItem({"tmdb_id": "2", "requested_by": "test", "aliases": {"request": {"type": "show", "episodes": {"1": [2]}}}})
    show = next(indexer.run(request))
    first, second = show.seasons[0].episodes
    assert first.last_state == States.Paused
    assert second.last_state != States.Paused
