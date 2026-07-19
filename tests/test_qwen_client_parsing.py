from quorumqa.qwen_client import _extract_json


def test_extracts_bare_json():
    assert _extract_json('{"letter": "B"}') == {"letter": "B"}


def test_extracts_fenced_json():
    text = 'Sure, here you go:\n```json\n{"letter": "B", "confidence": 0.8}\n```\nHope that helps!'
    assert _extract_json(text) == {"letter": "B", "confidence": 0.8}


def test_extracts_json_with_surrounding_prose():
    text = 'The answer is {"letter": "C"} based on my reasoning.'
    assert _extract_json(text) == {"letter": "C"}
