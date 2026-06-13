"""PILLAR 2 — TOOLS: material ingest. Any config -> normalized ScanCorpus.

This is the tool that lets the agent "read data" from the outside world. Today:
a lightweight Terraform/HCL parser. The corpus shape is format-agnostic, so a
Kubernetes/YAML parser could feed the same ScanCorpus tomorrow by implementing
`parse_*` and registering it in `ingest_path`.

Two guardrails are applied at this boundary (Pillar 3):
  - read-only target: we only ever open files for reading; the harness never
    writes to the scanned target.
  - input redaction: detected secrets are masked by the redaction guardrail
    BEFORE the corpus is built, so nothing unredacted reaches the agent or logs.
"""
from __future__ import annotations

import os
import re
from ..types import ScanCorpus
from ..guardrails.redaction import redact_text, SecretHit

# Matches:  resource "aws_s3_bucket" "data" {
_RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
_BLOCK_RE = re.compile(r'^\s*([a-z0-9_]+)\s*\{')          # nested block open
_ATTR_RE = re.compile(r'^\s*([a-zA-Z0-9_]+)\s*=\s*(.+?)\s*$')


def _read_files(root: str) -> dict[str, str]:
    files: dict[str, str] = {}
    if os.path.isfile(root):
        with open(root, "r", encoding="utf-8", errors="replace") as fh:
            files[os.path.basename(root)] = fh.read()
        return files
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if name.endswith((".tf", ".tf.json", ".hcl")):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root)
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    files[rel] = fh.read()
    return files


def _parse_terraform(path: str, text: str) -> list[dict]:
    """Best-effort brace-aware HCL resource extraction.

    Each resource record captures: type, name, file, start_line, raw body, and a
    flat attribute map (top-level + dotted nested keys) for deterministic scanning.
    """
    resources: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _RESOURCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        rtype, rname = m.group(1), m.group(2)
        start_line = i + 1
        depth = lines[i].count("{") - lines[i].count("}")
        body_lines = [(start_line, lines[i])]
        i += 1
        while i < len(lines) and depth > 0:
            depth += lines[i].count("{") - lines[i].count("}")
            body_lines.append((i + 1, lines[i]))
            i += 1
        attrs = _flatten_attrs(body_lines)
        resources.append({
            "type": rtype,
            "name": rname,
            "file": path,
            "start_line": start_line,
            "attrs": attrs,                         # {key: (value, line)}
            "raw": "\n".join(l for _, l in body_lines),
        })
    return resources


def _flatten_attrs(body_lines: list[tuple[int, str]]) -> dict[str, tuple[str, int]]:
    """Flatten attributes into dotted keys, e.g. server_side_encryption.sse_algorithm."""
    attrs: dict[str, tuple[str, int]] = {}
    prefix: list[str] = []
    for lineno, raw in body_lines:
        block = _BLOCK_RE.match(raw)
        attr = _ATTR_RE.match(raw)
        if attr:
            key = ".".join(prefix + [attr.group(1)])
            attrs[key] = (attr.group(2).strip().strip('"'), lineno)
        elif block and "=" not in raw:
            prefix.append(block.group(1))
        if "}" in raw and prefix:
            # close as many blocks as braces closed on this line
            for _ in range(raw.count("}")):
                if prefix:
                    prefix.pop()
    return attrs


def _build_config_map(resources: list[dict]) -> dict:
    cfg: dict = {}
    for r in resources:
        key = f"{r['type']}.{r['name']}"
        cfg[key] = {k: v[0] for k, v in r["attrs"].items()}
    return cfg


def ingest_path(root: str) -> tuple[ScanCorpus, list[SecretHit]]:
    """Ingest a Terraform file or directory into a redacted ScanCorpus.

    Returns the corpus and the raw secret hits (so the harness can alarm before
    the corpus — already redacted — flows to the agent).
    """
    raw_files = _read_files(root)
    redacted_files: dict[str, str] = {}
    all_hits: list[SecretHit] = []
    resources: list[dict] = []

    for path, text in raw_files.items():
        red_text, hits = redact_text(path, text)
        redacted_files[path] = red_text
        all_hits.extend(hits)
        resources.extend(_parse_terraform(path, red_text))

    corpus = ScanCorpus(
        source_root=root,
        files=redacted_files,
        resources=resources,
        config_map=_build_config_map(resources),
        redactions=[{"rule": h.rule, "file": h.file, "line": h.line} for h in all_hits],
    )
    return corpus, all_hits
