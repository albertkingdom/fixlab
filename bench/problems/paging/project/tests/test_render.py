from pager.display import render_page


def test_exact_multiple_of_the_page_size():
    items = [f"item{n}" for n in range(1, 11)]
    assert render_page(items, 2, 5) == "item6\nitem7\nitem8\nitem9\nitem10\nPage 2/2"


def test_last_partial_page():
    items = [f"item{n}" for n in range(1, 12)]
    assert render_page(items, 3, 5) == "item11\nPage 3/3"
