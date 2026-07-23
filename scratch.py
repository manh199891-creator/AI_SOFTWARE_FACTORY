import sys, os
from pathlib import Path
from review_pipeline import *
import json
import shutil
import tempfile
import subprocess
from datetime import datetime
import time

def build_review_batches(repo_root, included_files, config):
    batch_max_files = config.get("batch_max_files", 3)
    batch_max_chars = config.get("batch_max_chars", 70000)
    batches = []
    
    current_batch_files = []
    current_batch_chars = 0
    batch_id = 1
    
    for f in included_files:
        diff_str, _, file_truncated = collect_review_diff(repo_root, [f], max_diff_chars=batch_max_chars, max_file_chars=config.get("max_file_chars", 40000))
        f_len = len(diff_str)
        
        if f_len >= batch_max_chars:
            if current_batch_files:
                batches.append({
                    "batch_id": batch_id,
                    "files": current_batch_files,
                    "evidence_chars": current_batch_chars,
                    "status": "QUEUED",
                    "reason": "",
                    "run_id": None,
                    "duration_seconds": 0
                })
                batch_id += 1
                current_batch_files = []
                current_batch_chars = 0
            
            batches.append({
                "batch_id": batch_id,
                "files": [f],
                "evidence_chars": f_len,
                "status": "QUEUED",
                "reason": "",
                "run_id": None,
                "duration_seconds": 0,
                "needs_chunk_review": True
            })
            batch_id += 1
            continue
            
        if len(current_batch_files) >= batch_max_files or current_batch_chars + f_len > batch_max_chars:
            batches.append({
                "batch_id": batch_id,
                "files": current_batch_files,
                "evidence_chars": current_batch_chars,
                "status": "QUEUED",
                "reason": "",
                "run_id": None,
                "duration_seconds": 0
            })
            batch_id += 1
            current_batch_files = [f]
            current_batch_chars = f_len
        else:
            current_batch_files.append(f)
            current_batch_chars += f_len
            
    if current_batch_files:
        batches.append({
            "batch_id": batch_id,
            "files": current_batch_files,
            "evidence_chars": current_batch_chars,
            "status": "QUEUED",
            "reason": "",
            "run_id": None,
            "duration_seconds": 0
        })
        
    return batches

def build_codex_prompt_batch(manifest, project_root, config, batch_files):
    # Same as build_codex_prompt but uses batch_files for Included Files list and evidence gathering
    reviewed_files_json = json.dumps(batch_files, ensure_ascii=False)
    prompt = f"""
You are the Codex Reviewer. You must review the provided code changes strictly according to the plan and acceptance criteria.
DO NOT review files outside the Included Files list.

## Context
Run ID: {manifest['run_id']}
Task ID: {manifest['task_id']}
Feature Name: {manifest['feature_name']}
Snapshot Hash: {manifest['snapshot_hash']}

## Included Files (Only review these!)
"""
    for f in batch_files:
        prompt += f"- {f}\n"

    # Load context files
    for context_file in manifest['plan_files'] + manifest['acceptance_files']:
        fpath = project_root / context_file
        if fpath.exists():
            content = fpath.read_text(encoding='utf-8', errors='replace')
            prompt += f"\n## File: {context_file}\n```\n{content}\n```\n"

    repo_root = Path(manifest["repository_root"])
    prompt += "\n## Changed File Evidence\n"
    diff_str, is_truncated, file_truncated = collect_review_diff(
        repo_root, 
        batch_files, 
        max_diff_chars=config.get("max_diff_chars", 120000),
        max_file_chars=config.get("max_file_chars", 40000)
    )
    prompt += diff_str
    prompt += "\n"
    
    # We update manifest for truncation info
    # In batch mode, if any batch truncates, the manifest should mark it.
    if is_truncated or file_truncated:
        manifest["evidence_truncated"] = True
    if file_truncated:
        manifest["file_truncated"] = True
        
    if is_truncated or file_truncated:
        manifest["evidence_snippet"] = diff_str[-200:]

    # Strictly require Output Contract
    prompt += f"""
## Output Contract
You MUST output your review strictly in the following JSON format. Do not include markdown code blocks around the JSON if it breaks parsing.
{{
  "VERDICT": "PASS" | "FAIL",
  "REVIEWED_RUN_ID": "run_id_here",
  "REVIEWED_SNAPSHOT_HASH": "snapshot_hash_here",
  "REVIEWED_FILES": {reviewed_files_json},
  "FINDINGS": [
    {{
      "severity": "P0/P1/P2/P3",
      "file": "path/to/file",
      "line": 123,
      "title": "Short title",
      "body": "Detailed description"
    }}
  ]
}}
"""
    return prompt

