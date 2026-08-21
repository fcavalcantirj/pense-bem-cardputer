#!/usr/bin/env python3
"""Host checks for the pure online protocol inside the device app."""

from __future__ import annotations

import ast
from pathlib import Path


APP_PATH = Path(__file__).parents[1] / "device" / "apps" / "pense_bem.py"

PURE_NAMES = {
    "_PROTOCOL",
    "_ONLINE_CLIENT",
    "_PB_QUESTIONS",
    "_PB_PER_SECTION",
    "_SESSION_ID_CAPACITY",
    "_PROMPT_CAPACITY",
    "_OPTION_CAPACITY",
    "_MESSAGE_CAPACITY",
    "_ASSET_ID_CAPACITY",
}

PURE_CLASSES = {"_NetworkError", "_ServerError", "_ProtocolError"}

PURE_FUNCTIONS = {
    "_bounded_text",
    "_bounded_int",
    "_question_from_payload",
    "_start_payload",
    "_answer_payload",
    "_parse_start_response",
    "_parse_answer_response",
    "_post_with_retry",
    "_request_answer",
}


def load_namespace() -> tuple[dict[str, object], ast.Module]:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if names & PURE_NAMES:
                selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name in PURE_CLASSES:
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in PURE_FUNCTIONS:
            selected.append(node)

    namespace: dict[str, object] = {}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(APP_PATH), "exec"),
        namespace,
    )
    missing = (PURE_NAMES | PURE_CLASSES | PURE_FUNCTIONS) - namespace.keys()
    if missing:
        raise AssertionError("online app symbols missing: {}".format(sorted(missing)))
    return namespace, tree


def question(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "number": 1,
        "position": 1,
        "total": 30,
        "attempt": 1,
        "text": "Qual alternativa completa a pergunta?",
        "options": ["Primeira", "Segunda", "Terceira", "Quarta"],
        "text_pages": 1,
        "asset_id": "",
    }
    payload.update(changes)
    return payload


def answer_response(
    session_id: str = "session-123",
    request_id: int = 7,
    **changes: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol": 1,
        "session_id": session_id,
        "request_id": request_id,
        "result": "retry",
        "points_awarded": 0,
        "score": 0,
        "message": "Tente de novo.",
        "complete": False,
        "question": question(attempt=2),
    }
    payload.update(changes)
    return payload


def verify_payloads(ns: dict[str, object]) -> None:
    start_payload = ns["_start_payload"]
    answer_payload = ns["_answer_payload"]

    assert start_payload("011") == {
        "code": "011",
        "client": "atari8",
        "protocol": 1,
    }
    assert answer_payload("session-123", 7, "C") == {
        "session_id": "session-123",
        "request_id": 7,
        "answer": "C",
    }


def verify_bounds(ns: dict[str, object]) -> None:
    parse_start = ns["_parse_start_response"]
    parse_answer = ns["_parse_answer_response"]
    protocol_error = ns["_ProtocolError"]

    start = parse_start(
        {
            "protocol": 1,
            "session_id": "session-123",
            "score": 0,
            "complete": False,
            "question": question(),
        }
    )
    assert start["question"]["options"][3] == "Quarta"

    parsed = parse_answer(answer_response(), "session-123", 7)
    assert parsed["result"] == "retry"
    assert parsed["question"]["attempt"] == 2

    complete = parse_answer(
        answer_response(
            result="complete",
            score=296,
            complete=True,
            question=None,
            message="Rodada completa! Voce fez 296 pontos.",
        ),
        "session-123",
        7,
    )
    assert complete["score"] == 296
    assert complete["question"] is None

    invalid_payloads = [
        answer_response(session_id="other"),
        answer_response(request_id=8),
        answer_response(result="maybe"),
        answer_response(question=question(text="á" * 121)),
        answer_response(question=question(options=["A" * 65, "B", "C", "D"])),
        answer_response(question=question(attempt=4)),
    ]
    for payload in invalid_payloads:
        try:
            parse_answer(payload, "session-123", 7)
        except protocol_error:
            pass
        else:
            raise AssertionError("malformed response was accepted: {!r}".format(payload))


def verify_same_id_retry(ns: dict[str, object]) -> None:
    calls: list[dict[str, object]] = []
    failures = 1

    def fake_post(_url: str, payload: dict[str, object]) -> dict[str, object]:
        nonlocal failures
        calls.append(payload)
        if failures:
            failures -= 1
            raise ns["_NetworkError"]("simulated disconnect")
        return answer_response()

    retries: list[str] = []

    def fake_wait(_kb: object, title: str, _detail: str) -> bool:
        retries.append(title)
        return True

    ns["_post_json"] = fake_post
    ns["_wait_retry"] = fake_wait
    parsed = ns["_request_answer"](
        None,
        "http://127.0.0.1:18080",
        "session-123",
        7,
        "C",
    )
    assert parsed["result"] == "retry"
    assert retries == ["FALHA DE REDE"]
    assert len(calls) == 2
    assert calls[0] is calls[1]
    assert calls[0]["request_id"] == 7
    assert calls[0]["answer"] == "C"


def verify_online_separation(tree: ast.Module) -> None:
    play_online = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_play_online"
    )
    names = {node.id for node in ast.walk(play_online) if isinstance(node, ast.Name)}
    forbidden = {
        "_answer_key_for_book",
        "_questions_for",
        "_points_for_attempt",
        "_normalized_score",
        "_score_band",
    }
    assert not (names & forbidden), "online path consulted offline rules"

    calls = [
        node.func.id
        for node in ast.walk(play_online)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_release_ble_for_online" in calls
    assert calls.index("_release_ble_for_online") < calls.index("_connect_wifi")

    answer_call_line = min(
        node.lineno
        for node in ast.walk(play_online)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_request_answer"
    )
    increments = [
        node
        for node in ast.walk(play_online)
        if isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "request_id"
    ]
    assert len(increments) == 1
    assert increments[0].lineno > answer_call_line

    connect_wifi = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_connect_wifi"
    )
    disconnect_lines = [
        node.lineno
        for node in ast.walk(connect_wifi)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "disconnect"
    ]
    connect_lines = [
        node.lineno
        for node in ast.walk(connect_wifi)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
    ]
    assert disconnect_lines and connect_lines
    assert min(disconnect_lines) < min(connect_lines)


def main() -> None:
    namespace, tree = load_namespace()
    verify_payloads(namespace)
    verify_bounds(namespace)
    verify_same_id_retry(namespace)
    verify_online_separation(tree)
    print("online protocol: ok")
    print("same request_id retry: ok")
    print("online/offline separation: ok")


if __name__ == "__main__":
    main()
