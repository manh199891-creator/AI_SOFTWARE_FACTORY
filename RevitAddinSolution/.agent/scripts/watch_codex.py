"""
watch_codex.py — Watchdog script cho Codex CLI Review
Kiểm tra mỗi 5 phút. Tự kill và retry nếu bị treo > 20 phút.
"""
import subprocess
import time
import json
from pathlib import Path

CHECK_INTERVAL = 300   # 5 phút
MAX_REVIEW_TIME = 1200  # 20 phút
MAX_RETRY = 2

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / ".agent" / "reports" / "CODEX_REVIEW.md"
STATE  = ROOT / ".agent" / "state" / "workflow_state.json"
LOG    = ROOT / ".agent" / "logs" / "watchdog.log"


def log(message: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")
    print(message)


def update_state(codex_status: str):
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
        state["codex_status"] = codex_status
        STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def run_codex_review():
    return subprocess.Popen(
        ["codex", "/review"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )


def main():
    retry = 0
    log("=== Codex Watchdog started ===")

    while retry <= MAX_RETRY:
        log(f"Starting Codex review. Attempt {retry + 1}/{MAX_RETRY + 1}")
        update_state("running")
        process = run_codex_review()
        start = time.time()

        while True:
            time.sleep(CHECK_INTERVAL)

            if process.poll() is not None:
                log("Codex review completed.")
                update_state("completed")
                return

            elapsed = time.time() - start
            log(f"Still running... elapsed={int(elapsed)}s")

            if elapsed > MAX_REVIEW_TIME:
                log("TIMEOUT — Killing Codex process.")
                process.kill()
                retry += 1
                break

    # Hết retry
    REPORT.write_text(
        "# CODEX_REVIEW.md\n\n## Status\n\nTIMEOUT\n\n## Summary\n\nCodex review vượt quá số lần retry tối đa.\n",
        encoding="utf-8"
    )
    update_state("timeout")
    log("Codex review FAILED after max retries. Human review required.")


if __name__ == "__main__":
    main()
