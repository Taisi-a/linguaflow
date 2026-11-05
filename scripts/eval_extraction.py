"""Оценка качества извлечения слов из заметок.

Датасет — JSON-список заметок с вручную размеченными ожидаемыми словами:
    [{"topic": "...", "text": "...", "expected": ["come up with", "give up"]}]

Скрипт прогоняет каждый экстрактор (LLM и запасной разбор строк) и считает
precision (сколько найденного — правда), recall (сколько из нужного найдено) и F1.

Запуск:
    python -m scripts.eval_extraction eval/dataset.json
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.services.extraction import (
    ExtractionError,
    ExtractionUnavailable,
    LineExtractor,
    get_llm_extractor,
    normalize,
)


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    errors: int = 0
    seconds: float = 0.0
    misses: list = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def evaluate(extractor, dataset: list[dict]) -> Score:
    score = Score()
    for i, sample in enumerate(dataset):
        expected = {normalize(w) for w in sample["expected"]}
        started = time.perf_counter()
        try:
            found = {
                normalize(item.text) for item in extractor.extract(sample["text"], sample.get("topic", ""))
            }
        except (ExtractionUnavailable, ExtractionError) as e:
            score.errors += 1
            score.fn += len(expected)
            score.misses.append({"note": i, "error": str(e)[:200]})
            continue
        finally:
            score.seconds += time.perf_counter() - started
        score.tp += len(found & expected)
        score.fp += len(found - expected)
        score.fn += len(expected - found)
        if found != expected:
            score.misses.append(
                {"note": i, "missed": sorted(expected - found), "extra": sorted(found - expected)}
            )
    return score


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--out", type=Path, default=Path("eval/results/latest.json"))
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    extractors = [LineExtractor()]
    llm = get_llm_extractor()
    if llm:
        extractors.insert(0, llm)
    else:
        print(f"LLM_PROVIDER={get_settings().llm_provider} не настроен — оценивается только разбор строк\n")

    expected_total = sum(len(s["expected"]) for s in dataset)
    print(f"Заметок: {len(dataset)}, размеченных слов: {expected_total}\n")
    print(f"{'Экстрактор':<16}{'Precision':>11}{'Recall':>9}{'F1':>7}{'Ошибок':>9}{'Сек/заметку':>13}")

    report = {}
    for ex in extractors:
        s = evaluate(ex, dataset)
        name = getattr(ex, "model", "") or ex.name
        print(
            f"{name:<12}{s.precision:>11.0%}{s.recall:>9.0%}{s.f1:>7.0%}{s.errors:>9}"
            f"{s.seconds / max(len(dataset), 1):>13.2f}"
        )
        report[name] = {
            "precision": round(s.precision, 3),
            "recall": round(s.recall, 3),
            "f1": round(s.f1, 3),
            "errors": s.errors,
            "misses": s.misses,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nРазбор ошибок по заметкам: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
