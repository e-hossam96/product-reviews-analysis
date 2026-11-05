from app.models import NgramCount
from app.ngrams import STOPWORDS, top_ngrams


def pairs(result: list[NgramCount]) -> list[tuple[str, int]]:
    return [(n.ngram, n.count) for n in result]


def test_stopwords_never_start_or_end_an_ngram():
    result = top_ngrams(["The battery life is great", "the battery life is poor"])
    assert {n.ngram for n in result} == {"battery life"}


def test_counts_reviews_not_occurrences():
    result = top_ngrams(["battery battery battery battery", "screen"], max_n=1, min_count=1)
    assert dict(pairs(result)) == {"battery": 1, "screen": 1}


def test_min_count_filters_rare_ngrams():
    result = top_ngrams(["battery great", "battery poor"], max_n=1, min_count=2)
    assert pairs(result) == [("battery", 2)]


def test_drops_parts_with_the_same_count_as_the_phrase():
    texts = [
        "Battery life is great",
        "battery life could be better",
        "I love the battery life",
    ]
    assert pairs(top_ngrams(texts)) == [("battery life", 3)]


def test_keeps_shorter_ngram_when_its_count_is_higher():
    texts = [
        "Battery life is great",
        "battery life could be better",
        "I love the battery life",
        "The battery died fast",
    ]
    assert pairs(top_ngrams(texts)) == [("battery", 4), ("battery life", 3)]


def test_ngrams_do_not_span_punctuation():
    texts = ["Great battery, screen is sharp", "Love the battery, screen too"]
    assert {n.ngram for n in top_ngrams(texts)} == {"battery", "screen"}


def test_trigram_absorbs_its_parts():
    texts = ["fast wireless charging works", "I like fast wireless charging"]
    assert pairs(top_ngrams(texts)) == [("fast wireless charging", 2)]


def test_max_n_one_returns_only_unigrams():
    result = top_ngrams(["fast charging", "fast charging"], max_n=1)
    assert pairs(result) == [("charging", 2), ("fast", 2)]


def test_unicode_is_lowercased_and_kept():
    result = top_ngrams(["Café Crème", "café crème"])
    assert pairs(result) == [("café crème", 2)]


def test_digits_are_kept_inside_names_but_not_alone():
    texts = ["iphone 15 pro is great", "love my iphone 15 pro"]
    assert pairs(top_ngrams(texts)) == [("iphone 15 pro", 2)]


def test_top_k_and_ordering():
    texts = ["alpha beta", "alpha beta", "alpha gamma", "delta"]
    result = top_ngrams(texts, max_n=1, min_count=1, top_k=2)
    assert pairs(result) == [("alpha", 3), ("beta", 2)]


def test_empty_and_stopword_only_input():
    assert top_ngrams([]) == []
    assert top_ngrams(["the a an"]) == []


def test_stopwords_are_clean_single_words():
    assert all(w == w.strip().lower() and " " not in w for w in STOPWORDS)
    assert max(len(w) for w in STOPWORDS) <= 12  # catches accidentally merged entries
    assert {"the", "about", "above", "don't"} <= STOPWORDS
