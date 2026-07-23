import asyncio

from quorumqa.config import VERIFIER_MODEL
from quorumqa.qwen_client import QwenClient
from quorumqa.schemas import CallUsage, SolverAnswer, VerifierFinding
from quorumqa.tools.mcp_client import VerifierToolSession

EXTRACT_SYSTEM = (
    "You are the Verifier in a science-exam panel. Read the solver "
    "reasoning below and identify AT MOST 2 checkable claims -- a numeric "
    "derivation, a physical constant, or a unit conversion -- that "
    "materially affect which answer is correct. For each, propose exactly "
    "one tool call to check it against ground truth. Available tools: "
    "lookup_constant(name) for physical/mathematical constants; "
    "safe_calculate(expression) for arithmetic using + - * / ** % // and "
    "constant names as variables. NEVER propose looking up the question or "
    "answer choices themselves -- constants and arithmetic only. If there "
    "is nothing checkable, return an empty list."
)

FINALIZE_SYSTEM = (
    "For each claim below, you are given the tool's grounded result. "
    "Decide whether that result SUPPORTS or CONTRADICTS the claim as "
    "stated. Be strict: only mark supports_claim true if the tool result "
    "genuinely confirms the claim."
)


def _extract_claims(
    client: QwenClient, question: str, solver_answers: list[SolverAnswer], evidence_block: str = ""
) -> tuple[list[dict], CallUsage]:
    transcript = "\n\n".join(f"[{a.lens}] {a.letter}: {a.reasoning}" for a in solver_answers)
    evidence_prefix = f"{evidence_block}\n\n" if evidence_block else ""
    user = (
        f"{evidence_prefix}Question: {question}\n\nSolver reasoning:\n{transcript}\n\n"
        'JSON shape: {"claims": [{"claim": "...", "tool": "lookup_constant|safe_calculate", '
        '"arguments": {...}}]} (arguments for lookup_constant: {"name": "..."}; '
        'for safe_calculate: {"expression": "..."})'
    )
    result = client.chat_json(model=VERIFIER_MODEL, system=EXTRACT_SYSTEM, user=user, role="verifier", thinking=False)
    claims = result.data.get("claims") or result.data.get("items") or []
    return (claims if isinstance(claims, list) else []), result.usage


def _finalize(client: QwenClient, executed: list[dict], evidence_block: str = "") -> tuple[list[VerifierFinding], CallUsage]:
    lines = "\n".join(
        f"- claim: {c['claim']} | tool: {c['tool']}({c['arguments']}) -> {c['tool_result']}" for c in executed
    )
    evidence_prefix = f"{evidence_block}\n\n" if evidence_block else ""
    user = (
        f"{evidence_prefix}{lines}\n\n"
        'JSON shape: {"findings": [{"claim": "...", "supports_claim": true/false, '
        '"explanation": "..."}]} (one entry per claim above, same order)'
    )
    result = client.chat_json(model=VERIFIER_MODEL, system=FINALIZE_SYSTEM, user=user, role="verifier", thinking=False)
    findings_raw = result.data.get("findings", [])
    findings = []
    for c, f in zip(executed, findings_raw if isinstance(findings_raw, list) else []):
        findings.append(
            VerifierFinding(
                claim=c["claim"],
                tool_used=c["tool"],
                tool_query=str(c["arguments"]),
                tool_result=str(c["tool_result"]),
                supports_claim=bool(f.get("supports_claim", False)),
            )
        )
    return findings, result.usage


async def verify(
    client: QwenClient,
    tool_session: VerifierToolSession,
    question: str,
    solver_answers: list[SolverAnswer],
    evidence_block: str = "",
) -> tuple[list[VerifierFinding], list[CallUsage]]:
    """`evidence_block` (docs/recursive-rag-plan.md section 2, R2): passages
    retrieved from a disputed-step query, injected as ADDED grounding
    context for both the claim-extraction and finalize calls -- the
    Verifier's existing MCP tool calls (lookup_constant/safe_calculate) are
    completely unchanged and still fire exactly as before. Default "" means
    every existing caller (the shipped engine, every other lever) behaves
    byte-for-byte identically to before this parameter existed."""
    claims, extract_usage = await asyncio.to_thread(_extract_claims, client, question, solver_answers, evidence_block)
    usages = [extract_usage]

    if not claims:
        return [], usages

    executed = []
    for c in claims[:2]:
        tool = c.get("tool")
        arguments = c.get("arguments", {}) or {}
        if tool not in ("lookup_constant", "safe_calculate") or not isinstance(arguments, dict):
            continue
        tool_result = await tool_session.call(tool, arguments)
        executed.append({"claim": c.get("claim", ""), "tool": tool, "arguments": arguments, "tool_result": tool_result})

    if not executed:
        return [], usages

    findings, finalize_usage = await asyncio.to_thread(_finalize, client, executed, evidence_block)
    usages.append(finalize_usage)
    return findings, usages
