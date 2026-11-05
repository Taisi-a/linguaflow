"""Извлечение слов и правил из заметки с занятия.

Основной путь — LLM (Gemini): модель получает текст заметки и возвращает JSON,
который проверяется Pydantic-схемой. Если ключа нет или сеть недоступна, работает
запасной разборщик строк вида «come up with — придумать».
"""

import json
import re
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import get_settings


class ExtractedItem(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    translation: str = Field(default="", max_length=300)
    kind: str = "word"  # word | rule
    transcription: str = ""
    example: str = ""
    tutor_note: str = ""

    @field_validator("text", "translation", "transcription", "example", "tutor_note", mode="before")
    @classmethod
    def strip(cls, v):
        return (v or "").strip() if isinstance(v, str) or v is None else v

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, v):
        return "rule" if str(v).lower().strip() in {"rule", "grammar", "правило"} else "word"


class ExtractionResult(BaseModel):
    items: list[ExtractedItem]


class ExtractionUnavailable(Exception):
    """LLM недоступна: нет ключа, нет сети, ошибка API."""


class ExtractionError(Exception):
    """LLM ответила, но ответ не удалось разобрать."""


class Extractor(Protocol):
    name: str

    def extract(self, text: str, topic: str = "") -> list[ExtractedItem]: ...


PROMPT = """Ты помогаешь студентке, которая учит английский с репетитором.
Ниже её заметка с занятия: смесь английского и русского, как в тетради.

Найди в заметке:
- английские слова и устойчивые выражения (kind = "word");
- грамматические правила и конструкции (kind = "rule"), например «look forward to + -ing».

Для каждого элемента верни:
- text — слово, выражение или правило на английском, как в заметке;
- translation — перевод или краткое объяснение на русском (если в заметке есть перевод, возьми его);
- transcription — транскрипция IPA в слешах для слов, для правил пустая строка;
- example — одно короткое естественное предложение-пример на английском;
- tutor_note — пометка из заметки к этому элементу (например «не путать с come across»),
  иначе пустая строка.

Не добавляй то, чего в заметке нет. Домашнее задание и служебные пометки не являются словами.
Ответ — только JSON вида {{"items": [...]}} без пояснений.

Тема занятия: {topic}
Заметка:
\"\"\"
{text}
\"\"\"
"""

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_llm_response(raw: str) -> list[ExtractedItem]:
    """Разбирает ответ модели. Терпит обёртку ```json и голый список вместо объекта."""
    cleaned = _FENCE.sub("", raw.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Ответ модели не JSON: {e}") from e
    if isinstance(data, list):
        data = {"items": data}
    try:
        result = ExtractionResult.model_validate(data)
    except ValidationError as e:
        raise ExtractionError(f"Ответ модели не прошёл проверку схемы: {e}") from e
    return deduplicate(result.items)


def deduplicate(items: list[ExtractedItem]) -> list[ExtractedItem]:
    seen: set[str] = set()
    out = []
    for item in items:
        key = normalize(item.text)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip(" .,;:!?\"'«»"))


class GeminiExtractor:
    name = "llm"

    def __init__(self, api_key: str, model: str, retries: int = 1):
        self.api_key = api_key
        self.model = model
        self.retries = retries

    def _call(self, prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
            )
        except Exception as e:  # сеть, квота, неверный ключ
            raise ExtractionUnavailable(str(e)) from e
        return response.text or ""

    def extract(self, text: str, topic: str = "") -> list[ExtractedItem]:
        prompt = PROMPT.format(text=text, topic=topic or "не указана")
        last_error: ExtractionError | None = None
        for _ in range(self.retries + 1):
            try:
                return parse_llm_response(self._call(prompt))
            except ExtractionError as e:
                last_error = e
        assert last_error is not None
        raise last_error


# «come up with — придумать», «give up - бросить», «turn down: отказаться»
# Дефис считается разделителем только с пробелами вокруг, чтобы не резать «+ -ing».
_LINE = re.compile(r"^\s*[-•*]?\s*([A-Za-z][A-Za-z '’\-+().]*?)\s*(?:[—–:=]|(?<=\s)-(?=\s))\s*(.+?)\s*$")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")


class LineExtractor:
    """Запасной вариант без ИИ: разбирает строки «английский — перевод»."""

    name = "lines"

    def extract(self, text: str, topic: str = "") -> list[ExtractedItem]:
        items = []
        for line in text.splitlines():
            m = _LINE.match(line)
            if not m:
                continue
            eng, rus = m.group(1).strip(), m.group(2).strip()
            if not _CYRILLIC.search(rus):
                continue
            kind = "rule" if "+" in eng or "-ing" in eng else "word"
            items.append(ExtractedItem(text=eng, translation=rus, kind=kind))
        return deduplicate(items)


def get_extractor() -> Extractor:
    settings = get_settings()
    if settings.gemini_api_key:
        return GeminiExtractor(settings.gemini_api_key, settings.gemini_model)
    return LineExtractor()
