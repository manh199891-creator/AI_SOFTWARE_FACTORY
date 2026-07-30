import sys
import time
from pathlib import Path
from multiprocessing import Process
from workflow_governance import ReviewLifecycleGuard

def child_process(project_root_str, task_id, mode, proc_id):
    guard = ReviewLifecycleGuard(Path(project_root_str), task_id, mode)
    try:
        guard.acquire()
        print(f"Process {proc_id} acquired lease.")
        time.sleep(2)
        print(f"Process {proc_id} releasing lease.")
    except Exception as e:
        print(f"Process {proc_id} failed: {e}")
    finally:
        try:
            guard.release()
        except:
            pass

if __name__ == "__main__":
    project_root_str = r"E:\AI_SOFTWARE_FACTORY"
    task_id = "test_lease_task"
    mode = "test_mode"
    
    # Ensure state dir exists
    (Path(project_root_str) / ".agent" / "state").mkdir(parents=True, exist_ok=True)
    
    p1 = Process(target=child_process, args=(project_root_str, task_id, mode, 1))
    p2 = Process(target=child_process, args=(project_root_str, task_id, mode, 2))
    
    p1.start()
    time.sleep(0.1) # ensure p1 starts first
    p2.start()
    
    p1.join()
    p2.join()
    print("Test finished.")
