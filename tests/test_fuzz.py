"""Fuzz / stress: hostile inputs must never crash or hang the harness.

We drive the input layer that actually faces attacker-controlled data — ingest +
the deterministic scanners — across >=500 generated inputs (malformed HCL, random
bytes, huge, ReDoS bait, unicode, deeply nested), asserting: no unhandled
exception, bounded time, and that oversize input is rejected cleanly.
"""
from __future__ import annotations

import random
import time

import pytest

from policy_to_proof.guardrails.guardrails import Guardrails
from policy_to_proof.guardrails.redaction import redact_text
from policy_to_proof.tools import ingest
from policy_to_proof.tools.ingest import InputRejected, ingest_text
from policy_to_proof.tools.registry import run_scanner

CONTROLS = list(Guardrails().controls.values())
N_FUZZ = 520                         # > 500 per the acceptance bar
PER_INPUT_BUDGET_S = 1.0             # ingest + all scanners for one input
RESOURCE_TYPES = ["aws_s3_bucket", "aws_db_instance", "aws_iam_policy",
                  "aws_ebs_volume", "aws_lb_listener", "aws_cloudtrail"]
# exotic but valid unicode (RTL override, combining mark, emoji), as escapes so the
# test source stays pure ASCII
_UNICODE = "‮mixed ٠́ \U0001F4A9 token= end"


def _gen(rng: random.Random) -> str:
    """Produce one hostile/edge-case Terraform-ish input."""
    strat = rng.randint(0, 9)
    if strat == 0:                                   # random bytes -> text
        return bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 4000))
                     ).decode("utf-8", errors="replace")
    if strat == 1:                                   # unbalanced braces
        return 'resource "aws_x" "n" {\n' * rng.randint(1, 40)
    if strat == 2:                                   # truncated resource
        return 'resource "aws_db_instance" "db" {\n  storage_encrypted ='
    if strat == 3:                                   # deeply nested blocks
        return 'resource "aws_x" "n" {\n' + "a {\n" * rng.randint(1, 200)
    if strat == 4:                                   # ReDoS bait near a keyword
        return 'password = "' + "a" * rng.randint(1000, 60000)
    if strat == 5:                                   # many resources
        n = rng.randint(1, 400)
        return "\n".join(f'resource "{rng.choice(RESOURCE_TYPES)}" "n{i}" {{ x = {i} }}'
                         for i in range(n))
    if strat == 6:                                   # unicode / obfuscated
        return 'resource "aws_x" "name" {\n  k = "' + _UNICODE + '"\n}'
    if strat == 7:                                   # plausible-but-mutated
        s = 'resource "aws_db_instance" "db" {\n  storage_encrypted = false\n}\n'
        b = list(s)
        for _ in range(rng.randint(0, 20)):
            b[rng.randrange(len(b))] = rng.choice('{}"= \n#*')
        return "".join(b)
    if strat == 8:                                   # empty / whitespace
        return rng.choice(["", "   ", "\n\n\t\n", "# only a comment"])
    return 'resource "aws_iam_policy" "p" {\n  Action = "*"\n  Resource = "*"\n}'


def test_fuzz_never_crashes_or_hangs():
    rng = random.Random(1337)                        # deterministic corpus
    rejected = 0
    for i in range(N_FUZZ):
        data = _gen(rng)
        t0 = time.perf_counter()
        try:
            corpus, _ = ingest_text(f"fuzz_{i}.tf", data)
        except InputRejected:
            rejected += 1
            continue                                 # clean, expected rejection
        for control in CONTROLS:                     # scanners fail closed internally
            scan = run_scanner(control, corpus)
            assert scan.control_id == control.id
        elapsed = time.perf_counter() - t0
        assert elapsed < PER_INPUT_BUDGET_S, f"input {i} took {elapsed:.3f}s"
    assert rejected < N_FUZZ                          # generator produced a spread


def test_oversize_fuzz_input_is_rejected():
    with pytest.raises(InputRejected):
        ingest_text("huge.tf", "x" * (ingest.MAX_INPUT_BYTES + 1))


def test_redaction_pathological_line_under_budget():
    # A single 300k-char line near a secret keyword must stay fast (line-scan cap).
    pathological = 'aws_secret_access_key = "' + "A" * 300_000 + '"'
    t0 = time.perf_counter()
    redact_text("p.tf", pathological)
    assert (time.perf_counter() - t0) < 0.05          # < 50ms per the acceptance bar
