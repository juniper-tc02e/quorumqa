from quorumqa.qwen_client import _extract_json


def test_latex_backslashes_in_reasoning_survive():
    text = r'{"letter": "B", "confidence": 0.8, "reasoning": "\Delta H = -\mu B \text{ so B wins}"}'
    data = _extract_json(text)
    assert data["letter"] == "B"
    assert "Delta" in data["reasoning"]


def test_valid_escapes_untouched():
    text = '{"reasoning": "line1\\nline2 with \\"quote\\""}'
    data = _extract_json(text)
    assert data["reasoning"] == 'line1\nline2 with "quote"'


def test_bare_latex_array_wrapped():
    text = r'[{"claim": "\alpha decay"}]'
    data = _extract_json(text)
    assert data["items"][0]["claim"].endswith("decay")
