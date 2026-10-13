"""The strict subset: an accepted corpus with its values, a refused corpus with its reason."""

import pytest

from claude_session.yamlsubset import YAMLSubsetError, dump, load

ACCEPTED = [
    ("", {}),
    ("# only a comment\n", {}),
    ("a: 1\nb: -2\nc: 0.8\n", {"a": 1, "b": -2, "c": 0.8}),
    ("a: null\nb: ~\nc:\n", {"a": None, "b": None, "c": None}),
    ("a: true\nb: false\n", {"a": True, "b": False}),
    ("a: bare words here\n", {"a": "bare words here"}),
    ("a: \"x # not a comment\"\n", {"a": "x # not a comment"}),
    ("a: 'it''s'\n", {"a": "it's"}),
    ("a: x  # trailing\n", {"a": "x"}),
    ("a: history/sittings\n", {"a": "history/sittings"}),
    ("a:\n  b:\n    c: 1\n  d: 2\ne: 3\n", {"a": {"b": {"c": 1}, "d": 2}, "e": 3}),
    ("a:\n  - x\n  - 2\n", {"a": ["x", 2]}),
    ("a:\n- x\n- y\nb: 1\n", {"a": ["x", "y"], "b": 1}),
    ("a: [Read, Glob, \"x, y\"]\n", {"a": ["Read", "Glob", "x, y"]}),
    ("a: []\nb: {}\n", {"a": [], "b": {}}),
    ("c: {context: 180000, turns: 400}\n", {"c": {"context": 180000, "turns": 400}}),
    ("agent-relay: {enabled: auto}\n", {"agent-relay": {"enabled": "auto"}}),
    ("i:\n  - {path: /a, sha256: null}\n", {"i": [{"path": "/a", "sha256": None}]}),
]

REFUSED = [
    ("a: &x 1\n", "anchor"),
    ("a: *x\n", "alias"),
    ("a: !tag x\n", "tag"),
    ("a: |\n  text\n", "multi-line scalar"),
    ("a: >\n  text\n", "multi-line scalar"),
    ("a: one\n  two\n", "multi-line scalar"),
    ("a:\n  - - x\n", "nested list"),
    ("a:\n  - [x]\n", "nested list"),
    ("a: [[x]]\n", "nested flow collection"),
    ("a: {b: {c: 1}}\n", "nested flow collection"),
    ("a:\n\tb: 1\n", "tab"),
    ("a: 1\na: 2\n", "duplicate key"),
    ("a: {b: 1, b: 2}\n", "duplicate key"),
    ("---\na: 1\n", "document marker"),
    ("- a\n", "top level must be a mapping"),
    ("a:\n  - k: v\n", "list of block mappings"),
    ("a: \"open\n", "unterminated quote"),
    ("  a: 1\n", "bad indentation"),
    ("a:\n    b: 1\n  c: 2\n", "bad indentation"),
    ("a:\n  - x\n  b: 1\n", "bad indentation"),
    ("just text\n", "not a `key: value` line"),
]


@pytest.mark.parametrize("text,want", ACCEPTED)
def test_accepted(text, want):
    assert load(text) == want


@pytest.mark.parametrize("text,reason", REFUSED)
def test_refused(text, reason):
    with pytest.raises(YAMLSubsetError) as e:
        load(text)
    assert reason in e.value.reason
    assert e.value.line >= 1


def test_error_names_the_line():
    with pytest.raises(YAMLSubsetError) as e:
        load("a: 1\nb: 2\nb: 3\n")
    assert e.value.line == 3


def test_dump_round_trips_and_keeps_order():
    obj = {"z": 1, "a": {"y": [1, "two"], "x": None, "e": {}},
           "s": "needs: quoting", "t": "true", "i": [{"path": "/p", "sha256": None}]}
    text = dump(obj)
    assert load(text) == obj
    assert list(load(text)) == ["z", "a", "s", "t", "i"]
    assert dump(obj) == text


def test_dump_refuses_nested_lists():
    with pytest.raises(ValueError):
        dump({"a": [[1]]})
