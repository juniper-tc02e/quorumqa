from quorumqa.config import PRICING_USD_PER_MTOK
from quorumqa.schemas import CallUsage


def price_call(model: str, input_tokens: int, output_tokens: int, role: str) -> CallUsage:
    rates = PRICING_USD_PER_MTOK.get(model)
    if rates is None:
        raise KeyError(f"No pricing entry for model {model!r} -- add it to PRICING_USD_PER_MTOK")
    cost = (input_tokens / 1_000_000) * rates["input"] + (output_tokens / 1_000_000) * rates["output"]
    return CallUsage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 8),
        role=role,
    )
