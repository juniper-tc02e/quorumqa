import pytest

from quorumqa.tools.safe_math import SafeEvalError, safe_eval


def test_basic_arithmetic():
    assert safe_eval("2 + 3 * 4") == 14


def test_constants_and_precedence():
    assert safe_eval("2 * pi") == pytest.approx(2 * 3.14159265358979323846)


def test_rejects_function_calls():
    with pytest.raises(SafeEvalError):
        safe_eval("__import__('os').system('echo hi')")


def test_rejects_unknown_name():
    with pytest.raises(SafeEvalError):
        safe_eval("undefined_name + 1")


def test_rejects_attribute_access():
    with pytest.raises(SafeEvalError):
        safe_eval("(1).__class__")


def test_rejects_syntax_errors():
    with pytest.raises(SafeEvalError):
        safe_eval("2 +")
