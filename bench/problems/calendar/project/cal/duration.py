"""活動佔了幾天（含頭含尾）。"""


def days_booked(event):
    return (event.end - event.start).days + 1
