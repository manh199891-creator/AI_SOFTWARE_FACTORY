"""Canonical/deployed runtime integrity and managed-profile projection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

MANIFEST_VERSION = 1
RUNTIME_FILES = (
    "harness.py", "review_pipeline.py", "dual_agent_runtime.py", "learning_guard.py",
    "evolution_pipeline.py", "workflow_governance.py", "convergence_pipeline.py",
    "runtime_integrity.py",
)
SKILL_PACKAGES = ("skills/dual-agent", "skills/dual-agent-pipeline")
MANAGED_PROFILE_KEYS = (
    "auto_fix", "convergence_v2", "convergence_shadow", "max_reviews_per_phase",
    "execution_policy", "review_boundaries",
)


class IntegrityError(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _atomic_json(path: Path, payload: dict) -> None:
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
        try:
            os.unlink(temporary)
        except OSError:
            pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def managed_profile_projection(profile: dict) -> dict:
    agents = profile.get("dual_agents", {})
    return {key: agents.get(key) for key in MANAGED_PROFILE_KEYS}


def merge_managed_profile(target: dict, canonical: dict) -> dict:
    merged = json.loads(json.dumps(target))
    managed = merged.setdefault("dual_agents", {})
    source = canonical.get("dual_agents", {})
    for key in MANAGED_PROFILE_KEYS:
        if key in source:
            managed[key] = source[key]
    return merged


def resolve_source_root(project_root: Path, profile: dict | None = None) -> Path:
    project_root = project_root.resolve()
    profile = profile or _read_json(project_root / ".agent/project_profile.json", {}) or {}
    source_path = str(profile.get("source_path", "source-code")).strip() or "source-code"
    candidate = (project_root / source_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise IntegrityError("PROFILE_DRIFT", f"source_path escapes project root: {source_path}") from exc
    if not candidate.exists():
        raise IntegrityError("PROFILE_DRIFT", f"source_path does not exist: {candidate}")
    return candidate


def _inventory(factory_root: Path) -> list[Path]:
    files = [factory_root / name for name in RUNTIME_FILES]
    files.extend(sorted(path for path in (factory_root / "schemas").rglob("*") if path.is_file()))
    for package in SKILL_PACKAGES:
        root = factory_root / package
        files.extend(sorted(path for path in root.rglob("*") if path.is_file()))
    files.extend([
        factory_root / "RevitAddinSolution/.agent/project_profile.json",
        factory_root / "NavisAddinSolution/.agent/project_profile.json",
        factory_root / ".agent/project_profile.json",
    ])
    return sorted(set(files), key=lambda item: item.as_posix().lower())


def build_manifest(factory_root: Path, output_path: Path | None = None) -> dict:
    factory_root = factory_root.resolve()
    entries = []
    missing = []
    for path in _inventory(factory_root):
        if not path.is_file():
            missing.append(path.relative_to(factory_root).as_posix())
            continue
        entries.append({
            "path": path.relative_to(factory_root).as_posix(),
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        })
    if missing:
        raise IntegrityError("MISSING_RUNTIME_MODULE", "Missing: " + ", ".join(missing))
    profiles = {}
    for name, rel in (
        ("factory", ".agent/project_profile.json"),
        ("RevitAddinSolution", "RevitAddinSolution/.agent/project_profile.json"),
        ("NavisAddinSolution", "NavisAddinSolution/.agent/project_profile.json"),
    ):
        profiles[name] = managed_profile_projection(_read_json(factory_root / rel, {}) or {})
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "files": entries,
        "managed_profiles": profiles,
    }
    manifest_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload["manifest_sha256"] = manifest_hash
    if output_path:
        _atomic_json(output_path, payload)
    return payload


def verify_manifest(root: Path, manifest_path: Path, *, profile_path: Path | None = None,
                    expected_profile: dict | None = None) -> dict:
    root = root.resolve()
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != MANIFEST_VERSION:
        raise IntegrityError("RUNTIME_DRIFT", f"Invalid runtime manifest: {manifest_path}")
    for entry in manifest.get("files", []):
        path = root / entry["path"]
        if not path.is_file():
            raise IntegrityError("MISSING_RUNTIME_MODULE", entry["path"])
        if sha256_file(path) != entry.get("sha256") or path.stat().st_size != entry.get("size"):
            raise IntegrityError("RUNTIME_DRIFT", entry["path"])
    if profile_path and expected_profile is not None:
        actual = _read_json(profile_path, {}) or {}
        if managed_profile_projection(actual) != managed_profile_projection(expected_profile):
            raise IntegrityError("PROFILE_DRIFT", str(profile_path))
    return {"status": "PASS", "manifest_sha256": manifest.get("manifest_sha256"), "file_count": len(manifest.get("files", []))}


def verify_deployment_journal(project_root: Path) -> None:
    journal = _read_json(project_root / ".agents/deployment_journal.json", {}) or {}
    if journal.get("status") in {"DEPLOYING", "ROLLING_BACK"}:
        raise IntegrityError("RUNTIME_DRIFT", f"Incomplete deployment journal: {journal.get('status')}")


def verify_deployed_bundle(target_root: Path, project_name: str) -> dict:
    verify_deployment_journal(target_root)
    manifest_path = target_root / ".agents/runtime/runtime_manifest.json"
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != 1:
        raise IntegrityError("MISSING_RUNTIME_MODULE", str(manifest_path))
    for entry in manifest.get("files", []):
        path = target_root / entry.get("path", "")
        if not path.is_file(): raise IntegrityError("MISSING_RUNTIME_MODULE", entry.get("path", ""))
        if sha256_file(path) != entry.get("sha256") or path.stat().st_size != entry.get("size"):
            raise IntegrityError("RUNTIME_DRIFT", entry.get("path", ""))
    profile = _read_json(target_root / f".agents/factory/{project_name}/.agent/project_profile.json", {}) or {}
    if managed_profile_projection(profile) != manifest.get("managed_profile"):
        raise IntegrityError("PROFILE_DRIFT", project_name)
    return {"status":"PASS", "file_count":len(manifest.get("files", []))}


def preflight_integrity(factory_root: Path, project_root: Path, project_name: str, profile: dict) -> dict:
    pipeline_file = project_root / ".agent/state/pipeline_status.json"
    if pipeline_file.exists():
        pipeline_data = _read_json(pipeline_file, {}) or {}
        if pipeline_data.get("terminal") and pipeline_data.get("status") == "STATE_DESYNC":
            raise IntegrityError("STATE_DESYNC_TERMINAL", "Task is in STATE_DESYNC terminal state")
    mode = profile.get("integrity_mode")
    if not mode:
        return {"status":"NOT_CONFIGURED"}
    if mode == "canonical":
        return verify_manifest(factory_root, factory_root / "runtime_manifest.json")
    if mode != "deployed": raise IntegrityError("PROFILE_DRIFT", f"Unknown integrity_mode: {mode}")
    # Local deployment layout: <target>/.agents/factory/<project>.
    if factory_root.name.lower() == "factory" and factory_root.parent.name.lower() == ".agents":
        return verify_deployed_bundle(factory_root.parent.parent, project_name)
    # Canonical development validates its own bundle and the managed projection.
    result = verify_manifest(factory_root, factory_root / "runtime_manifest.json")
    manifest = _read_json(factory_root / "runtime_manifest.json", {}) or {}
    expected = manifest.get("managed_profiles", {}).get(project_name)
    if expected is not None and managed_profile_projection(profile) != expected:
        raise IntegrityError("PROFILE_DRIFT", project_name)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("manifest", "verify", "merge-profile"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--target-profile")
    parser.add_argument("--canonical-profile")
    args = parser.parse_args()
    try:
        root = Path(args.root)
        if args.action == "manifest":
            result = build_manifest(root, Path(args.output or root / "runtime_manifest.json"))
        elif args.action == "verify":
            result = verify_manifest(root, Path(args.manifest or root / "runtime_manifest.json"))
        else:
            target_path = Path(args.target_profile)
            canonical = _read_json(Path(args.canonical_profile), {}) or {}
            merged = merge_managed_profile(_read_json(target_path, {}) or {}, canonical)
            _atomic_json(Path(args.output or target_path), merged)
            result = {"status": "PASS", "output": str(args.output or target_path)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except IntegrityError as exc:
        print(json.dumps({"status": "FAIL", "reason_code": exc.reason_code, "detail": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
