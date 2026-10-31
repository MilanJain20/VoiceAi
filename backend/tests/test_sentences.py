"""Sentence splitter: the first piece is allowed to be short."""

from app.services.audio.sentences import FIRST_CHUNK_MIN, split_sentence


def test_first_chunk_splits_on_a_short_clause() -> None:
    ready, rest = split_sentence(
        "Hello there, this is a longer thought that continues.", first_chunk=True
    )
    assert ready.endswith(",")
    assert len(ready) >= FIRST_CHUNK_MIN
    assert rest.startswith("this")


def test_later_chunk_waits_for_more_text() -> None:
    ready, rest = split_sentence("Hello there, friend.", first_chunk=False)
    assert ready == ""
    assert "Hello" in rest


def test_later_chunk_splits_on_sentence_end() -> None:
    text = "This sentence is definitely long enough to speak. Next one starts here."
    ready, rest = split_sentence(text, first_chunk=False)
    assert ready.endswith(".")
    assert rest.startswith("Next")
