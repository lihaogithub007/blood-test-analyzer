import json

from pdf_processor import extract_json_from_text, fix_json


def test_extract_json_from_markdown_codeblock():
    raw = "hello\n```json\n{\"a\": 1}\n```\nbye"
    assert extract_json_from_text(raw) == "{\"a\": 1}"


def test_extract_json_balanced_object():
    raw = "prefix {\"a\": {\"b\": 2}} suffix"
    assert extract_json_from_text(raw) == "{\"a\": {\"b\": 2}}"


def test_fix_json_removes_trailing_commas():
    fixed = fix_json("{\"a\": 1,}")
    assert json.loads(fixed) == {"a": 1}


def test_fix_json_completes_brackets():
    fixed = fix_json("{\"a\": [1, 2}")
    assert json.loads(fixed) == {"a": [1, 2]}

