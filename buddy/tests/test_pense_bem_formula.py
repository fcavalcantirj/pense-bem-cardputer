#!/usr/bin/env python3
"""Verify the formula inside the single-file device app on CPython."""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path


APP_PATH = Path(__file__).parents[1] / "device" / "apps" / "pense_bem.py"

PURE_NAMES = {
    "_PB_BOOKS",
    "_PB_QUESTIONS",
    "_PB_PER_SECTION",
    "_PB_PAGE",
    "_PB_SECTIONS",
    "_PB_SHIFT_Q",
    "_PB_SEED",
    "_PB_OFFSETS",
    "_PB_LCG_DEFAULT",
    "_PB_LCG_MULT",
    "_PB_LCG_ADD",
    "_PB_U64_MASK",
    "_POINTS",
    "_JUDGE_HOLD_MS",
    "_REVEAL_HOLD_MS",
    "_SPEAKER_VOLUME",
    "_SFX_RIGHT",
    "_SFX_WRONG",
    "_SFX_REVEAL",
    "_END_SONGS",
}

PURE_FUNCTIONS = {
    "_answer_key_for_book",
    "_questions_for",
    "_points_for_attempt",
    "_normalized_score",
    "_score_band",
    "_parse_code",
}


def load_pure_app_namespace() -> dict[str, object]:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & PURE_NAMES:
                selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in PURE_FUNCTIONS:
            selected.append(node)

    namespace: dict[str, object] = {}
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(APP_PATH), "exec"), namespace)
    missing = (PURE_NAMES | PURE_FUNCTIONS) - namespace.keys()
    if missing:
        raise AssertionError("pure app symbols missing: {}".format(sorted(missing)))
    return namespace


def verify_rules(ns: dict[str, object]) -> None:
    answer_key = ns["_answer_key_for_book"]
    questions_for = ns["_questions_for"]
    points = ns["_points_for_attempt"]
    normalized = ns["_normalized_score"]
    band = ns["_score_band"]
    parse_code = ns["_parse_code"]

    assert len(ns["_PB_SEED"]) == 150
    assert len(ns["_PB_OFFSETS"]) == 588
    assert answer_key(0) is None
    assert answer_key(100) is None
    assert len(answer_key(99)) == 150
    assert all(0 <= answer <= 3 for answer in answer_key(99))
    assert parse_code("011") == (1, 1)
    assert parse_code("171") == (17, 1)
    assert parse_code("181") == (18, 1)
    assert parse_code("191") == (19, 1)
    assert parse_code("000") is None
    assert parse_code("017") is None
    assert ns["_JUDGE_HOLD_MS"] == 1200
    assert ns["_REVEAL_HOLD_MS"] == 2600
    assert ns["_SPEAKER_VOLUME"] == 100
    assert ns["_SFX_RIGHT"] == ((1047, 90), (1568, 160))
    assert ns["_SFX_WRONG"] == ((520, 280),)
    assert ns["_SFX_REVEAL"] == ((520, 110), (0, 60), (392, 220))
    assert len(ns["_END_SONGS"]) == 4
    assert ns["_END_SONGS"][0][-1] == (1047, 320)
    assert questions_for(1, 1) == list(range(1, 31))
    assert questions_for(5, 1) == list(range(121, 151))
    for seed in range(1, 1001):
        review = questions_for(6, seed * 2654435761)
        assert len(review) == 30
        assert all(
            (question - 1) // 5 == page for page, question in enumerate(review)
        )
    assert [points(i) for i in range(1, 5)] == [10, 6, 4, 0]
    assert normalized(300, 30) == 100
    assert normalized(0, 30) == 0
    assert [band(score) for score in (76, 51, 26, 25)] == [0, 1, 2, 3]


def verify_reference_table(ns: dict[str, object], reference: Path) -> tuple[int, int]:
    """Prove full-table transcription; this generated fixture is circular."""
    answer_key = ns["_answer_key_for_book"]
    expected = "".join(reference.read_text(encoding="ascii").split())
    cells = 99 * 150
    # The upstream generator emitted two extra trailing characters. Its own
    # readers, and the ESP32 parity suite, deliberately consume only 99x150.
    if len(expected) != cells + 2:
        raise AssertionError("unexpected reference-table length: {}".format(len(expected)))

    passed = 0
    for book in range(1, 100):
        key = answer_key(book)
        start = (book - 1) * 150
        for index, answer in enumerate(key):
            if chr(97 + answer) != expected[start + index]:
                raise AssertionError(
                    "reference mismatch: book {} question {}".format(book, index + 1)
                )
            passed += 1
    return passed, cells


def verify_fixture(
    ns: dict[str, object], fixture: Path
) -> tuple[int, int, int, int, int]:
    answer_key = ns["_answer_key_for_book"]
    keys: dict[int, bytearray] = {}
    passed = 0
    total = 0
    distinct: set[tuple[int, int, str]] = set()
    failures: list[str] = []

    physical_lines = fixture.read_text(encoding="utf-8").splitlines()
    if not physical_lines or physical_lines[0] != "book\tquestion\tanswer":
        raise AssertionError("unexpected fixture header")
    separators = sum(not line.strip() for line in physical_lines[1:])
    fixture_lines = len(physical_lines) - 1

    with fixture.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            code = row["book"].strip()
            book = int(code[:2])
            question = int(row["question"])
            expected = row["answer"].strip().upper()
            distinct.add((book, question, expected))
            if book not in keys:
                keys[book] = answer_key(book)
            actual = chr(65 + keys[book][question - 1])
            total += 1
            if actual == expected:
                passed += 1
            elif len(failures) < 10:
                failures.append(
                    "{} question {}: expected {}, got {}".format(
                        code, question, expected, actual
                    )
                )

    if failures:
        raise AssertionError("\n".join(failures))
    return passed, total, separators, fixture_lines, len(distinct)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: test_pense_bem_formula.py REAL_BOOKS_TSV", file=sys.stderr)
        return 2
    fixture = Path(sys.argv[1])
    reference = fixture.with_name("reference-table.txt")
    ns = load_pure_app_namespace()
    verify_rules(ns)
    passed, total, separators, fixture_lines, distinct = verify_fixture(ns, fixture)
    table_passed, table_total = verify_reference_table(ns, reference)
    verified_lines = passed + separators
    print("{}/{}".format(verified_lines, fixture_lines))
    print(
        "answers: {}/{} rows, {} distinct; separators: {}".format(
            passed, total, distinct, separators
        )
    )
    print(
        "reference port: {}/{} (circular; transcription check only)".format(
            table_passed, table_total
        )
    )
    print("offline rules: ok")
    complete = (
        passed == total == 982
        and distinct == 925
        and separators == 38
        and verified_lines == fixture_lines == 1020
        and table_passed == table_total == 14850
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
