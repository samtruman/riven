"""Regression tests for the narrow Italian audio/subtitle policy.

RTN remains responsible for regular filtering and ordering.  These tests only
cover the information RTN's flat language list cannot represent.
"""
from types import SimpleNamespace

from program.services.scrapers import shared


class Candidate:
    def __init__(self, infohash: str):
        self.infohash = infohash


def test_release_kind_distinguishes_audio_from_subtitles():
    assert shared._italian_release_kind("Example.S01E01.ITA.1080p") == "audio"
    assert shared._italian_release_kind("Example.S01E01.Subs.ITA.2160p") == "subtitles"
    assert shared._italian_release_kind("Example.S01E01.2160p") == "none"


def test_subtitle_only_candidate_is_a_fallback(monkeypatch):
    audio = Candidate("audio")
    subtitles = Candidate("subtitles")
    ranking = SimpleNamespace(
        languages=SimpleNamespace(required=["it"]),
        prefer_explicit_italian_audio=True,
    )
    monkeypatch.setattr(
        shared.settings_manager, "settings", SimpleNamespace(ranking=ranking)
    )

    assert shared._apply_italian_audio_policy(
        {audio, subtitles}, {"audio": "audio", "subtitles": "subtitles"}
    ) == {audio}
    assert shared._apply_italian_audio_policy(
        {subtitles}, {"subtitles": "subtitles"}
    ) == {subtitles}


def test_disabling_policy_leaves_ordering_to_rtn(monkeypatch):
    audio = Candidate("audio")
    subtitles = Candidate("subtitles")
    ranking = SimpleNamespace(
        languages=SimpleNamespace(required=["it"]),
        prefer_explicit_italian_audio=False,
    )
    monkeypatch.setattr(
        shared.settings_manager, "settings", SimpleNamespace(ranking=ranking)
    )

    candidates = {audio, subtitles}
    assert shared._apply_italian_audio_policy(
        candidates, {"audio": "audio", "subtitles": "subtitles"}
    ) == candidates
