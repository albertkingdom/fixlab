from pager.display import render_page


def test_first_page_of_an_exact_multiple():
    assert render_page(["a", "b", "c", "d"], 1, 2) == "a\nb\nPage 1/2 (next)"


def test_no_items():
    assert render_page([], 1, 5) == "(no items)\nPage 1/1"


def test_a_page_before_the_start_shows_the_first_page():
    assert render_page(["a", "b", "c"], 0, 3) == "a\nb\nc\nPage 1/1"
