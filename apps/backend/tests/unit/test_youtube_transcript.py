"""Canal transcript YouTube : selection de piste et parsing json3.

Aucun reseau : on teste les fonctions pures qui decident quelle piste lire
et comment l'aplatir en texte.
"""

from __future__ import annotations

import json

from app.extractors.youtube_oracle import parse_json3_transcript, pick_subtitle_track


def _json3(*chunks: str) -> str:
    return json.dumps({"events": [{"segs": [{"utf8": c}]} for c in chunks]})


def test_parse_json3_joins_segments_and_collapses_whitespace():
    payload = _json3("Une etude", " de\nStroop", "  en 1935.")
    assert parse_json3_transcript(payload) == "Une etude de Stroop en 1935."


def test_parse_json3_ignores_events_without_segs():
    payload = json.dumps({"events": [{"tStartMs": 0}, {"segs": [{"utf8": "ok"}]}]})
    assert parse_json3_transcript(payload) == "ok"


def test_parse_json3_empty_or_malformed_returns_none():
    assert parse_json3_transcript("{not json") is None
    assert parse_json3_transcript(json.dumps({"events": []})) is None
    assert parse_json3_transcript(_json3("   ")) is None


def _track(ext: str = "json3") -> list[dict]:
    return [{"ext": "vtt", "url": "u-vtt"}, {"ext": ext, "url": f"u-{ext}"}]


def test_pick_prefers_manual_subtitles_over_automatic():
    # L'ASR massacre les noms propres, precisement ce qu'on cherche.
    info = {
        "language": "en",
        "subtitles": {"en": _track()},
        "automatic_captions": {"en": _track()},
    }
    assert pick_subtitle_track(info) == ("en", "u-json3")

    info_auto_only = {"language": "en", "automatic_captions": {"en": _track()}}
    assert pick_subtitle_track(info_auto_only) == ("en", "u-json3")


def test_pick_prefers_video_language():
    info = {
        "language": "de",
        "subtitles": {"en": _track(), "de": _track(), "fr": _track()},
    }
    assert pick_subtitle_track(info)[0] == "de"


def test_pick_falls_back_to_any_language():
    # Agnostique : une video en japonais sans piste fr/en reste exploitable.
    info = {"subtitles": {"ja": _track()}}
    assert pick_subtitle_track(info) == ("ja", "u-json3")


def test_pick_requires_json3_format():
    # Le vtt automatique repete chaque ligne dans la fenetre suivante.
    info = {"subtitles": {"en": [{"ext": "vtt", "url": "u-vtt"}]}}
    assert pick_subtitle_track(info) is None


def test_pick_none_when_no_tracks():
    assert pick_subtitle_track({}) is None
    assert pick_subtitle_track({"subtitles": {}, "automatic_captions": {}}) is None


def test_split_transcript_covers_whole_text():
    # ~55k chars = une heure de parole, le cas nominal qui depassait le
    # plafond d'entree du LLM et perdait la fin de la video.
    from app.services.llm import split_transcript

    text = " ".join(f"mot{i}" for i in range(8_000))
    chunks = split_transcript(text, size=10_000)
    assert len(chunks) > 1
    assert all(len(c) <= 10_000 for c in chunks)
    assert " ".join(chunks) == text


def test_split_transcript_caps_absurdly_long_input():
    # Borne de cout LLM : au-dela (~5 h de parole) on tronque sciemment.
    from app.services.llm import _TRANSCRIPT_MAX_CHUNKS, split_transcript

    text = " ".join(f"mot{i}" for i in range(100_000))
    assert len(split_transcript(text, size=10_000)) == _TRANSCRIPT_MAX_CHUNKS


def test_split_transcript_short_text_single_chunk():
    from app.services.llm import split_transcript

    assert split_transcript("une phrase courte") == ["une phrase courte"]
    assert split_transcript("   ") == []
