import re

def rewrite():
    content = open("review_pipeline.py", "r", encoding="utf-8").read()
    
    start_str = "    # 5. Build Prompt"
    end_str = "    # Update canonical pointer"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)
    
    if start_idx == -1 or end_idx == -1:
        print("Could not find boundaries")
        return
        
    new_body = """    # 5. Build and Execute Batches
    config = get_review_config(project_root)
    batches = build_review_batches(repo_root, changed_files, config)
    
    manifest["batches"] = batches
    manifest["status"] = ReviewStatus.RUNNING
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    for batch in batches:
        run_codex_review_batch(batch, manifest, project_root, repo_root, config)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        
    # 7. Aggregate and Parse Result
    status, findings = aggregate_batch_results(batches)
    reason = ""
    
    # 7.5 Check post-run snapshot
    if status == ReviewStatus.PASS:
        try:
            post_hash, _ = get_deterministic_snapshot(repo_root)
            if post_hash != snapshot_hash:
                status = ReviewStatus.STALE
                reason = "Source code changed during review."
        except Exception as e:
            status = ReviewStatus.INFRA_FAIL
            reason = f"Failed to get post-run snapshot: {e}"
            
    if not reason:
        if status == ReviewStatus.PASS:
            reason = "All batches passed."
        elif status == ReviewStatus.FAIL:
            reason = "One or more batches failed review."
        elif status == ReviewStatus.INFRA_FAIL:
            reason = "Infrastructure failure in one or more batches."
    
    # 8. Write Report
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_md = f\"\"\"# CODEX_REVIEW.md

## Review Metadata
- mode: real_review_batched
- run_id: {run_id}
- task_id: {task_id}
- completed_at: {ts_now}
- reviewed_diff_hash: {snapshot_hash}
- status: {status}
- placeholder: false
- reason: {reason}
\"\"\"
    if manifest.get('reason_code'):
        report_md += f"- reason_code: {manifest.get('reason_code')}\\n"

    report_md += f\"\"\"
## Findings
\"\"\"
    if not findings:
        report_md += "No findings.\\n"
    else:
        for f in findings:
            report_md += f"- **{f.get('severity', 'UNKNOWN')}**: `{f.get('file', '?')}:{f.get('line', '?')}` - {f.get('title', '?')}\\n  {f.get('body', '')}\\n"

    report_md += f\"\"\"
## Raw Output
\"\"\"
    for b in batches:
        report_md += f"### Batch {b['batch_id']}\\n"
        report_md += f"#### Stdout\\n```\\n{b.get('stdout', '')}\\n```\\n"
        report_md += f"#### Stderr\\n```\\n{b.get('stderr', '')}\\n```\\n"
        
    report_file = reviews_dir / f"{run_id}.md"
    report_file.write_text(report_md, encoding="utf-8")
    
"""
    new_content = content[:start_idx] + new_body + content[end_idx:]
    
    open("review_pipeline.py", "w", encoding="utf-8").write(new_content)
    print("Injected run body")

rewrite()
