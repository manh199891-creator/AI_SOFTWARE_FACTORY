"""Deterministic convergence controls for the dual-agent review pipeline.

The module deliberately has no dependency on the Codex runtime.  It owns the
machine-readable state, deterministic lint/contract checks, semantic ledgers,
and convergence decisions that must happen before or after an expensive review.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


STATUS_VERSION = 2
ALLOWED_STATUSES = {
    "NOT_STARTED", "RUNNING", "NEEDS_FIX", "READY_FOR_REVIEW", "REVIEWING", "PASS",
    "INFRA_FAIL", "STALE", "NO_PROGRESS", "BLOCKED_HANDOFF", "STATE_DESYNC",
    "PHASE_REVIEW_CEILING", "BATCH_REVIEW_CEILING", "BLOCKED_SCOPE", "BLOCKED_VERIFY",
}
TERMINAL_STATUSES = {
    "PASS", "INFRA_FAIL", "STALE", "NO_PROGRESS", "BLOCKED_HANDOFF", "STATE_DESYNC",
    "PHASE_REVIEW_CEILING", "BATCH_REVIEW_CEILING", "BLOCKED_SCOPE", "BLOCKED_VERIFY",
}
TRANSITIONS = {
    "NOT_STARTED": {"RUNNING", "NEEDS_FIX", "PASS", "STATE_DESYNC", "INFRA_FAIL", "STALE", "NO_PROGRESS", "BLOCKED_HANDOFF", "BLOCKED_SCOPE", "BLOCKED_VERIFY"},
    "RUNNING": {"NEEDS_FIX", "READY_FOR_REVIEW", "REVIEWING", "PASS", "INFRA_FAIL", "STALE", "NO_PROGRESS", "BLOCKED_HANDOFF", "STATE_DESYNC", "BLOCKED_SCOPE", "BLOCKED_VERIFY"},
    "NEEDS_FIX": {"READY_FOR_REVIEW", "RUNNING", "BLOCKED_HANDOFF", "NO_PROGRESS", "STATE_DESYNC", "INFRA_FAIL", "BATCH_REVIEW_CEILING", "PHASE_REVIEW_CEILING"},
    "READY_FOR_REVIEW": {"REVIEWING", "NEEDS_FIX", "STATE_DESYNC", "STALE", "INFRA_FAIL"},
    "REVIEWING": {"RUNNING", "PASS", "NEEDS_FIX", "INFRA_FAIL", "STALE", "STATE_DESYNC", "NO_PROGRESS", "BLOCKED_HANDOFF", "BATCH_REVIEW_CEILING", "PHASE_REVIEW_CEILING"},
    "STALE": {"RUNNING", "READY_FOR_REVIEW", "STATE_DESYNC", "INFRA_FAIL"},
    "STATE_DESYNC": {"RUNNING", "READY_FOR_REVIEW"},
    "BLOCKED_HANDOFF": {"READY_FOR_REVIEW", "STATE_DESYNC"},
    "PHASE_REVIEW_CEILING": {"READY_FOR_REVIEW", "STATE_DESYNC"},
    "BATCH_REVIEW_CEILING": {"READY_FOR_REVIEW", "STATE_DESYNC"},
    "INFRA_FAIL": {"RUNNING", "READY_FOR_REVIEW", "STATE_DESYNC"},
    "NO_PROGRESS": {"READY_FOR_REVIEW", "STATE_DESYNC"},
    "BLOCKED_SCOPE": {"RUNNING", "STATE_DESYNC"},
    "BLOCKED_VERIFY": {"RUNNING", "STATE_DESYNC"},
    "PASS": {"RUNNING", "STATE_DESYNC"},
}
ACTIVE_FINDING_STATUSES = {"OPEN", "REGRESSED", "NEEDS_TRIAGE", "FIX_CLAIMED"}
REVIEW_LENSES = (
    "repository_grounding",
    "scope_ownership",
    "schema_citation",
    "lifecycle_rollback",
    "security_deployability",
    "benchmark_reproducibility",
    "cross_contract_consistency",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try: os.unlink(temporary)
        except OSError: pass


def _default_status_v2(*, status="NOT_STARTED", task_id="unknown", mode="code") -> dict:
    return {
        "status_version": 2, "status": status, "terminal": status in TERMINAL_STATUSES,
        "task_id": task_id, "mode": mode, "lifecycle_phase": mode.upper(),
        "review_kind": "none", "review_boundary_id": None, "run_id": None,
        "snapshot_hash": "", "previous_snapshot_hash": None, "reason_code": "",
        "reason": "", "next_action": "initialize", "writer_status": "NOT_STARTED",
        "writer_checkpoint_id": None, "work_item_current": 0, "work_item_total": 0,
        "phase_review_count": 0, "batch_review_count": 0,
        "failure_budget_remaining": 3, "ready_for_codex": False,
        "history": [], "updated_at": utc_now(),
    }


def validate_pipeline_status(payload: dict) -> None:
    required = set(_default_status_v2())
    missing = sorted(required - set(payload))
    if missing: raise ValueError("Missing pipeline status fields: " + ", ".join(missing))
    if payload.get("status_version") != 2: raise ValueError("status_version must be 2")
    if payload.get("status") not in ALLOWED_STATUSES: raise ValueError("Unsupported status")
    if bool(payload.get("terminal")) != (payload.get("status") in TERMINAL_STATUSES):
        raise ValueError("terminal does not match status")
    if not payload.get("task_id") or not payload.get("mode"): raise ValueError("task_id and mode required")
    current, total = int(payload.get("work_item_current", 0)), int(payload.get("work_item_total", 0))
    if current < 0 or total < 0 or (total and current > total): raise ValueError("Invalid work-item progress")


def migrate_pipeline_status(project_root: Path, *, task_id: str | None = None,
                            mode: str | None = None, run_id: str | None = None) -> dict:
    path = project_root / ".agent/state/pipeline_status.json"
    legacy = _read_json(path, None)
    if legacy is None:
        return _default_status_v2(task_id=task_id or "unknown", mode=mode or "code")
    if legacy.get("status_version") == 2:
        try:
            validate_pipeline_status(legacy)
        except ValueError as exc:
            broken = _default_status_v2(status="STATE_DESYNC", task_id=task_id or legacy.get("task_id") or "unknown", mode=mode or legacy.get("mode") or "code")
            broken.update(reason_code="MALFORMED_STATUS_V2", reason=str(exc), next_action="repair_state")
            _write_json(path, broken)
            return broken
        return legacy
    if legacy.get("status_version") != 1 or not legacy.get("task_id") or not legacy.get("status"):
        migrated = _default_status_v2(status="STATE_DESYNC", task_id=task_id or legacy.get("task_id") or "unknown", mode=mode or legacy.get("mode") or "code")
        migrated.update(reason_code="MALFORMED_LEGACY_STATUS", reason="Legacy status cannot be migrated safely", next_action="repair_state")
    elif task_id and legacy.get("task_id") != task_id:
        migrated = _default_status_v2(status="STATE_DESYNC", task_id=task_id, mode=mode or legacy.get("mode") or "code")
        migrated.update(run_id=run_id, reason_code="STALE_TASK_IDENTITY", reason="Legacy task identity conflicts with active task", next_action="repair_state")
    else:
        old_status = str(legacy.get("status", "STATE_DESYNC")).upper()
        if old_status not in ALLOWED_STATUSES: old_status = "STATE_DESYNC"
        migrated = _default_status_v2(status=old_status, task_id=legacy["task_id"], mode=mode or legacy.get("mode") or "code")
        for key in ("run_id", "snapshot_hash", "previous_snapshot_hash", "reason_code", "reason", "next_action"):
            if key in legacy: migrated[key] = legacy[key]
        migrated["terminal"] = migrated["status"] in TERMINAL_STATUSES
        migrated["history"] = legacy.get("history", [])
        migrated["updated_at"] = legacy.get("updated_at", utc_now())
    validate_pipeline_status(migrated)
    _write_json(path, migrated)
    return migrated


def write_pipeline_status(
    project_root: Path,
    *,
    status: str,
    task_id: str,
    mode: str,
    run_id: str | None,
    snapshot_hash: str,
    reason_code: str = "",
    reason: str = "",
    next_action: str = "",
    lifecycle_phase: str | None = None,
    review_kind: str | None = None,
    review_boundary_id: str | None = None,
    writer_status: str | None = None,
    writer_checkpoint_id: str | None = None,
    work_item_current: int | None = None,
    work_item_total: int | None = None,
    phase_review_count: int | None = None,
    batch_review_count: int | None = None,
    failure_budget_remaining: int | None = None,
    ready_for_codex: bool | None = None,
    allow_reopen: bool = False,
) -> dict:
    """Write the sole current-status authority and return its payload."""
    status = status.upper()
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported pipeline status: {status}")
    path = project_root / ".agent/state/pipeline_status.json"
    previous = migrate_pipeline_status(project_root, task_id=task_id, mode=mode, run_id=run_id)
    old_status = previous.get("status", "NOT_STARTED")
    if status != old_status and status not in TRANSITIONS.get(old_status, set()) and not allow_reopen:
        raise ValueError(f"Forbidden pipeline transition: {old_status} -> {status}")
    if previous.get("task_id") not in {"unknown", task_id} and not allow_reopen:
        raise ValueError("Pipeline task identity conflict")
    payload = dict(previous)
    history = list(previous.get("history", []))
    history.append({"from": old_status, "to": status, "at": utc_now(), "reason_code": reason_code})
    payload.update({
        "status_version": STATUS_VERSION, "status": status, "terminal": status in TERMINAL_STATUSES,
        "task_id": task_id, "mode": mode, "lifecycle_phase": (lifecycle_phase or mode).upper(),
        "run_id": run_id, "snapshot_hash": snapshot_hash,
        "previous_snapshot_hash": previous.get("snapshot_hash"), "reason_code": reason_code,
        "reason": reason, "next_action": next_action, "history": history[-100:], "updated_at": utc_now(),
    })
    optional = {
        "review_kind": review_kind, "review_boundary_id": review_boundary_id,
        "writer_status": writer_status, "writer_checkpoint_id": writer_checkpoint_id,
        "work_item_current": work_item_current, "work_item_total": work_item_total,
        "phase_review_count": phase_review_count, "batch_review_count": batch_review_count,
        "failure_budget_remaining": failure_budget_remaining, "ready_for_codex": ready_for_codex,
    }
    for key, value in optional.items():
        if value is not None: payload[key] = value
    validate_pipeline_status(payload)
    _write_json(path, payload)
    return payload


def render_status_markdown(title: str, status: dict, extra: Iterable[str] = ()) -> str:
    lines = [
        f"# {title}", "", f"## Status: {status['status']}",
        f"- status_version: {status['status_version']}",
        f"- task_id: {status['task_id']}", f"- mode: {status['mode']}",
        f"- run_id: {status.get('run_id') or 'n/a'}",
        f"- snapshot_hash: {status.get('snapshot_hash') or 'n/a'}",
        f"- reason_code: {status.get('reason_code') or 'n/a'}",
    ]
    if status.get("reason"):
        lines.append(f"- reason: {status['reason']}")
    lines.extend(["", *extra, ""])
    return "\n".join(lines)


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    file: str
    line: int
    evidence: str
    remediation: str
    severity: str = "P1"


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _add(diags: list[Diagnostic], rule: str, file: str, text: str, match, remediation: str,
         severity: str = "P1") -> None:
    evidence = match.group(0).strip().replace("\n", " ")[:240]
    diags.append(Diagnostic(rule, file, _line_number(text, match.start()), evidence, remediation, severity))


def lint_artifacts(project_root: Path, mode: str, artifact_files: list[str], budget: int) -> dict:
    """Run cheap, deterministic research/plan checks and persist JSON + Markdown."""
    diagnostics: list[Diagnostic] = []
    context = project_root / ".agent/context"
    combined = []
    for rel in artifact_files:
        path = context / rel
        if not path.is_file():
            diagnostics.append(Diagnostic("ARTIFACT001", rel, 1, "missing artifact", "Create the complete artifact."))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        combined.append((rel, text))
        # Machine-specific Windows or Unix home paths (repository links/URLs excluded).
        for match in re.finditer(r"(?im)(?:[A-Z]:\\(?:Users|AI_SOFTWARE_FACTORY|Antigravity)\\\S+|/(?:home|Users)/[^\s`]+)", text):
            _add(diagnostics, "PATH001", rel, text, match, "Replace the machine path with a repository-relative path.")
        if len(text) > budget:
            diagnostics.append(Diagnostic("ARTIFACT001", rel, 1, f"{len(text)} chars > {budget}",
                                          "Use section transport; do not truncate content.", "P0"))
        stripped = text.rstrip()
        if stripped.endswith(("{", "[")) or text.count("```") % 2:
            diagnostics.append(Diagnostic("ARTIFACT001", rel, max(1, text.count("\n") + 1),
                                          "artifact ends in an incomplete block", "Complete the final block/section."))

        # Planning-critical assertions need authority, access date and evidence state.
        for match in re.finditer(r"(?im)^.*\b(?:must|required|guarantees?|supported|limit(?:ation)?|according to)\b.*$", text):
            window = text[max(0, match.start() - 240): min(len(text), match.end() + 320)]
            if not re.search(r"https?://", window) or not re.search(r"(?i)(access(?:ed)?|retrieved|truy cập).{0,30}\d{4}", window):
                _add(diagnostics, "TRACE001", rel, text, match,
                     "Add an authority URL, access date, and FACT/INFERENCE evidence state.", "P2")

        # Metrics must specify formula, threshold, and zero-gold behavior.
        for match in re.finditer(r"(?im)^.*\b(?:precision|recall|accuracy|f1|rate|tỷ lệ|metric)\b.*$", text):
            window = text[match.start(): min(len(text), match.end() + 500)]
            required = (r"[/÷]|numerator|tử số", r"denominator|mẫu số", r"(?:>=|<=|>|<|threshold|ngưỡng)", r"zero|0 gold|không có gold")
            if not all(re.search(pattern, window, re.I) for pattern in required):
                _add(diagnostics, "BENCH001", rel, text, match,
                     "Define numerator, denominator, threshold, and zero-gold behavior.")

        if re.search(r"(?i)benchmark|gold set|gold-set", text):
            if not all(re.search(pattern, text, re.I) for pattern in (r"adjudicat|phân xử", r"version|phiên bản", r"construct|construction|xây dựng")):
                diagnostics.append(Diagnostic("BENCH003", rel, 1, "benchmark/gold set lacks a complete protocol",
                                              "Define gold construction, adjudication, and versioning."))

        # HTTP outcome conflation: a single status attached to distinct failure classes.
        for match in re.finditer(r"(?im)^.*\b(?:401|403|408|413|422|429|5\d\d)\b.*$", text):
            terms = re.findall(r"(?i)auth|size|timeout|validat|rate.?limit", match.group(0))
            statuses = set(re.findall(r"\b[1-5]\d\d\b", match.group(0)))
            if len(terms) >= 2 and len(statuses) <= 1:
                _add(diagnostics, "HTTP001", rel, text, match,
                     "Map authentication, size, timeout, validation, and rate-limit failures separately.")

    all_text = "\n".join(text for _, text in combined)
    # Compare concrete implementation paths named as required outside the
    # document's definitive scope block. This intentionally ignores prose-only
    # ideas and repository evidence citations.
    scope_marker = re.search(r"(?i)scope of changes\s*\(definitive|definitive implementation scope", all_text)
    if scope_marker:
        scope_end = re.search(r"(?m)^#{2,3}\s+", all_text[scope_marker.end():])
        end = scope_marker.end() + scope_end.start() if scope_end else len(all_text)
        scope_block = all_text[scope_marker.start():end]
        path_pattern = r"`([^`\n]+\.(?:cs|xaml|csproj|json|ya?ml|ps1|py|addin|dockerfile))`"
        scoped = {value.replace("\\", "/").lower() for value in re.findall(path_pattern, scope_block, re.I)}
        missing = []
        for match in re.finditer(r"(?im)^.*\b(?:required|must|shall|new component|implementation)\b.*$", all_text[end:]):
            for value in re.findall(path_pattern, match.group(0), re.I):
                normalized = value.replace("\\", "/").lower()
                if normalized not in scoped and not normalized.startswith(("source-code/", ".agent/")):
                    missing.append(normalized)
        if missing:
            diagnostics.append(Diagnostic(
                "SCOPE001", artifact_files[0], _line_number(all_text, end),
                "Required paths outside definitive scope: " + ", ".join(sorted(set(missing))[:8]),
                "Add each required implementation path/component to the definitive scope or remove the requirement.",
            ))
    # Reconcile explicit allocation table values when a total is declared.
    total_match = re.search(r"(?i)(?:corpus|total|tổng)\D{0,20}(\d+)", all_text)
    alloc_match = re.search(r"(?i)(?:allocation|phân bổ)\s*[:=]\s*([0-9+\s]+)", all_text)
    if total_match and alloc_match:
        values = [int(x) for x in re.findall(r"\d+", alloc_match.group(1))]
        if values and sum(values) != int(total_match.group(1)):
            diagnostics.append(Diagnostic("BENCH002", artifact_files[0], _line_number(all_text, alloc_match.start()),
                                          f"allocations {values} != total {total_match.group(1)}",
                                          "Make benchmark allocations reconcile with the corpus total."))

    # Detect multiple authoritative schema/scope declarations with different bodies.
    for rule, heading in (("SCOPE002", r"(?:definitive|authoritative)\s+(?:scope|ownership)"),
                          ("SCHEMA001", r"(?:authoritative|canonical)\s+(?:schema|dto|payload|manifest)")):
        blocks = re.findall(rf"(?ims)^#+\s+.*{heading}.*?$\n(.*?)(?=^#|\Z)", all_text)
        normalized = {re.sub(r"\s+", " ", block).strip().lower() for block in blocks if block.strip()}
        if len(normalized) > 1:
            diagnostics.append(Diagnostic(rule, artifact_files[0], 1, f"{len(normalized)} conflicting authoritative blocks",
                                          "Keep exactly one authoritative definition or make the sections consistent."))

    payload = {
        "schema_version": 1, "run_id": str(uuid.uuid4()), "mode": mode,
        "status": "FAIL" if diagnostics else "PASS", "created_at": utc_now(),
        "artifact_files": artifact_files, "transport_budget": budget,
        "diagnostics": [asdict(item) for item in diagnostics],
    }
    reports = project_root / ".agent/reports"
    _write_json(reports / "PRE_REVIEW_LINT.json", payload)
    lines = ["# PRE_REVIEW_LINT.md", "", f"## Status: {payload['status']}",
             f"- run_id: {payload['run_id']}", f"- mode: {mode}", "", "## Diagnostics", ""]
    lines.extend(f"- **{d.rule_id}** `{d.file}:{d.line}` — {d.evidence} — {d.remediation}" for d in diagnostics)
    if not diagnostics:
        lines.append("- None.")
    (reports / "PRE_REVIEW_LINT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def normalize_finding_id(finding: dict) -> str:
    """Semantic identity ignores wording, line location, and severity drift."""
    explicit = finding.get("finding_id") or finding.get("contract_id")
    if explicit:
        return re.sub(r"[^a-z0-9]+", ".", str(explicit).lower()).strip(".")
    text = " ".join(str(finding.get(key, "")) for key in ("family", "title", "body", "file")).lower()
    families = {
        "benchmark": r"benchmark|metric|gold|precision|recall|corpus",
        "security": r"security|auth|credential|secret|fail.?closed|permission",
        "lifecycle": r"lifecycle|rollback|retention|cleanup|concurr|activation|manifest",
        "schema": r"schema|dto|payload|contract|citation|trace|scope|ownership",
        "transport": r"truncat|context|section|artifact|transport",
    }
    family = next((name for name, pattern in families.items() if re.search(pattern, text)), "general")
    contract_keys = {
        "gold-set-reproducibility": r"gold(?:en)?[ -]?set|adjudicat|reproduc",
        "metric-formula": r"numerator|denominator|precision|recall|metric formula",
        "scope-ownership": r"scope|ownership|out.of.scope",
        "schema-consistency": r"schema|dto|payload",
        "rollback-retention": r"rollback|retention|cleanup",
        "authentication": r"authentication|authorization|\bauth\b|credential",
        "artifact-transport": r"truncat|transport|context limit|section batch",
    }
    stable_key = next((key for key, pattern in contract_keys.items() if re.search(pattern, text)), None)
    if stable_key:
        return f"{family}.{stable_key}"
    stop = {"the", "a", "an", "is", "are", "missing", "invalid", "inconsistent", "must", "should",
            "file", "line", "contract", "finding", "not", "and", "or", "of", "to", "for"}
    tokens = [token for token in re.findall(r"[a-z0-9]+", text) if token not in stop and len(token) > 2]
    key = ".".join(sorted(dict.fromkeys(tokens))[:6]) or hashlib.sha256(text.encode()).hexdigest()[:12]
    return f"{family}.{key}"


def merge_finding_ledger(project_root: Path, run_id: str, snapshot_hash: str,
                         findings: list[dict], claimed_resolutions: list[dict] | None = None) -> dict:
    path = project_root / ".agent/state/finding_ledger.json"
    ledger = _read_json(path, {"schema_version": 1, "entries": []})
    entries = {entry["finding_id"]: entry for entry in ledger.get("entries", [])}
    current_ids = set()
    severity_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for finding in findings:
        fid = normalize_finding_id(finding)
        current_ids.add(fid)
        severity = str(finding.get("severity", "P2")).upper()
        entry = entries.get(fid)
        if entry is None:
            entry = {
                "finding_id": fid, "family": fid.split(".", 1)[0], "severity": severity,
                "status": "OPEN", "first_seen_run": run_id, "last_seen_run": run_id,
                "last_seen_snapshot": snapshot_hash, "resolution_evidence": [],
                "resolved_snapshot": None, "regression_count": 0,
            }
            entries[fid] = entry
        else:
            if entry.get("status") == "VERIFIED_RESOLVED":
                entry["status"] = "REGRESSED"
                entry["regression_count"] = int(entry.get("regression_count", 0)) + 1
            elif entry.get("status") not in {"DEFERRED", "SUPERSEDED"}:
                entry["status"] = "OPEN"
            if severity_rank.get(severity, 2) < severity_rank.get(entry.get("severity", "P2"), 2):
                entry["severity"] = severity
            entry.update(last_seen_run=run_id, last_seen_snapshot=snapshot_hash)
    for claim in claimed_resolutions or []:
        fid = normalize_finding_id(claim)
        if fid in entries and fid not in current_ids and claim.get("evidence"):
            entries[fid]["status"] = "FIX_CLAIMED"
            entries[fid]["resolution_evidence"].append(claim["evidence"])
    # A prior FIX_CLAIMED item absent from this complete review is verified closed.
    for fid, entry in entries.items():
        if fid not in current_ids and entry.get("status") == "FIX_CLAIMED":
            entry["status"] = "VERIFIED_RESOLVED"
            entry["resolved_snapshot"] = snapshot_hash
    ledger.update(updated_at=utc_now(), entries=sorted(entries.values(), key=lambda x: x["finding_id"]))
    _write_json(path, ledger)
    return ledger


def active_findings(ledger: dict) -> list[dict]:
    return [entry for entry in ledger.get("entries", []) if entry.get("status") in ACTIVE_FINDING_STATUSES]


def seed_contract_ledger(project_root: Path, snapshot_hash: str, artifact_files: list[str]) -> dict:
    """Seed immutable contract families from explicit stable Markdown sections."""
    path = project_root / ".agent/context/CONTRACT_LEDGER.json"
    existing = _read_json(path, None)
    if existing:
        return existing
    families = {
        "scope": r"scope|ownership", "schema": r"schema|dto|payload",
        "lifecycle": r"activation|rollback|retention|concurr|cleanup",
        "security": r"security|fail.?closed|authentication",
        "benchmark": r"benchmark|metric|gold set|acceptance gate",
        "provenance": r"citation|provenance|source authority|fact/inference",
    }
    contracts = []
    for rel in artifact_files:
        text = (project_root / ".agent/context" / rel).read_text(encoding="utf-8", errors="replace")
        sections = split_markdown_sections(text)
        for family, pattern in families.items():
            candidates = [(sid, body) for sid, body in sections if re.search(pattern, body[:500], re.I)]
            if not candidates:
                continue
            sid, body = max(candidates, key=lambda item: len(item[1]))
            elements = sorted(set(re.findall(r"(?m)^\s*(?:[-*]|\d+\.)\s+`?([^:`\n]{3,80})", body)))[:30]
            contracts.append({
                "contract_id": f"{family}.{sid}", "family": family, "authoritative_section": sid,
                "artifact": rel, "required_elements": elements,
                "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "source_snapshot": snapshot_hash, "status": "VERIFIED",
            })
    ledger = {"schema_version": 1, "created_at": utc_now(), "contracts": contracts, "migrations": []}
    _write_json(path, ledger)
    return ledger


def check_contract_regressions(project_root: Path, artifact_files: list[str]) -> list[dict]:
    ledger = _read_json(project_root / ".agent/context/CONTRACT_LEDGER.json", {"contracts": []})
    texts = {rel: (project_root / ".agent/context" / rel).read_text(encoding="utf-8", errors="replace")
             for rel in artifact_files if (project_root / ".agent/context" / rel).is_file()}
    regressions = []
    for contract in ledger.get("contracts", []):
        text = texts.get(contract.get("artifact", ""), "")
        missing = [element for element in contract.get("required_elements", []) if element.lower() not in text.lower()]
        heading = contract.get("authoritative_section", "")
        if not text or (heading and heading not in {sid for sid, _ in split_markdown_sections(text)}) or missing:
            regressions.append({
                "contract_id": contract.get("contract_id"), "severity": "P1",
                "artifact": contract.get("artifact"), "missing_elements": missing,
                "reason": "Authoritative section or required elements disappeared.",
            })
    return regressions


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
    if not matches:
        return [("document", text)]
    result = []
    if matches[0].start() > 0:
        result.append(("preamble", text[:matches[0].start()]))
    used = {}
    for index, match in enumerate(matches):
        title = re.sub(r"[^a-z0-9]+", "-", match.group(2).lower()).strip("-") or "section"
        used[title] = used.get(title, 0) + 1
        sid = title if used[title] == 1 else f"{title}-{used[title]}"
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((sid, text[match.start():end]))
    return result


def section_batches(project_root: Path, artifact_files: list[str], budget: int) -> dict:
    """Bind every source byte to a stable section and bounded batch."""
    sections, batches, current, current_size = [], [], [], 0
    for rel in artifact_files:
        raw = (project_root / ".agent/context" / rel).read_text(encoding="utf-8", errors="replace")
        for sid, body in split_markdown_sections(raw):
            # A single large heading remains lossless but is given stable part
            # IDs so every transport batch stays bounded.
            parts = [body[index:index + budget] for index in range(0, len(body), budget)] or [""]
            for part_index, part in enumerate(parts, 1):
                part_id = sid if len(parts) == 1 else f"{sid}.part-{part_index}"
                item = {"artifact": rel, "section_id": part_id, "char_count": len(part),
                        "section_hash": hashlib.sha256(part.encode("utf-8")).hexdigest(), "content": part}
                sections.append(item)
                if current and current_size + len(part) > budget:
                    batches.append(current); current, current_size = [], 0
                current.append(item); current_size += len(part)
    if current:
        batches.append(current)
    full_hash = hashlib.sha256("".join(item["content"] for item in sections).encode("utf-8")).hexdigest()
    return {"full_artifact_hash": full_hash, "sections": sections, "batches": batches,
            "excluded_bytes": 0, "complete": True}


def evaluate_convergence(project_root: Path, task_id: str, mode: str, run_id: str,
                         snapshot_hash: str, before: dict, after: dict,
                         max_reviews: int = 6) -> dict:
    before_map = {e["finding_id"]: e for e in before.get("entries", [])}
    after_map = {e["finding_id"]: e for e in after.get("entries", [])}
    resolved = sum(1 for fid, old in before_map.items()
                   if old.get("status") in ACTIVE_FINDING_STATUSES and after_map.get(fid, {}).get("status") == "VERIFIED_RESOLVED")
    regressed = sum(1 for e in after_map.values() if e.get("status") == "REGRESSED")
    introduced = sum(1 for fid, e in after_map.items() if fid not in before_map and e.get("status") in ACTIVE_FINDING_STATUSES)
    net = resolved - regressed - introduced
    path = project_root / ".agent/state/convergence_state.json"
    state = _read_json(path, {"schema_version": 2, "phases": {}, "reviews": []})
    state.setdefault("schema_version", 2)
    state.setdefault("phases", {})
    state.setdefault("reviews", [])
    phase_key = f"{task_id}:{mode}"
    phase = state["phases"].setdefault(phase_key, {"task_id": task_id, "lifecycle_phase": mode,
                                                   "review_count": 0, "batches": {}, "reviews": []})
    active_ids = sorted(item.get("finding_id") for item in active_findings(after))
    batch_id = hashlib.sha256("\0".join(active_ids).encode()).hexdigest()[:16]
    batch_count = int(phase["batches"].get(batch_id, 0)) + 1
    phase_count = int(phase.get("review_count", 0)) + 1
    prior_no_progress = bool(phase["reviews"] and phase["reviews"][-1].get("net_closure", 1) <= 0)
    decision = "NEEDS_FIX"
    reason_code = "OPEN_FINDINGS"
    if not active_findings(after):
        decision, reason_code = "PASS", "SEMANTIC_DEBT_CLOSED"
    elif prior_no_progress and net <= 0:
        decision, reason_code = "NO_PROGRESS", "TWO_CHANGED_SNAPSHOTS_NO_NET_CLOSURE"
    elif batch_count > 2:
        decision, reason_code = "BATCH_REVIEW_CEILING", "BATCH_REVIEW_CEILING"
    elif phase_count > max_reviews:
        decision, reason_code = "PHASE_REVIEW_CEILING", "PHASE_REVIEW_CEILING"
    item = {"run_id": run_id, "snapshot_hash": snapshot_hash, "verified_resolved": resolved,
            "regressed": regressed, "newly_introduced": introduced, "net_closure": net,
            "decision": decision, "reason_code": reason_code, "task_id": task_id,
            "lifecycle_phase": mode, "phase_review_count": phase_count,
            "batch_review_count": batch_count, "finding_batch_id": batch_id, "at": utc_now()}
    phase["review_count"] = phase_count
    phase["batches"][batch_id] = batch_count
    phase["reviews"].append(item)
    state["reviews"].append(item)
    state["updated_at"] = utc_now()
    _write_json(path, state)
    report = project_root / ".agent/reports/CONVERGENCE_REPORT.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CONVERGENCE_REPORT.md", "", f"## Status: {decision}", f"- task_id: {task_id}",
             f"- mode: {mode}", f"- run_id: {run_id}", f"- snapshot_hash: {snapshot_hash}",
             f"- reason_code: {reason_code}", "", "## Trend", "",
             "| Run | Resolved | Regressed | Introduced | Net | Decision |", "|---|---:|---:|---:|---:|---|"]
    lines.extend(f"| {r['run_id']} | {r['verified_resolved']} | {r['regressed']} | {r['newly_introduced']} | {r['net_closure']} | {r['decision']} |" for r in state["reviews"])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return item


def doctor_summary(project_root: Path, configured_budget: int = 0, artifact_size: int = 0) -> dict:
    status = _read_json(project_root / ".agent/state/pipeline_status.json", {})
    convergence = _read_json(project_root / ".agent/state/convergence_state.json", {"reviews": []})
    findings = _read_json(project_root / ".agent/state/finding_ledger.json", {"entries": []})
    lint = _read_json(project_root / ".agent/reports/PRE_REVIEW_LINT.json", {})
    review = _read_json(project_root / ".agent/state/review_run.json", {})
    task_context = _read_json(project_root / ".agent/context/TASK_CONTEXT.json", {})
    contracts = _read_json(project_root / ".agent/context/CONTRACT_LEDGER.json", {})
    failure_budget = task_context.get("failure_budget", {})
    payload = {
        "schema_version": 2, "generated_at": utc_now(), "authoritative_status": status,
        "latest_reviewer_run_id": review.get("run_id"), "latest_handoff_run_id": None,
        "open_finding_families": sorted({e.get("family") for e in active_findings(findings)}),
        "linter_status": lint.get("status", "NOT_RUN"),
        "convergence_trend": [r.get("net_closure") for r in convergence.get("reviews", [])[-6:]],
        "configured_artifact_budget": configured_budget, "actual_artifact_size": artifact_size,
        "stale_report": bool(status and review and status.get("snapshot_hash") != review.get("snapshot_hash")),
        "current_snapshot_hash": status.get("snapshot_hash"),
        "previous_snapshot_hash": status.get("previous_snapshot_hash"),
        "failure_budget": {
            "used": failure_budget.get("used", 0), "remaining": failure_budget.get("remaining"),
            "limit": failure_budget.get("limit"),
            "reopen_count": len(task_context.get("failure_budget_history", [])),
        },
        "contract_ledger_status": contracts.get("seed_status", "SEEDED" if contracts.get("contracts") else "NOT_SEEDED"),
    }
    handoff = _read_json(project_root / ".agent/reports/FIXER_HANDOFF.json", {})
    payload["latest_handoff_run_id"] = handoff.get("review_run_id")
    _write_json(project_root / ".agent/reports/DUAL_AGENT_DOCTOR.json", payload)
    return payload


def migrate_review_history(project_root: Path) -> dict:
    """Conservatively seed semantic history; unknown closure is never invented."""
    reports = project_root / ".agent/reports/codex-reviews"
    path = project_root / ".agent/state/finding_ledger.json"
    existing = _read_json(path, {"schema_version": 1, "entries": []})
    entries = {item["finding_id"]: item for item in existing.get("entries", [])}
    imported_reports = 0
    if reports.is_dir():
        for report_path in sorted(reports.iterdir()):
            if report_path.suffix.lower() not in {".json", ".md"}:
                continue
            findings, run_id, snapshot = [], report_path.stem, "unknown"
            if report_path.suffix.lower() == ".json":
                payload = _read_json(report_path, {})
                run_id = payload.get("run_id", run_id)
                snapshot = payload.get("snapshot_hash", snapshot)
                findings.extend(payload.get("findings", []))
                for batch in payload.get("batches", []):
                    findings.extend(batch.get("findings", []))
            else:
                text = report_path.read_text(encoding="utf-8", errors="replace")
                run_match = re.search(r"(?im)^-\s*run_id:\s*(\S+)", text)
                snap_match = re.search(r"(?im)^-\s*(?:reviewed_diff_hash|snapshot_hash):\s*(\S+)", text)
                if run_match: run_id = run_match.group(1)
                if snap_match: snapshot = snap_match.group(1)
                for match in re.finditer(
                    r"(?ms)^- \*\*(P[0-3])\*\*:\s*`([^`:]+):(\d+)`\s*-\s*(.+?)\n\s{2}(.+?)(?=\n- \*\*P[0-3]|\n## |\Z)", text
                ):
                    findings.append({"severity": match.group(1), "file": match.group(2),
                                     "line": int(match.group(3)), "title": match.group(4).strip(),
                                     "body": re.sub(r"\s+", " ", match.group(5)).strip()})
            if not findings:
                continue
            imported_reports += 1
            for finding in findings:
                fid = normalize_finding_id(finding)
                entry = entries.get(fid)
                if entry is None:
                    entries[fid] = {
                        "finding_id": fid, "family": fid.split(".", 1)[0],
                        "severity": str(finding.get("severity", "P2")).upper(),
                        "status": "NEEDS_TRIAGE", "first_seen_run": run_id, "last_seen_run": run_id,
                        "last_seen_snapshot": snapshot, "resolution_evidence": [],
                        "resolved_snapshot": None, "regression_count": 0,
                    }
                else:
                    entry.update(last_seen_run=run_id, last_seen_snapshot=snapshot)
    ledger = {"schema_version": 1, "updated_at": utc_now(),
              "migration": {"imported_reports": imported_reports, "status": "NEEDS_TRIAGE"},
              "entries": sorted(entries.values(), key=lambda item: item["finding_id"])}
    _write_json(path, ledger)
    return ledger
