"""Durable task context, verification evidence, and operational knowledge.

The markdown reports remain human-facing.  The JSON files written here are the
machine-readable contract that lets a later process resume and audit a task.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
import fnmatch
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


TASK_CONTEXT_SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 1
WRITER_STATUSES = {"IN_PROGRESS", "TASK_COMPLETE", "PHASE_COMPLETE", "BLOCKED"}
CONTENT_REVIEW_LIMIT = 3
NON_CONTENT_REVIEW_OUTCOMES = {
    "INFRA_FAIL", "STALE", "DUPLICATE", "DUPLICATE_SNAPSHOT", "SCHEMA_ERROR",
    "STATE_DESYNC", "CANCELLED", "CANCELED", "INVALID_STATE",
}


class PhaseReviewBlocked(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    return normalized.lower() or "task"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


@contextmanager
def _exclusive_governance_lock(project_root: Path):
    """Serialize task-context budget and approval compare-and-swap operations."""
    path = project_root / ".agent/state/governance.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _phase_review_bucket(context: dict, task_id: str, mode: str) -> dict:
    by_task = context.setdefault("review_attempts_by_phase", {}).setdefault(task_id, {})
    return by_task.setdefault(mode, {
        "completed_content_failures": 0,
        "content_failures": [],
        "outcomes": [],
        "approvals": [],
        "authorizations": [],
    })


def review_phase_state(project_root: Path, task_id: str, mode: str) -> dict:
    context = load_task_context(project_root)
    bucket = _phase_review_bucket(context, task_id, mode) if context else {}
    return json.loads(json.dumps(bucket)) if bucket else {
        "completed_content_failures": 0, "content_failures": [], "outcomes": [],
        "approvals": [], "authorizations": [],
    }


def _available_phase_approval(bucket: dict) -> dict | None:
    counter = int(bucket.get("completed_content_failures", 0))
    return next((item for item in bucket.get("approvals", [])
                 if not item.get("consumed_at") and int(item.get("previous_counter", -1)) == counter), None)


def preflight_phase_review(project_root: Path, task_id: str, mode: str) -> tuple[bool, str]:
    state = review_phase_state(project_root, task_id, mode)
    count = int(state.get("completed_content_failures", 0))
    if count < CONTENT_REVIEW_LIMIT:
        return True, f"Content review failures: {count}/{CONTENT_REVIEW_LIMIT}"
    if _available_phase_approval(state):
        return True, "Human phase-resume approval is available for one review."
    return False, (
        f"PHASE_REVIEW_BLOCKED: {task_id}/{mode} has {count} completed content failures; "
        "approve-phase-resume is required."
    )


def authorize_phase_review_attempt(project_root: Path, task_id: str, mode: str,
                                   snapshot_hash: str, invocation_id: str) -> dict:
    with _exclusive_governance_lock(project_root):
        context = load_task_context(project_root)
        if not context or context.get("task_id") != task_id or context.get("mode") != mode:
            raise PhaseReviewBlocked("REVIEW_IDENTITY_MISMATCH")
        bucket = _phase_review_bucket(context, task_id, mode)
        prior = next((item for item in bucket["authorizations"]
                      if item.get("invocation_id") == invocation_id), None)
        if prior:
            if prior.get("terminal_status"):
                raise PhaseReviewBlocked("INVOCATION_REVIEW_ALREADY_COMPLETED")
            if prior.get("snapshot_hash") != snapshot_hash:
                raise PhaseReviewBlocked("INVOCATION_SNAPSHOT_CHANGED")
            return dict(prior)
        count = int(bucket.get("completed_content_failures", 0))
        approval = None
        if count >= CONTENT_REVIEW_LIMIT:
            approval = _available_phase_approval(bucket)
            if not approval:
                raise PhaseReviewBlocked("PHASE_REVIEW_BLOCKED")
            approval.update(consumed_at=utc_now(), consumed_by_invocation=invocation_id)
        authorization = {
            "authorization_id": str(uuid.uuid4()), "task_id": task_id, "mode": mode,
            "snapshot_hash": snapshot_hash, "invocation_id": invocation_id,
            "content_failures_before": count,
            "approval_id": approval.get("approval_id") if approval else None,
            "authorized_at": utc_now(), "terminal_status": None,
        }
        bucket["authorizations"].append(authorization)
        context["updated_at"] = utc_now()
        _write_json(task_context_path(project_root), context)
        return dict(authorization)


def record_phase_review_outcome(project_root: Path, task_id: str, mode: str, run_id: str,
                                snapshot_hash: str, status: str,
                                invocation_id: str | None = None) -> dict:
    status = str(status).upper()
    with _exclusive_governance_lock(project_root):
        context = load_task_context(project_root)
        if not context or context.get("task_id") != task_id or context.get("mode") != mode:
            return review_phase_state(project_root, task_id, mode)
        bucket = _phase_review_bucket(context, task_id, mode)
        duplicate = any(item.get("run_id") == run_id for item in bucket["outcomes"])
        effective_status = "DUPLICATE" if duplicate else status
        outcome = {"run_id": run_id, "snapshot_hash": snapshot_hash,
                   "status": effective_status, "recorded_at": utc_now()}
        if not duplicate:
            bucket["outcomes"].append(outcome)
        if status == "FAIL" and not duplicate:
            same_snapshot = any(item.get("snapshot_hash") == snapshot_hash for item in bucket["content_failures"])
            if same_snapshot:
                outcome["status"] = "DUPLICATE_SNAPSHOT"
            else:
                bucket["content_failures"].append(dict(outcome))
                bucket["completed_content_failures"] = len(bucket["content_failures"])
                if bucket["completed_content_failures"] >= CONTENT_REVIEW_LIMIT:
                    context["status"] = "blocked_handoff"
                    context["resume_cursor"] = "human_phase_approval"
        if invocation_id:
            authorization = next((item for item in bucket["authorizations"]
                                  if item.get("invocation_id") == invocation_id), None)
            if authorization:
                authorization.update(terminal_status=effective_status, terminal_run_id=run_id,
                                     terminal_snapshot_hash=snapshot_hash, completed_at=utc_now())
        context["updated_at"] = utc_now()
        _write_json(task_context_path(project_root), context)
        return json.loads(json.dumps(bucket))


def approve_phase_resume(project_root: Path, task_id: str, mode: str,
                         blocked_run_id: str, reason: str) -> dict:
    if not reason.strip():
        raise ValueError("APPROVAL_REASON_REQUIRED")
    with _exclusive_governance_lock(project_root):
        context = load_task_context(project_root)
        if not context or context.get("task_id") != task_id or context.get("mode") != mode:
            raise ValueError("APPROVAL_IDENTITY_MISMATCH")
        bucket = _phase_review_bucket(context, task_id, mode)
        count = int(bucket.get("completed_content_failures", 0))
        if count < CONTENT_REVIEW_LIMIT:
            raise ValueError("PHASE_NOT_BLOCKED")
        last_run = bucket.get("content_failures", [{}])[-1].get("run_id")
        if blocked_run_id != last_run:
            raise ValueError("BLOCKED_RUN_ID_MISMATCH")
        if _available_phase_approval(bucket):
            raise ValueError("UNCONSUMED_APPROVAL_EXISTS")
        approval = {
            "approval_id": str(uuid.uuid4()), "task_id": task_id, "mode": mode,
            "blocked_run_id": blocked_run_id, "approved_at": utc_now(),
            "previous_counter": count, "reason": reason.strip(),
            "consumed_at": None, "consumed_by_invocation": None,
        }
        bucket["approvals"].append(approval)
        context.setdefault("events", []).append({
            "at": approval["approved_at"], "type": "phase_resume_approved",
            "detail": f"{approval['approval_id']} for {blocked_run_id}: {reason.strip()}",
        })
        context["updated_at"] = utc_now()
        _write_json(task_context_path(project_root), context)
        return dict(approval)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def task_context_path(project_root: Path) -> Path:
    return project_root / ".agent/context/TASK_CONTEXT.json"


def evidence_manifest_path(project_root: Path) -> Path:
    return project_root / ".agent/state/EVIDENCE_MANIFEST.json"


def load_task_context(project_root: Path) -> dict:
    path = task_context_path(project_root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def writer_checkpoint_path(project_root: Path) -> Path:
    return project_root / ".agent/state/writer_checkpoint.json"


def load_writer_checkpoint(project_root: Path) -> dict:
    return _read_json(writer_checkpoint_path(project_root), {}) or {}


def _scope_allows(path: str, scope: dict) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    allowed = scope.get("allowed_files", [])
    forbidden = scope.get("forbidden", [])
    return bool(allowed) and any(fnmatch.fnmatch(normalized, item.replace("\\", "/")) for item in allowed) and not any(fnmatch.fnmatch(normalized, item.replace("\\", "/")) for item in forbidden)


def validate_writer_readiness(project_root: Path, payload: dict, current_snapshot_hash: str) -> dict:
    context = load_task_context(project_root)
    if not context or payload.get("task_id") != context.get("task_id"):
        raise ValueError("WRITER_CHECKPOINT_TASK_MISMATCH")
    phase = str(payload.get("phase", "")).lower()
    if phase not in {"research", "plan", "code", "release"} or phase != str(context.get("mode", "")).lower():
        raise ValueError("WRITER_CHECKPOINT_PHASE_MISMATCH")
    if payload.get("status") not in WRITER_STATUSES:
        raise ValueError("WRITER_CHECKPOINT_INVALID_STATUS")
    current = int(payload.get("work_item_current", -1)); total = int(payload.get("work_item_total", -1))
    if current < 0 or total <= 0 or current > total:
        raise ValueError("WRITER_CHECKPOINT_INVALID_PROGRESS")
    previous = load_writer_checkpoint(project_root)
    if previous and previous.get("task_id") == payload.get("task_id"):
        old_current = int(previous.get("work_item_current", 0))
        if not payload.get("rollback_evidence") and current != old_current + 1:
            raise ValueError("WRITER_CHECKPOINT_PROGRESS_NOT_MONOTONIC")
    if payload.get("snapshot_hash") != current_snapshot_hash:
        raise ValueError("WRITER_CHECKPOINT_SNAPSHOT_MISMATCH")
    latest_review = _read_json(project_root / ".agent/state/review_run.json", {}) or {}
    if payload.get("ready_for_codex") and current_snapshot_hash in {
        previous.get("snapshot_hash"), latest_review.get("snapshot_hash")
    }:
        raise ValueError("WRITER_CHECKPOINT_UNCHANGED_SNAPSHOT")
    scope = _read_json(project_root / ".agent/context/TASK_SCOPE.json", {}) or context.get("scope", {})
    invalid_files = [item for item in payload.get("changed_files", []) if not _scope_allows(str(item), scope)]
    if invalid_files:
        raise ValueError("WRITER_CHECKPOINT_SCOPE: " + ", ".join(invalid_files))
    checks = payload.get("checks", [])
    if not checks:
        raise ValueError("WRITER_CHECKPOINT_CHECKS_MISSING")
    claims = {str(item.get("finding_id")): item for item in payload.get("finding_claims", []) if item.get("finding_id")}
    blockers = {str(item.get("finding_id")): item for item in payload.get("blockers", []) if item.get("finding_id")}
    ledger = _read_json(project_root / ".agent/state/finding_ledger.json", {"entries": []}) or {"entries": []}
    known = {str(item.get("finding_id")) for item in ledger.get("entries", [])}
    unknown = sorted((set(claims) | set(blockers)) - known)
    if unknown: raise ValueError("WRITER_CHECKPOINT_UNKNOWN_FINDING: " + ", ".join(unknown))
    active = {str(item.get("finding_id")) for item in ledger.get("entries", []) if item.get("status") in {"OPEN", "REGRESSED", "NEEDS_TRIAGE", "FIX_CLAIMED"}}
    unresolved = [fid for fid in active if not claims.get(fid, {}).get("evidence") and not blockers.get(fid, {}).get("evidence")]
    if payload.get("ready_for_codex"):
        if any(str(item.get("status", "")).upper() != "PASS" for item in checks):
            raise ValueError("WRITER_CHECKPOINT_CHECK_FAILED")
        if unresolved:
            raise ValueError("WRITER_CHECKPOINT_FINDINGS_UNACCOUNTED: " + ", ".join(sorted(unresolved)))
        if payload.get("status") not in {"TASK_COMPLETE", "PHASE_COMPLETE"}:
            raise ValueError("WRITER_CHECKPOINT_NOT_COMPLETE")
        policy = context.get("execution_policy", "checkpointed")
        if policy == "continuous" and payload.get("status") != "PHASE_COMPLETE" and not payload.get("review_boundary_id"):
            raise ValueError("WRITER_CHECKPOINT_BOUNDARY_REQUIRED")
    return {"active_findings": sorted(active), "unresolved": sorted(unresolved), "latest_review_run": latest_review.get("run_id")}


def record_writer_checkpoint(project_root: Path, payload: dict, current_snapshot_hash: str) -> dict:
    validation = validate_writer_readiness(project_root, payload, current_snapshot_hash)
    checkpoint = dict(payload)
    checkpoint.update({
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_id": str(uuid.uuid4()),
        "snapshot_hash": current_snapshot_hash,
        "latest_review_run_id": validation.get("latest_review_run"),
        "reservation": {"state": "READY" if payload.get("ready_for_codex") else "NOT_READY", "run_id": None, "updated_at": utc_now()},
        "recorded_at": utc_now(),
    })
    _write_json(writer_checkpoint_path(project_root), checkpoint)
    return checkpoint


def reserve_writer_checkpoint(project_root: Path, task_id: str, phase: str, snapshot_hash: str,
                              run_id: str, review_kind: str, boundary_id: str | None) -> dict:
    checkpoint = load_writer_checkpoint(project_root)
    if not checkpoint: raise ValueError("WRITER_CHECKPOINT_REQUIRED")
    if checkpoint.get("task_id") != task_id or checkpoint.get("phase") != phase:
        raise ValueError("WRITER_CHECKPOINT_IDENTITY_MISMATCH")
    if checkpoint.get("snapshot_hash") != snapshot_hash or not checkpoint.get("ready_for_codex"):
        raise ValueError("WRITER_CHECKPOINT_NOT_READY")
    reservation = checkpoint.get("reservation", {})
    if reservation.get("state") != "READY":
        raise ValueError("WRITER_CHECKPOINT_ALREADY_RESERVED")
    checkpoint["reservation"] = {"state": "RESERVED", "run_id": run_id, "review_kind": review_kind,
                                 "review_boundary_id": boundary_id, "updated_at": utc_now()}
    _write_json(writer_checkpoint_path(project_root), checkpoint)
    return checkpoint


def transition_checkpoint_reservation(project_root: Path, run_id: str, state: str) -> dict:
    if state not in {"LAUNCHED", "CONSUMED", "READY"}: raise ValueError("Invalid reservation state")
    checkpoint = load_writer_checkpoint(project_root)
    reservation = checkpoint.get("reservation", {})
    if reservation.get("run_id") != run_id: raise ValueError("WRITER_CHECKPOINT_RESERVATION_MISMATCH")
    reservation.update(state=state, updated_at=utc_now())
    if state == "READY": reservation["run_id"] = None
    checkpoint["reservation"] = reservation
    _write_json(writer_checkpoint_path(project_root), checkpoint)
    return checkpoint


def reconcile_checkpoint_reservation(project_root: Path, stale_after_seconds: int = 300,
                                     now: datetime | None = None) -> dict:
    """Recover a crash before launch without ever duplicating a launched review."""
    checkpoint = load_writer_checkpoint(project_root)
    reservation = checkpoint.get("reservation", {})
    if reservation.get("state") != "RESERVED":
        return checkpoint
    try:
        updated_at = datetime.fromisoformat(str(reservation.get("updated_at", "")).replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return checkpoint
    current = now or datetime.now(timezone.utc)
    if (current - updated_at).total_seconds() < max(0, stale_after_seconds):
        return checkpoint
    reservation.update(state="READY", run_id=None, recovered_from="RESERVED", updated_at=utc_now())
    checkpoint["reservation"] = reservation
    _write_json(writer_checkpoint_path(project_root), checkpoint)
    return checkpoint


def initialize_task_context(
    project_root: Path,
    project_name: str,
    task_id: str,
    feature: str,
    mode: str,
    scope: dict,
    snapshot_hash: str,
    snapshot_files: list[str],
    profile: dict,
    *,
    force: bool = False,
) -> dict:
    path = task_context_path(project_root)
    existing = load_task_context(project_root)
    if existing and existing.get("task_id") == task_id and not force:
        now = utc_now()
        _phase_review_bucket(existing, task_id, mode)
        existing["feature"] = feature
        existing["mode"] = mode
        existing["lifecycle_phase"] = mode
        existing["execution_policy"] = scope.get("execution_policy", existing.get("execution_policy", "checkpointed"))
        existing["repository_snapshot"] = {
            "hash": snapshot_hash,
            "files": snapshot_files,
        }
        existing["scope"] = {
            "allowed_files": scope.get("allowed_files", []),
            "forbidden": scope.get("forbidden", []),
            "artifact_files": scope.get("artifact_files", []),
        }
        existing["relevant_files"] = list(snapshot_files)
        existing["verification_commands"] = {
            stage: profile.get(f"{stage}_command") or None
            for stage in ("build", "test", "lint")
        }
        existing["updated_at"] = now
        existing.setdefault("events", []).append(
            {"at": now, "type": "context_refreshed", "detail": f"Mode set to {mode}"}
        )
        _write_json(path, existing)
        return existing

    budget = profile.get("failure_budget", {})
    limit = max(1, int(budget.get("max_failed_attempts", 3)))
    verification_commands = {
        stage: profile.get(f"{stage}_command") or None
        for stage in ("build", "test", "lint")
    }
    now = utc_now()
    payload = {
        "schema_version": TASK_CONTEXT_SCHEMA_VERSION,
        "task_id": task_id,
        "project": project_name,
        "feature": feature,
        "mode": mode,
        "lifecycle_phase": mode,
        "execution_policy": scope.get("execution_policy", "checkpointed"),
        "work_item_current": 0,
        "work_item_total": 0,
        "status": "initialized",
        "resume_cursor": "scope_ready",
        "created_at": now,
        "updated_at": now,
        "repository_snapshot": {
            "hash": snapshot_hash,
            "files": snapshot_files,
        },
        "scope": {
            "allowed_files": scope.get("allowed_files", []),
            "forbidden": scope.get("forbidden", []),
            "artifact_files": scope.get("artifact_files", []),
        },
        "relevant_files": list(snapshot_files),
        "constraints": [
            "Changes must remain inside TASK_SCOPE.json.",
            "Completion claims require fresh verification evidence when policy enables it.",
        ],
        "decisions": [],
        "verification_commands": verification_commands,
        "evidence": [],
        "failure_budget": {
            "limit": limit,
            "used": 0,
            "remaining": limit,
            "failed_attempts": [],
        },
        "review_attempts_by_phase": {},
        "events": [
            {"at": now, "type": "initialized", "detail": "Task context created"}
        ],
    }
    _phase_review_bucket(payload, task_id, mode)
    _write_json(path, payload)
    return payload


def update_task_context(
    project_root: Path,
    *,
    status: str | None = None,
    resume_cursor: str | None = None,
    event_type: str | None = None,
    detail: str = "",
    evidence_ref: str | None = None,
) -> dict:
    context = load_task_context(project_root)
    if not context:
        return {}
    now = utc_now()
    if status:
        context["status"] = status
    if resume_cursor:
        context["resume_cursor"] = resume_cursor
    if evidence_ref and evidence_ref not in context.setdefault("evidence", []):
        context["evidence"].append(evidence_ref)
    if event_type:
        context.setdefault("events", []).append(
            {"at": now, "type": event_type, "detail": detail}
        )
    context["updated_at"] = now
    _write_json(task_context_path(project_root), context)
    return context


def record_failed_attempt(
    project_root: Path,
    *,
    stage: str,
    hypothesis: str,
    evidence: str,
    run_id: str | None = None,
    snapshot_hash: str | None = None,
) -> tuple[dict, bool]:
    context = load_task_context(project_root)
    if not context:
        return {}, False
    failure = context.setdefault(
        "failure_budget",
        {"limit": 3, "used": 0, "remaining": 3, "failed_attempts": []},
    )
    if not snapshot_hash:
        manifest = _read_json(project_root / ".agent/state/review_run.json", {})
        snapshot_hash = str(manifest.get("snapshot_hash", ""))
    normalized = "\0".join(
        part.strip().lower() for part in (
            snapshot_hash or "unknown-snapshot",
            stage,
            hypothesis,
            evidence,
        )
    )
    fingerprint = sha256_text(normalized)[:16]
    prior_attempts = failure.setdefault("failed_attempts", [])
    if any(item.get("fingerprint") == fingerprint for item in prior_attempts):
        context["last_attempt_result"] = "DUPLICATE_ATTEMPT"
        context["updated_at"] = utc_now()
        _write_json(task_context_path(project_root), context)
        return context, int(failure.get("remaining", 0)) == 0

    attempt = {
        "at": utc_now(),
        "stage": stage,
        "hypothesis": hypothesis,
        "evidence": evidence,
        "run_id": run_id,
        "snapshot_hash": snapshot_hash,
        "fingerprint": fingerprint,
    }
    prior_attempts.append(attempt)
    failure["used"] = int(failure.get("used", 0)) + 1
    failure["remaining"] = max(0, int(failure.get("limit", 3)) - failure["used"])
    exhausted = failure["remaining"] == 0
    context["status"] = "blocked_handoff" if exhausted else "needs_fix"
    context["resume_cursor"] = "root_cause_handoff" if exhausted else "fix_required"
    context["last_attempt_result"] = "RECORDED"
    context["updated_at"] = utc_now()
    _write_json(task_context_path(project_root), context)
    if exhausted:
        write_bug_episode(project_root, context)
        write_root_cause_handoff(project_root, context)
    return context, exhausted


def prepare_failure_budget_retry(
    project_root: Path,
    current_snapshot_hash: str,
    resume_hypothesis: str | None = None,
) -> tuple[bool, str]:
    """Block blind retries; reopen an exhausted budget only for new code plus a hypothesis."""
    context = load_task_context(project_root)
    if not context:
        return True, "No durable task context yet."
    phase_ready, phase_detail = preflight_phase_review(
        project_root, str(context.get("task_id", "unknown")), str(context.get("mode", "code"))
    )
    if not phase_ready:
        return False, phase_detail
    phase_state = review_phase_state(
        project_root, str(context.get("task_id", "unknown")), str(context.get("mode", "code"))
    )
    if int(phase_state.get("completed_content_failures", 0)) >= CONTENT_REVIEW_LIMIT:
        # The approval is consumed only by authorize_phase_review_attempt just
        # before launch. Failure-budget history is never reset by approval.
        return True, phase_detail
    failure = context.get("failure_budget", {})
    remaining = int(failure.get("remaining", failure.get("limit", 3)))
    if remaining > 0:
        return True, f"Failure budget remaining: {remaining}"

    manifest_path = project_root / ".agent/state/review_run.json"
    last_snapshot_hash = ""
    if manifest_path.exists():
        try:
            last_snapshot_hash = json.loads(manifest_path.read_text(encoding="utf-8")).get("snapshot_hash", "")
        except Exception:
            last_snapshot_hash = ""
    if not resume_hypothesis or not resume_hypothesis.strip():
        return False, "Failure budget exhausted. Provide --resume-hypothesis after making a scoped code change."
    if not last_snapshot_hash or current_snapshot_hash == last_snapshot_hash:
        return False, "Failure budget exhausted and the task snapshot is unchanged; another review would repeat the same attempt."

    # Convergence v2 requires observable closure evidence, not snapshot churn
    # plus prose.  Shadow mode records the old behavior without enforcing it.
    profile_path = project_root / ".agent/project_profile.json"
    profile = _read_json(profile_path, {}) if profile_path.exists() else {}
    if profile.get("dual_agents", {}).get("convergence_v2", False):
        checkpoint = load_writer_checkpoint(project_root)
        if (not checkpoint or not checkpoint.get("ready_for_codex")
                or checkpoint.get("snapshot_hash") != current_snapshot_hash
                or checkpoint.get("task_id") != context.get("task_id")
                or checkpoint.get("phase") != context.get("mode")):
            return False, "Failure budget cannot reopen: a valid changed-snapshot writer checkpoint is required."
        if checkpoint.get("retry_hypothesis", "").strip() != resume_hypothesis.strip():
            return False, "Failure budget cannot reopen: checkpoint hypothesis does not match the requested hypothesis."
        ledger = _read_json(project_root / ".agent/state/finding_ledger.json", {"entries": []})
        active = {
            item.get("finding_id") for item in ledger.get("entries", [])
            if item.get("status") in {"OPEN", "REGRESSED", "NEEDS_TRIAGE", "FIX_CLAIMED"}
        }
        completion = _read_json(project_root / ".agent/state/fixer_completion.json", {})
        evidence_by_id = {
            item.get("finding_id"): item.get("evidence")
            for item in completion.get("resolved_findings", []) if item.get("evidence")
        }
        missing = sorted(fid for fid in active if fid not in evidence_by_id)
        if missing:
            return False, (
                "Failure budget cannot reopen: resolution evidence is missing for "
                + ", ".join(missing)
            )

    now = utc_now()
    history = context.setdefault("failure_budget_history", [])
    history.append({
        "closed_at": now,
        "resume_hypothesis": resume_hypothesis.strip(),
        "previous_snapshot_hash": last_snapshot_hash,
        "new_snapshot_hash": current_snapshot_hash,
        "attempts": list(failure.get("failed_attempts", [])),
    })
    limit = max(1, int(failure.get("limit", 3)))
    context["failure_budget"] = {
        "limit": limit,
        "used": 0,
        "remaining": limit,
        "failed_attempts": [],
    }
    context["status"] = "retry_authorized"
    context["resume_cursor"] = "review_retry"
    context.setdefault("events", []).append({
        "at": now,
        "type": "failure_budget_reopened",
        "detail": resume_hypothesis.strip(),
    })
    context["updated_at"] = now
    _write_json(task_context_path(project_root), context)
    write_resumed_root_cause_handoff(project_root, context, history[-1])
    return True, "Failure budget reopened for a changed snapshot and explicit hypothesis."


def build_evidence_manifest(
    project_root: Path,
    task_id: str,
    snapshot_before: str,
    snapshot_after: str,
    results: list[dict],
) -> dict:
    required_results = [item for item in results if item.get("required", False)]
    status = (
        "PASS"
        if snapshot_before == snapshot_after
        and all(item.get("status") == "PASS" for item in required_results)
        else "FAIL"
    )
    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "task_id": task_id,
        "created_at": utc_now(),
        "snapshot_before": snapshot_before,
        "snapshot_after": snapshot_after,
        "fresh": snapshot_before == snapshot_after,
        "status": status,
        "results": results,
    }
    _write_json(evidence_manifest_path(project_root), payload)
    update_task_context(
        project_root,
        status="verified" if status == "PASS" else "verification_failed",
        resume_cursor="review_ready" if status == "PASS" else "verify_required",
        event_type="verification",
        detail=f"Evidence run {payload['run_id']} finished with {status}",
        evidence_ref=".agent/state/EVIDENCE_MANIFEST.json",
    )
    return payload


def validate_fresh_evidence(
    project_root: Path,
    task_id: str | None,
    current_snapshot: str,
    required_stages: list[str],
) -> tuple[bool, list[str], dict]:
    path = evidence_manifest_path(project_root)
    if not path.exists():
        return False, ["EVIDENCE_MANIFEST.json is missing."], {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"EVIDENCE_MANIFEST.json is invalid: {exc}"], {}

    issues = []
    if task_id and manifest.get("task_id") != task_id:
        issues.append("Evidence task_id does not match TASK_SCOPE.json.")
    if not manifest.get("fresh") or manifest.get("snapshot_after") != current_snapshot:
        issues.append("Verification evidence is stale for the current repository snapshot.")
    by_stage = {item.get("stage"): item for item in manifest.get("results", [])}
    for stage in required_stages:
        item = by_stage.get(stage)
        if not item:
            issues.append(f"Required evidence stage '{stage}' is missing.")
        elif item.get("status") != "PASS":
            issues.append(f"Required evidence stage '{stage}' did not pass.")
    if manifest.get("status") != "PASS":
        issues.append("Evidence manifest status is not PASS.")
    return not issues, issues, manifest


def knowledge_root(project_root: Path) -> Path:
    return project_root / ".agent/knowledge"


def ensure_knowledge_layout(project_root: Path) -> None:
    root = knowledge_root(project_root)
    for relative in ("memory/bugs", "memory/decisions", "learn", "later"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Operational Knowledge\n\n"
            "- `memory/`: facts, decisions, and bug episodes used by agents.\n"
            "- `learn/`: curated explanations for humans; never generated by default.\n"
            "- `later/`: out-of-scope findings captured without widening the active task.\n\n"
            "Markdown is the source of truth. Any future search index must be rebuildable.\n",
            encoding="utf-8",
        )


def write_later_finding(project_root: Path, task_id: str, files: list[str]) -> Path | None:
    if not files:
        return None
    ensure_knowledge_layout(project_root)
    path = knowledge_root(project_root) / "later" / f"{_slug(task_id)}.md"
    lines = [
        f"# Deferred findings for {task_id}",
        "",
        f"Updated: {utc_now()}",
        "",
        "These changed files were outside the active task boundary. They were recorded, not fixed:",
        "",
    ]
    lines.extend(f"- `{item}`" for item in sorted(set(files)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_bug_episode(project_root: Path, context: dict) -> Path:
    ensure_knowledge_layout(project_root)
    task_id = context.get("task_id", "task")
    path = knowledge_root(project_root) / "memory/bugs" / f"{_slug(task_id)}.md"
    attempts = context.get("failure_budget", {}).get("failed_attempts", [])
    lines = [
        "---",
        f'title: "Failure budget exhausted: {task_id}"',
        f'description: "Repeated task attempts exhausted the configured failure budget"',
        "tags: [failure-budget, blocked-handoff, pipeline]",
        "type: episode",
        "importance: 4",
        "---",
        "",
        f"# Failure budget exhausted: {task_id}",
        "",
        "## Symptom",
        context.get("feature", "Unknown task failure"),
        "",
        "## Attempts",
    ]
    for index, attempt in enumerate(attempts, 1):
        lines.append(
            f"{index}. **{attempt.get('stage', 'unknown')}** — "
            f"{attempt.get('hypothesis', 'No hypothesis')} — {attempt.get('evidence', '')}"
        )
    lines.extend(
        [
            "",
            "## Root Cause",
            "Unknown. Investigation stopped after the configured failure budget.",
            "",
            "## Prevention",
            "Resume only with a new testable hypothesis or new evidence.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_root_cause_handoff(project_root: Path, context: dict) -> Path:
    reports = project_root / ".agent/reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "ROOT_CAUSE_HANDOFF.md"
    attempts = context.get("failure_budget", {}).get("failed_attempts", [])
    lines = [
        "# ROOT_CAUSE_HANDOFF.md",
        "",
        "## Status: BLOCKED_HANDOFF",
        f"- task_id: {context.get('task_id', 'unknown')}",
        f"- failure_budget: {len(attempts)} / {context.get('failure_budget', {}).get('limit', 3)}",
        "",
        "## Failed Attempts",
        "",
    ]
    for index, attempt in enumerate(attempts, 1):
        lines.extend(
            [
                f"### {index}. {attempt.get('stage', 'unknown')}",
                f"- Hypothesis: {attempt.get('hypothesis', '')}",
                f"- Evidence: {attempt.get('evidence', '')}",
                f"- Run: {attempt.get('run_id') or 'n/a'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Resume Condition",
            "Provide a new falsifiable hypothesis or new observable evidence. Do not repeat an exhausted attempt.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_resumed_root_cause_handoff(project_root: Path, context: dict, resume_entry: dict) -> Path:
    """Make an old terminal handoff visibly historical after an authorized retry."""
    reports = project_root / ".agent/reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "ROOT_CAUSE_HANDOFF.md"
    lines = [
        "# ROOT_CAUSE_HANDOFF.md",
        "",
        "## Status: RESUMED_HISTORY",
        f"- task_id: {context.get('task_id', 'unknown')}",
        f"- reopened_at: {resume_entry.get('closed_at', utc_now())}",
        f"- previous_snapshot: {resume_entry.get('previous_snapshot_hash', '')}",
        f"- resumed_snapshot: {resume_entry.get('new_snapshot_hash', '')}",
        "",
        "## Resume Hypothesis",
        resume_entry.get("resume_hypothesis", ""),
        "",
        "## Current Meaning",
        "This file is historical, not a terminal gate. Use TASK_CONTEXT.json and DUAL_AGENT_REPORT.md for current status.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


import os

class ReviewLifecycleGuard:
    def __init__(self, project_root: Path, task_id: str, mode: str, checkpoint_authorization: dict | None = None):
        self.project_root = project_root
        self.task_id = task_id
        self.mode = mode
        self.checkpoint_authorization = checkpoint_authorization
        self.lock_path = self.project_root / ".agent" / "state" / f"{task_id}_{mode}.lock"
        self._fd = None

    def acquire(self):
        try:
            # os.O_CREAT | os.O_EXCL | os.O_WRONLY is cross-platform atomic file creation
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self._fd, str(os.getpid()).encode())
        except FileExistsError:
            raise RuntimeError("RUN_ALREADY_ACTIVE")

    def release(self):
        if self._fd is not None:
            os.close(self._fd)
            try:
                os.remove(str(self.lock_path))
            except OSError:
                pass
            self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

