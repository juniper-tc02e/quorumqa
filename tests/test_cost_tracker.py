import pytest

from quorumqa.cost_tracker import price_call


def test_price_call_computes_expected_cost():
    usage = price_call("qwen3.7-max", input_tokens=1_000_000, output_tokens=1_000_000, role="judge")
    assert usage.cost_usd == pytest.approx(2.50 + 7.50)


def test_price_call_unknown_model_raises():
    with pytest.raises(KeyError):
        price_call("not-a-real-model", input_tokens=100, output_tokens=100, role="solver")
