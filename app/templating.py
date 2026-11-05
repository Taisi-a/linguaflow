from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.services.srs import plural
from app.timeutil import local_date

MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
MONTHS_FULL = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def ru_date(value: date | datetime, full: bool = False) -> str:
    if isinstance(value, datetime):
        value = local_date(value)
    months = MONTHS_FULL if full else MONTHS_SHORT
    return f"{value.day} {months[value.month - 1]}"


def ru_plural(n: int, one: str, few: str, many: str) -> str:
    return f"{n} {plural(n, one, few, many)}"


templates.env.filters["ru_date"] = ru_date
templates.env.globals["ru_plural"] = ru_plural
templates.env.globals["plural"] = plural
