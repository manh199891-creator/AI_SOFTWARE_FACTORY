import re

def rewrite():
    content = open("review_pipeline.py", "r", encoding="utf-8").read()
    
    # Check if we already injected build_review_batches
    if "def build_review_batches" in content:
        print("Already injected")
        return
        
    scratch = open("scratch.py", "r", encoding="utf-8").read()
    # Extract functions from scratch.py (build_review_batches, build_codex_prompt_batch, run_codex_review_batch, aggregate_batch_results)
    import ast
    mod = ast.parse(scratch)
    funcs_code = []
    
    # We'll just read lines from scratch.py that belong to these functions
    lines = scratch.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("def build_review_batches"):
            start = i
            break
            
    funcs_text = "\n".join(lines[start:])
    
    # Now insert before run_codex_review
    idx = content.find("def run_codex_review(")
    if idx == -1:
        print("Could not find run_codex_review")
        return
        
    new_content = content[:idx] + funcs_text + "\n\n" + content[idx:]
    
    open("review_pipeline.py", "w", encoding="utf-8").write(new_content)
    print("Injected functions")

rewrite()
