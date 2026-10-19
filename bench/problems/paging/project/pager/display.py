"""顯示一頁。"""

from pager.clamp import clamp
from pager.pages import slice_for


def render_page(items, page, size):
    last_page = (len(items) // size) or 1
    page = clamp(page, last_page)
    start, end = slice_for(page, size)
    rows = [str(item) for item in items[start:end]] or ["(no items)"]
    footer = f"Page {page}/{last_page}"
    if page < last_page:
        footer += " (next)"
    rows.append(footer)
    return "\n".join(rows)
