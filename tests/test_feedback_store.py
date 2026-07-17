from pathlib import Path

import pytest

from core.feedback.store import add_comment, comment_counts, load_comments, save_comments


def test_add_and_load_comments(tmp_path: Path):
    entry = add_comment(
        author="سارة",
        comment="فكرة رائعة!",
        sentiment="positive",
        data_dir=tmp_path,
    )
    assert entry["author"] == "سارة"
    assert entry["sentiment"] == "positive"

    loaded = load_comments(data_dir=tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["comment"] == "فكرة رائعة!"


def test_newest_comment_first(tmp_path: Path):
    add_comment(author="أ", comment="أول", data_dir=tmp_path)
    add_comment(author="ب", comment="ثاني", data_dir=tmp_path)
    loaded = load_comments(data_dir=tmp_path)
    assert loaded[0]["comment"] == "ثاني"
    assert loaded[1]["comment"] == "أول"


def test_comment_counts(tmp_path: Path):
    add_comment(author="x", comment="1", sentiment="positive", data_dir=tmp_path)
    add_comment(author="y", comment="2", sentiment="neutral", data_dir=tmp_path)
    add_comment(author="z", comment="3", sentiment="negative", data_dir=tmp_path)
    counts = comment_counts(load_comments(data_dir=tmp_path))
    assert counts == {"positive": 1, "neutral": 1, "negative": 1}


def test_empty_comment_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="نص التعليق"):
        add_comment(author="x", comment="   ", data_dir=tmp_path)


def test_load_missing_file_returns_empty(tmp_path: Path):
    assert load_comments(data_dir=tmp_path) == []


def test_save_and_reload_roundtrip(tmp_path: Path):
    comments = [
        {
            "id": "1",
            "author": "test",
            "comment": "ok",
            "sentiment": "neutral",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    save_comments(comments, data_dir=tmp_path)
    assert load_comments(data_dir=tmp_path) == comments
