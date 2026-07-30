import sys, os, time, json

def main():
    scenario = os.environ.get("FAKE_CODEX_SCENARIO", "PASS")
    
    if scenario == "TIMEOUT":
        time.sleep(10) # Enough for test timeouts
        print("Done")
        sys.exit(0)
        
    if scenario == "EMPTY":
        sys.exit(0)
        
    if scenario == "PASS_BUT_SOURCE_CHANGED":
        # Modify a file to invalidate snapshot
        live_repo = os.environ.get("FAKE_LIVE_REPO", ".")
        target_file = os.path.join(live_repo, "file1.txt")
        with open(target_file, "a") as f:
            f.write("Modified by Codex")
        scenario = "PASS" # Then continue as normal PASS
        
    if scenario == "INFRA_FAIL_BAD_JSON":
        print("This is not JSON at all. Something went wrong.")
        sys.exit(0)
        
    if scenario == "NON_ZERO_EXIT":
        print("Something crashed.")
        sys.exit(1)
        
    # Standard output contract
    # But wait, run_codex_review needs the actual hash and run_id to pass validation
    # Let's read stdin to extract the hash and run_id from the prompt if possible
    # For a fake test, we can just grab it by parsing the input prompt
    stdin_content = sys.stdin.read() if not sys.stdin.isatty() else ""
    
    run_id = "unknown"
    snapshot_hash = "unknown"
    reviewed_files = []
    
    in_included_files = False
    for line in stdin_content.splitlines():
        if line.startswith("Run ID:"):
            run_id = line.split(":", 1)[1].strip()
        elif line.startswith("Snapshot Hash:"):
            snapshot_hash = line.split(":", 1)[1].strip()
        elif line.startswith("## Included Files"):
            in_included_files = True
        elif in_included_files and line.startswith("## "):
            in_included_files = False
        elif in_included_files and line.startswith("- ") and line[2:].strip():
            reviewed_files.append(line[2:].strip())
            
    run_id_to_output = os.environ.get("FAKE_CODEX_RUN_ID", run_id)
    hash_to_output = os.environ.get("FAKE_CODEX_HASH", snapshot_hash)
    files_to_output = reviewed_files
    if scenario == "BAD_REVIEWED_FILES":
        files_to_output = ["wrong-file.txt"]
        scenario = "PASS"
        
    if scenario == "TIMEOUT_THEN_PASS":
        if len(reviewed_files) > 1:
            time.sleep(10) # timeout
            sys.exit(0)
        else:
            scenario = "PASS"

    if scenario == "TIMEOUT_SINGLE_FILE":
        if len(reviewed_files) == 1:
            time.sleep(10) # timeout
            sys.exit(0)
        else:
            scenario = "PASS"
    
    if scenario == "PASS":
        out = {
            "VERDICT": "PASS",
            "REVIEWED_RUN_ID": run_id_to_output,
            "REVIEWED_SNAPSHOT_HASH": hash_to_output,
            "REVIEWED_FILES": files_to_output,
            "FINDINGS": []
        }
        print(json.dumps(out, indent=2))
        sys.exit(0)
        
    if scenario == "FAIL":
        out = {
            "VERDICT": "FAIL",
            "REVIEWED_RUN_ID": run_id_to_output,
            "REVIEWED_SNAPSHOT_HASH": hash_to_output,
            "REVIEWED_FILES": files_to_output,
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
        print(json.dumps(out, indent=2))
        sys.exit(0)
        
    print(f"Unknown scenario {scenario}")
    sys.exit(1)

if __name__ == "__main__":
    main()