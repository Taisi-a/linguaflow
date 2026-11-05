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


# ---------- провайдеры ----------

import httpx  # noqa: E402

from app.config import Settings  # noqa: E402
from app.services.extraction import (  # noqa: E402
    OllamaExtractor,
    OpenAICompatibleExtractor,
    get_llm_extractor,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("POST", "http://x"), response=None)

    def json(self):
        return self.payload


def test_ollama_sends_json_format_and_parses_answer(monkeypatch):
    sent = {}

    def fake_post(url, json, timeout, **kw):
        sent.update(url=url, body=json)
        return FakeResponse({"message": {"content": GOOD_JSON}})

    monkeypatch.setattr(httpx, "post", fake_post)
    items = OllamaExtractor("http://localhost:11434/", "qwen2.5:7b").extract("note", "topic")
    assert sent["url"] == "http://localhost:11434/api/chat"
    assert sent["body"]["format"] == "json" and sent["body"]["model"] == "qwen2.5:7b"
    assert len(items) == 2


def test_ollama_not_running_is_unavailable(monkeypatch):
    def refuse(*a, **kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", refuse)
    with pytest.raises(ExtractionUnavailable):
        OllamaExtractor("http://localhost:11434", "m").extract("note")


def test_openai_compatible_parses_choices(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert url == "https://api.example.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer key"
        return FakeResponse({"choices": [{"message": {"content": GOOD_JSON}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    ex = OpenAICompatibleExtractor("https://api.example.com/v1", "key", "model")
    assert len(ex.extract("note")) == 2


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"llm_provider": "ollama"}, OllamaExtractor),
        ({"llm_provider": "gemini", "gemini_api_key": "k"}, GeminiExtractor),
        ({"llm_provider": "gemini"}, type(None)),  # без ключа — запасной режим
        ({"llm_provider": "openai", "openai_api_key": "k", "openai_model": "m"}, OpenAICompatibleExtractor),
        ({"llm_provider": "none"}, type(None)),
    ],
)
def test_provider_selection(env, expected):
    assert isinstance(get_llm_extractor(Settings(_env_file=None, **env)), expected)
