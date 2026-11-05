import pytest

from app.ingest import IngestError, clean_text, parse_reviews, sample_reviews


def parse(csv_text: str, *, max_rows=100, max_bytes=1_000_000, encoding="utf-8"):
    return parse_reviews(csv_text.encode(encoding), max_rows=max_rows, max_bytes=max_bytes)


def test_parses_basic_csv():
    result = parse("id,text\n1,Great battery\n2,Screen is sharp\n")
    assert [r.text for r in result.reviews] == ["Great battery", "Screen is sharp"]
    assert (result.total_rows, result.skipped_empty) == (2, 0)


def test_row_index_preserved_when_rows_skipped():
    result = parse("text\nfirst\n   \nthird\n")
    assert [(r.row_index, r.text) for r in result.reviews] == [(0, "first"), (2, "third")]
    assert (result.total_rows, result.skipped_empty) == (3, 1)


def test_header_is_case_insensitive_and_bom_safe():
    result = parse("\ufeff Text ,id\nGreat,1\n")
    assert [r.text for r in result.reviews] == ["Great"]


@pytest.mark.parametrize("delimiter", [";", "\t", "|"])
def test_detects_delimiter(delimiter):
    result = parse(f"id{delimiter}text\n1{delimiter}Great battery\n")
    assert [r.text for r in result.reviews] == ["Great battery"]


def test_missing_text_column_lists_found_columns():
    with pytest.raises(IngestError, match=r"'text'.*id, review"):
        parse("id,review\n1,Great\n")


def test_cp1252_fallback():
    result = parse("text\ncafé au lait\n", encoding="cp1252")
    assert result.reviews[0].text == "café au lait"


def test_clean_text_strips_html_urls_and_extra_whitespace():
    raw = "Great <b>battery</b> &amp; screen!\n\n  See https://example.com/x?a=1 and www.foo.com  now\x00"
    assert clean_text(raw) == "Great battery & screen! See and now"


def test_clean_text_keeps_comparison_symbols():
    text = "paid <5 dollars, rated >3 stars"
    assert clean_text(text) == text


def test_quoted_multiline_field_is_collapsed():
    result = parse('id,text\n1,"Line one\nline two, with comma"\n')
    assert result.reviews[0].text == "Line one line two, with comma"


def test_row_limit_enforced():
    with pytest.raises(IngestError, match="more than 2 rows"):
        parse("text\na\nb\nc\n", max_rows=2)


def test_size_limit_enforced():
    with pytest.raises(IngestError, match="larger than"):
        parse("text\n" + "x" * 50, max_bytes=10)


def test_empty_file_rejected():
    with pytest.raises(IngestError, match="empty"):
        parse("")
    with pytest.raises(IngestError, match="empty"):
        parse("  \n")


def test_no_usable_reviews_rejected():
    with pytest.raises(IngestError, match="No non-empty"):
        parse("text\n \n \n")
    with pytest.raises(IngestError, match="No non-empty"):
        parse("text\n")


def test_row_shorter_than_header_is_treated_as_empty():
    result = parse("id,text\n1\n2,ok\n")
    assert [(r.row_index, r.text) for r in result.reviews] == [(1, "ok")]
    assert result.skipped_empty == 1


def test_sample_reviews_is_deterministic_and_truncated():
    texts = [f"review number {i} " + "x" * 100 for i in range(50)]
    a = sample_reviews(texts, k=5, max_chars=30)
    b = sample_reviews(texts, k=5, max_chars=30)
    assert a == b
    assert len(a) == 5
    assert all(len(t) <= 30 for t in a)


def test_sample_reviews_returns_everything_when_pool_is_small():
    result = sample_reviews(["short", "tiny"], k=10, max_chars=100)
    assert sorted(result) == ["short", "tiny"]


def test_exactly_max_rows_is_accepted():
    result = parse("text\na\nb\n", max_rows=2)
    assert len(result.reviews) == 2
