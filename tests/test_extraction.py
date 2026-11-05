import json

import pytest

from app.services.extraction import (
    ExtractionError,
    ExtractionUnavailable,
    GeminiExtractor,
    LineExtractor,
    parse_llm_response,
)

GOOD_JSON = json.dumps(
    {
        "items": [
            {
                "text": "come up with",
                "translation": "придумать",
                "kind": "word",
                "transcription": "/kʌm ʌp wɪð/",
            },
            {"text": "look forward to + -ing", "translation": "ждать с нетерпением", "kind": "grammar"},
        ]
    },
    ensure_ascii=False,
)


def test_parse_valid_response():
    items = parse_llm_response(GOOD_JSON)
    assert [i.text for i in items] == ["come up with", "look forward to + -ing"]
    assert items[1].kind == "rule"  # «grammar» нормализуется в «rule»


def test_parse_strips_markdown_fence():
    items = parse_llm_response(f"```json\n{GOOD_JSON}\n```")
    assert len(items) == 2


def test_parse_accepts_bare_list():
    items = parse_llm_response('[{"text": "give up", "translation": "сдаться"}]')
    assert items[0].text == "give up"


def test_parse_removes_duplicates_case_insensitive():
    raw = '[{"text": "Give up", "translation": "a"}, {"text": "give up.", "translation": "b"}]'
    assert len(parse_llm_response(raw)) == 1


@pytest.mark.parametrize("raw", ["не json", '{"words": []}', '[{"translation": "без слова"}]'])
def test_parse_rejects_bad_responses(raw):
    with pytest.raises(ExtractionError):
        parse_llm_response(raw)


def test_gemini_retries_once_on_bad_answer(monkeypatch):
    answers = iter(["мусор", GOOD_JSON])
    extractor = GeminiExtractor(api_key="x", model="m", retries=1)
    monkeypatch.setattr(extractor, "_call", lambda prompt: next(answers))
    assert len(extractor.extract("note")) == 2


def test_gemini_gives_up_after_retries(monkeypatch):
    extractor = GeminiExtractor(api_key="x", model="m", retries=1)
    monkeypatch.setattr(extractor, "_call", lambda prompt: "мусор")
    with pytest.raises(ExtractionError):
        extractor.extract("note")


def test_gemini_network_error_is_unavailable(monkeypatch):
    extractor = GeminiExtractor(api_key="x", model="m")

    def boom(prompt):
        raise ExtractionUnavailable("no network")

    monkeypatch.setattr(extractor, "_call", boom)
    with pytest.raises(ExtractionUnavailable):
        extractor.extract("note")


def test_line_extractor_parses_notebook_lines():
    note = """come up with — придумать
    give up - бросить, сдаться
    look forward to + -ing — ждать с нетерпением
    не путать come up with и come across
    Д/З: 5 предложений"""
    items = LineExtractor().extract(note)
    assert [(i.text, i.kind) for i in items] == [
        ("come up with", "word"),
        ("give up", "word"),
        ("look forward to + -ing", "rule"),
    ]
    assert items[1].translation == "бросить, сдаться"


def test_line_extractor_ignores_lines_without_russian():
    assert LineExtractor().extract("Present Perfect - have done") == []
