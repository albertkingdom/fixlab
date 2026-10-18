from pager.display import render_page


def test_second_page_of_eleven_has_a_next_page():
    items = [f"item{n}" for n in range(1, 12)]
    assert render_page(items, 2, 5) == "item6\nitem7\nitem8\nitem9\nitem10\nPage 2/3 (next)"


def test_one_item_over_the_page_size_makes_a_second_page():
    assert render_page(["a", "b", "c", "d"], 2, 3) == "d\nPage 2/2"


def test_a_page_beyond_the_end_shows_the_last_page():
    items = [f"item{n}" for n in range(1, 8)]
    assert render_page(items, 9, 3) == "item7\nPage 3/3"
