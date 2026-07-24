"""Quota token-audit (reasoning-supercharge-plan §2 item 0; research doc F-rung
prerequisite): size the Token Plan's 1-week quota in TOKENS by summing every
logged call from the runs that exhausted it (window: 2026-07-21 03:32 UTC →
exhaustion on 2026-07-24 ~03:52), then price the planned week-1 runs against it.

HONESTY BOUNDS, stated up front:
- This is a LOWER bound on true consumption. Dropped items (ReadTimeout/429)
  burned tokens without leaving a row; the invalidated AIME run logged only
  the ~26-28 survivors of 60 attempted x up-to-4 retries; JSON-retry attempts
  are summed into usage only when the item eventually landed.
- Thinking tokens bill as output tokens (included in output_tokens).
- cost_usd is always 0.0 on this endpoint; tokens are the only meter.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
WINDOW_START = datetime(2026, 7, 21, 3, 32, tzinfo=timezone.utc)


def iter_usage(obj):
    """Yield every {input_tokens, output_tokens} usage dict nested anywhere."""
    if isinstance(obj, dict):
        if "input_tokens" in obj and "output_tokens" in obj:
            yield obj
        else:
            for v in obj.values():
                yield from iter_usage(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_usage(v)


def main():
    rows = []
    for p in sorted(RESULTS.glob("*.jsonl")):
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mtime < WINDOW_START:
            continue
        tin = tout = n_items = 0
        try:
            with p.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    n_items += 1
                    for u in iter_usage(r):
                        tin += int(u.get("input_tokens") or 0)
                        tout += int(u.get("output_tokens") or 0)
        except OSError:
            continue
        if tin or tout:
            rows.append((p.name, mtime, n_items, tin, tout))

    rows.sort(key=lambda r: r[1])
    total_in = sum(r[3] for r in rows)
    total_out = sum(r[4] for r in rows)
    total = total_in + total_out

    lines = []
    lines.append("# Token Plan weekly-quota audit (window 2026-07-21 03:32 UTC -> exhausted 2026-07-24 ~03:52)\n")
    lines.append("| file (in-window mtime) | items | input tok | output tok | total |")
    lines.append("|---|---|---|---|---|")
    for name, mtime, n, tin, tout in rows:
        lines.append(f"| {name} ({mtime:%m-%d %H:%M}) | {n} | {tin:,} | {tout:,} | {tin+tout:,} |")
    lines.append(f"| **TOTAL (logged lower bound)** | | **{total_in:,}** | **{total_out:,}** | **{total:,}** |")

    # Per-planned-run pricing from measured per-question costs
    lines.append("\n## What the measured runs cost per question (for pricing week-1)\n")
    per_q = {}
    for name, _, n, tin, tout in rows:
        if n:
            per_q[name] = (tin + tout) / n
    for name, v in sorted(per_q.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {name}: ~{v:,.0f} tok/row")

    out = RESULTS / "quota_token_audit.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"TOTAL logged in window: {total:,} tokens ({total_in:,} in / {total_out:,} out) across {len(rows)} files")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
