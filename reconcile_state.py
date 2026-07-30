import json
import os
import datetime

STATE_FILE = "RevitAddinSolution/.agent/state/pipeline_status.json"

def main():
    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found.")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    old_status = data.get("status", "UNKNOWN")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Append to history without altering existing records
    history = data.get("history", [])
    history.append({
        "from": old_status,
        "to": "STATE_DESYNC",
        "at": now,
        "reason_code": "PHASE_1_FORCED_DESYNC"
    })
    
    # Update top level fields
    data["status"] = "STATE_DESYNC"
    data["terminal"] = True
    data["updated_at"] = now
    
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully recorded STATE_DESYNC terminal state in {STATE_FILE}")

if __name__ == "__main__":
    main()
