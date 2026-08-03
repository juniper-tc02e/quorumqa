"""`--timeout` must reach the client, and its default must not move.

WHY. benchmark/lever_experiments.py constructed `QwenClient()` with no timeout
at three sites, so every call used the client's 300-second default. That
default is not harmless: TB-1 arm C lost ~5 items per seed to
`ReadTimeout: read timeout=300` on long-generation items and came within one
item of tripping the |S| >= 81 drop kill on a 1.33M-token run. Those drops are
504/timeout-correlated and therefore NOT missing at random, so they bias every
affected result toward items with shorter answers.

The `timeout` parameter already existed on QwenClient; it simply was not wired
through. Two properties are pinned here:

  the flag REACHES the client -- a flag that parses but is dropped on the way
  is worse than none, because it looks like it worked;

  the default stays 300 -- every committed run was measured at 300, and its
  drop rate is part of the published record. Changing the default would make
  those runs unreproducible.

Offline: no API calls (the client is replaced with a recorder).
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

import benchmark.lever_experiments as lev


def test_the_default_is_still_300_seconds():
    """Every committed run was measured at this value. Moving it silently
    invalidates the published drop rates."""
    assert lev.DEFAULT_CLIENT_TIMEOUT == 300.0

    from quorumqa.qwen_client import QwenClient
    client_default = inspect.signature(QwenClient.__init__).parameters["timeout"].default
    assert client_default == 300, (
        "the runner default and the client default must agree, or `--timeout` "
        "changes behaviour even when the user does not pass it"
    )


@pytest.mark.parametrize("entry", ["main_live", "main_baseline", "main_gate_replay"])
def test_every_entry_point_accepts_a_timeout(entry):
    params = inspect.signature(getattr(lev, entry)).parameters
    assert "timeout" in params, f"{entry} cannot be given a timeout"
    assert params["timeout"].default == lev.DEFAULT_CLIENT_TIMEOUT


def test_no_client_is_constructed_without_a_timeout():
    """The defect itself: three bare `QwenClient()` calls. Guarding the source
    catches a fourth being added later, which a behavioural test on the
    existing three would miss."""
    src = open(lev.__file__, encoding="utf-8").read()
    assert "QwenClient()" not in src, (
        "a bare QwenClient() ignores --timeout and silently uses 300s"
    )
    assert src.count("QwenClient(timeout=timeout)") == 3


def test_the_flag_actually_reaches_the_client(monkeypatch, tmp_path):
    """A flag that parses but is dropped en route is worse than no flag: it
    looks like it worked."""
    seen: list[float] = []

    class Recorder:
        def __init__(self, *a, timeout=None, **kw):
            seen.append(timeout)

    monkeypatch.setattr(lev, "QwenClient", Recorder)
    frozen = lev.RESULTS_DIR / "full_run2.jsonl"
    if not frozen.exists():
        pytest.skip("frozen run is gitignored; present only where the run happened")

    try:
        asyncio.run(lev.main_gate_replay(frozen, tmp_path / "out.jsonl", timeout=900.0))
    except Exception:
        pass  # the replay will fail on the recorder; construction is the assertion

    assert seen, "no client was constructed"
    assert seen[0] == 900.0, f"--timeout did not reach the client (got {seen[0]})"


def test_the_cli_exposes_the_flag():
    src = open(lev.__file__, encoding="utf-8").read()
    assert '"--timeout"' in src
    assert "args.timeout" in src
    # all three dispatch branches must forward it
    assert src.count("args.timeout") == 3, (
        "every dispatch branch must forward --timeout, or the flag works for "
        "some levers and is silently ignored for others"
    )