def run_codex_review_batch(batch, manifest, project_root, repo_root, config):
    batch_id = batch["batch_id"]
    batch_files = batch["files"]
    prompt = build_codex_prompt_batch(manifest, project_root, config, batch_files)
    
    temp_review_dir = Path(tempfile.mkdtemp(prefix=f"codex_review_{manifest['run_id']}_b{batch_id}_"))
    review_cwd = temp_review_dir / "source-code"
    shutil.copytree(repo_root, review_cwd)
    
    # Run Codex
    codex_executable = "codex"
    if os.name == 'nt' and not codex_executable.endswith(".cmd") and not codex_executable.endswith(".exe"):
        codex_executable = "codex.cmd"
    if "CODEX_EXECUTABLE" in os.environ:
        codex_executable = os.environ["CODEX_EXECUTABLE"]
        
    last_message_path = temp_review_dir / "codex_last_message.txt"
    start_time = time.time()
    
    try:
        proc = subprocess.Popen(
            [
                codex_executable,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "--output-last-message",
                str(last_message_path),
                "-",
            ],
            cwd=review_cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        timeout = int(config.get("timeout_seconds", 180))
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
        exit_code = proc.returncode
        if last_message_path.exists():
            last_message = last_message_path.read_text(encoding="utf-8", errors="replace").strip()
            if last_message:
                stdout = last_message
                
        # Parse result
        status, reason, findings = parse_codex_result(stdout, stderr, exit_code, manifest['run_id'], manifest['snapshot_hash'], batch_files)
        
        batch["status"] = status
        batch["reason"] = reason
        batch["findings"] = findings
        batch["stdout"] = stdout
        batch["stderr"] = stderr
        batch["exit_code"] = exit_code
        batch["duration_seconds"] = int(time.time() - start_time)
        batch["run_id"] = f"{manifest['run_id']}_b{batch_id}"
        
        return batch
        
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        stdout, stderr = proc.communicate()
        exit_code = -1
        
        batch["status"] = ReviewStatus.INFRA_FAIL
        batch["reason"] = f"Timeout ({timeout}s)"
        batch["reason_code"] = "CODEX_TIMEOUT"
        batch["findings"] = []
        batch["stdout"] = stdout
        batch["stderr"] = stderr
        batch["exit_code"] = exit_code
        batch["duration_seconds"] = int(time.time() - start_time)
        return batch
        
    except Exception as e:
        batch["status"] = ReviewStatus.INFRA_FAIL
        batch["reason"] = f"Exception: {e}"
        batch["findings"] = []
        batch["stdout"] = ""
        batch["stderr"] = ""
        batch["exit_code"] = -1
        batch["duration_seconds"] = int(time.time() - start_time)
        return batch
        
    finally:
        _cleanup_dir(temp_review_dir)

def aggregate_batch_results(batches):
    final_status = ReviewStatus.PASS
    all_findings = []
    
    # Status Priority: INFRA_FAIL > STALE > FAIL > PASS
    # Note: parse_codex_result handles STALE_SOURCE_CHANGED which returns STALE
    has_infra_fail = False
    has_stale = False
    has_fail = False
    
    for b in batches:
        st = b.get("status")
        if st == ReviewStatus.INFRA_FAIL:
            has_infra_fail = True
        elif st == ReviewStatus.STALE:
            has_stale = True
        elif st == ReviewStatus.FAIL:
            has_fail = True
            
        all_findings.extend(b.get("findings", []))
        
    if has_infra_fail:
        final_status = ReviewStatus.INFRA_FAIL
    elif has_stale:
        final_status = ReviewStatus.STALE
    elif has_fail:
        final_status = ReviewStatus.FAIL
        
    return final_status, all_findings
