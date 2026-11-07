import csv
import io

from app.aggregate import ExportRow, build_export_csv, build_results, csv_safe, title_case
from app.ai import ProductDetails

PRODUCT = ProductDetails(name="Galaxy S24", aspects=["battery life", "screen", "price"])


def test_results_mean_distribution_and_order():
    result = build_results(
        PRODUCT,
        review_count=5,
        analyzed_count=4,
        failed_count=1,
        scores=[("screen", 5), ("battery life", 2), ("screen", 4), ("battery life", 2)],
    )
    assert [a.aspect for a in result.aspects] == ["Battery Life", "Screen", "Price"]
    battery, screen, _price = result.aspects
    assert (battery.mean_score, battery.mention_count) == (2.0, 2)
    assert (screen.mean_score, screen.mention_count) == (4.5, 2)
    assert battery.distribution == {1: 0, 2: 2, 3: 0, 4: 0, 5: 0}
    assert screen.distribution == {1: 0, 2: 0, 3: 0, 4: 1, 5: 1}
    assert (result.review_count, result.analyzed_count, result.failed_count) == (5, 4, 1)


def test_unmentioned_aspect_has_no_mean_but_a_full_distribution():
    price = build_results(
        PRODUCT, review_count=1, analyzed_count=1, failed_count=0, scores=[]
    ).aspects[2]
    assert price.mean_score is None and price.mention_count == 0
    assert price.distribution == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


def test_scores_for_aspects_outside_the_product_are_ignored():
    result = build_results(
        PRODUCT, review_count=1, analyzed_count=1, failed_count=0, scores=[("camera", 5)]
    )
    assert all(a.mention_count == 0 for a in result.aspects)


def test_mean_is_rounded_to_two_decimals():
    result = build_results(
        PRODUCT,
        review_count=3,
        analyzed_count=3,
        failed_count=0,
        scores=[("screen", 5), ("screen", 5), ("screen", 4)],
    )
    assert result.aspects[1].mean_score == 4.67


def test_csv_safe_neutralizes_formulas_only():
    assert csv_safe("=1+1") == "'=1+1"
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe("-5 degrees") == "'-5 degrees"
    assert csv_safe("Great battery") == "Great battery"
    assert csv_safe("1+1=2") == "1+1=2"


def test_export_layout():
    rows = [
        ExportRow(2, "second, with comma", "done", {"screen": 4}),
        ExportRow(0, "first", "done", {"battery life": 5, "screen": 1}),
        ExportRow(1, "=HYPERLINK(\"http://x\")", "failed"),
    ]
    data = build_export_csv(PRODUCT, rows)
    assert data.startswith(b"\xef\xbb\xbf")
    table = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert table[0] == ["row", "text", "status", "Battery Life", "Screen", "Price"]
    assert table[1] == ["1", "first", "done", "5", "1", ""]
    assert table[2] == ["2", "'=HYPERLINK(\"http://x\")", "failed", "", "", ""]
    assert table[3] == ["3", "second, with comma", "done", "", "4", ""]


def test_title_case():
    assert title_case("samsung headphones") == "Samsung Headphones"
    assert title_case("battery life") == "Battery Life"
    assert title_case("value for money") == "Value for Money"
    assert title_case("noise-cancelling") == "Noise-Cancelling"
    assert title_case("iPhone 15 Pro") == "iPhone 15 Pro"
    assert title_case("for kids") == "For Kids"


def test_results_are_titled():
    result = build_results(
        ProductDetails(name="samsung headphones", aspects=["battery life"]),
        review_count=0,
        analyzed_count=0,
        failed_count=0,
        scores=[],
    )
    assert result.product_name == "Samsung Headphones"
    assert result.aspects[0].aspect == "Battery Life"


def test_export_header_is_formula_safe():
    product = ProductDetails(name="X", aspects=["=cmd"])
    header = build_export_csv(product, []).decode("utf-8-sig").splitlines()[0]
    assert header == "row,text,status,'=cmd"
