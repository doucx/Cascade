import os
import re
import sys

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

TARGET_DIRS = ["packages", "tests", "scripts"]
SKIP_DIRS = [".git", "__pycache__", ".pytest_cache", "venv", "env", "node_modules", "dist", "build"]

# Replacements are processed in order. 
# Specific patterns must come before general ones.
REPLACEMENTS = [
    # --- 1. structural_id (Graph Node) -> current_node_instance_hash ---
    (r"\.structural_id\b", ".current_node_instance_hash"),
    (r"\bstructural_id=", "current_node_instance_hash="),
    
    # --- 2. source_id (EdgeIR) -> source_node_instance_hash ---
    # Avoid _source_id (used in MQTT connector)
    (r"(?<!_)\.source_id\b", ".source_node_instance_hash"),
    (r"\bsource_id=", "source_node_instance_hash="),

    # --- 3. target_id (EdgeIR) -> target_node_instance_hash ---
    (r"\.target_id\b", ".target_node_instance_hash"),
    (r"\btarget_id=", "target_node_instance_hash="),

    # --- 4. structure_hash (Blueprint) -> current_code_structure_hash ---
    # This is for Instruction/Call/MapCall fields
    (r"\.structure_hash\b", ".current_code_structure_hash"),
    (r"\bstructure_hash=", "current_code_structure_hash="),
    
    # Also handle string literals in dicts/fingerprints if they were short
    # But be careful not to replace "current_code_structure_hash" with "current_code_current_code_..."
    # We rely on the fact that the axiom already demands the long name in fingerprints.
    # However, existing tests might use "structure_hash" as a key in kwargs.
    
    # --- 5. NodeIR.id -> current_node_instance_hash ---
    # This is the most delicate one.
    
    # 5a. Definition in models.py
    (r"class NodeIR:\s+id: str", "class NodeIR:\n    current_node_instance_hash: str"),
    
    # 5b. Construction
    (r"NodeIR\(\s*id=", "NodeIR(current_node_instance_hash="),
    
    # 5c. Usage (Attribute access)
    # We strictly limit this to variables that look like nodes to avoid replacing 'constraint.id' or 'run.id'
    (r"\bnode\.id\b", "node.current_node_instance_hash"),
    (r"\bn\.id\b", "n.current_node_instance_hash"),
    (r"\bnode_ir\.id\b", "node_ir.current_node_instance_hash"),
    (r"\binput_node\.id\b", "input_node.current_node_instance_hash"),
    # Common in optimizer
    (r"in_degree\[node\.id\]", "in_degree[node.current_node_instance_hash]"),
    # Common in tests
    (r"graph\.nodes\[0\]\.id", "graph.nodes[0].current_node_instance_hash"),
    
    # --- 6. Cleanup of leftover variable names (Optional but good for consistency) ---
    # Renaming 'node_id' variable to 'node_hash' is safer but might be too noisy.
    # For now, we stick to FIELD names as mandated by the axiom.
]

def process_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"{YELLOW}Skipping binary/non-utf8 file: {file_path}{RESET}")
        return

    original_content = content
    modified = False

    for pattern, replacement in REPLACEMENTS:
        # Check if pattern exists before replacing to save time/regex ops
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True

    if modified:
        print(f"{GREEN}Patching: {file_path}{RESET}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

def main():
    root_dir = os.getcwd()
    print(f"Starting Great Renaming in {root_dir}...")
    
    for target in TARGET_DIRS:
        base_path = os.path.join(root_dir, target)
        if not os.path.exists(base_path):
            continue
            
        for root, dirs, files in os.walk(base_path):
            # Filter skip dirs in place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            for file in files:
                if file.endswith(".py"):
                    process_file(os.path.join(root, file))

    print(f"{GREEN}Refactoring complete.{RESET}")

if __name__ == "__main__":
    main()