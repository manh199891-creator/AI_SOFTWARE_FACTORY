# CODEX_REVIEW.md

## Review Metadata
- mode: plan
- review_tier: STANDARD
- run_id: 8aa5d7cb-5c15-489d-ac42-eb3592dfbe16
- task_id: incident_plan
- completed_at: 2026-07-22 17:35:48
- reviewed_diff_hash: 6194b50b16e60874cee0a24f13af3fa34710c1c0356f56eef03359a239f28236
- status: FAIL
- placeholder: false
- reason: Review found issues.
- exit_code: 0


## Findings
- **P1**: `file1.txt:10` - Bug found
  There is a severe bug here.

## Raw Output
### Stdout
```
{
  "VERDICT": "FAIL",
  "REVIEWED_RUN_ID": "8aa5d7cb-5c15-489d-ac42-eb3592dfbe16",
  "REVIEWED_SNAPSHOT_HASH": "6194b50b16e60874cee0a24f13af3fa34710c1c0356f56eef03359a239f28236",
  "REVIEWED_FILES": [
    "PLAN.md",
    "TECHNICAL_DESIGN.md",
    "ACCEPTANCE_CRITERIA.md"
  ],
  "FINDINGS": [
    {
      "severity": "P1",
      "file": "file1.txt",
      "line": 10,
      "title": "Bug found",
      "body": "There is a severe bug here."
    }
  ]
}

```
### Stderr
```

```
