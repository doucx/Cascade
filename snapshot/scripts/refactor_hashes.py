import os
import re

# Color codes for output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

TARGET_DIRS = ["packages", "tests"]
SKIP_DIRS = [".git", "__pycache__", ".pytest_cache", "venv", "env", "node_modules", "dist", "build"]

# Replacements are processed in order.
REPLACEMENTS = [
    # --- 1. structural_id (Graph Node) -> current_node_instance_hash ---
    # Definition: structural_id: str
    (r"\bstructural_id\s*:\s*str", "current_node_instance_hash: str"),
    # Attribute access: .structural_id
    (r"\.structural_id\b", ".current_node_instance_hash"),
    # Keyword arg: structural_id=
    (r"\bstructural_id\s*=", "current_node_instance_hash="),
    
    # --- 2. source_id (EdgeIR) -> source_node_instance_hash ---
    # Definition
    (r"\bsource_id\s*:\s*str", "source_node_instance_hash: str"),
    # Attribute
    (r"(?<!_)\.source_id\b", ".source_node_instance_hash"),
    # Kwarg
    (r"\bsource_id\s*=", "source_node_instance_hash="),

    # --- 3. target_id (EdgeIR) -> target_node_instance_hash ---
    # Definition
    (r"\btarget_id\s*:\s*str", "target_node_instance_hash: str"),
    # Attribute
    (r"\.target_id\b", ".target_node_instance_hash"),
    # Kwarg
    (r"\btarget_id\s*=", "target_node_instance_hash="),

    # --- 4. structure_hash (Blueprint) -> current_code_structure_hash ---
    # Definition (often Optional[str])
    (r"\bstructure_hash\s*:\s*", "current_code_structure_hash: "),
    # Attribute
    (r"\.structure_hash\b", ".current_code_structure_hash"),
    # Kwarg
    (r"\bstructure_hash\s*=", "current_code_structure_hash="),
    
    # --- 5. NodeIR.id -> current_node_instance_hash ---
    # WARNING: 'id' is very common. We must be context-specific.
    
    # 5a. Definition in models.py (handled by specific pattern)
    (r"class NodeIR:.*?id:\s*str", "class NodeIR:\n    current_node_instance_hash: str"),
    
    # 5b. Construction: NodeIR(..., id=..., ...)
    # We match 'NodeIR' followed by any characters (non-greedy) until 'id='
    # This covers multiline calls.
    (r"(NodeIR\s*\([^)]*?)\bid\s*=", r"\1current_node_instance_hash="),
    
    # 5c. Usage (Attribute access) - Context aware
    (r"\bnode\.id\b", "node.current_node_instance_hash"),
    (r"\bn\.id\b", "n.current_node_instance_hash"),
    (r"\bnode_ir\.id\b", "node_ir.current_node_instance_hash"),
    (r"\binput_node\.id\b", "input_node.current_node_instance_hash"),
    (r"in_degree\[node\.id\]", "in_degree[node.current_node_instance_hash]"),
    (r"graph\.nodes\[0\]\.id", "graph.nodes[0].current_node_instance_hash"),
    (r"restored_node\.id\b", "restored_node.current_node_instance_hash"),
    
    # 5d. Test assertions and assignments
    (r"assert node\.id ==", "assert node.current_node_instance_hash =="),
    (r"assert graph\.nodes\[\d+\]\.id ==", "assert graph.nodes[0].current_node_instance_hash =="),
    
    # --- 6. EdgeIR Construction in Tests ---
    # EdgeIR(source_id="A", ...)
    # Handled by generic source_id replacement above? Yes.
]

def process_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return

    original_content = content
    modified = False

    # Pre-compiled NodeIR multiline fix for re.DOTALL support
    # This is specifically to fix: NodeIR(\n    id=...
    # We repeat this until no changes to catch multiple args if necessary, 
    # though usually id is just one arg.
    # Note: Regex in loop is simple string replace, this one needs special flags.
    
    node_ir_pattern = re.compile(r"(NodeIR\s*\([^)]*?)\bid\s*=", re.DOTALL)
    if node_ir_pattern.search(content):
        new_content = node_ir_pattern.sub(r"\1current_node_instance_hash=", content)
        if new_content != content:
            content = new_content
            modified = True

    # Run standard replacements
    for pattern, replacement in REPLACEMENTS:
        # We assume most patterns don't need DOTALL, except the manual one above.
        # But `class NodeIR:.*?id:` might need DOTALL if it spans lines (unlikely for definition).
        flags = 0
        if "class NodeIR" in pattern:
            flags = re.DOTALL
            
        if re.search(pattern, content, flags=flags):
            new_content = re.sub(pattern, replacement, content, flags=flags)
            if new_content != content:
                content = new_content
                modified = True

    if modified:
        print(f"{GREEN}Patching: {file_path}{RESET}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

def main():
    root_dir = os.getcwd()
    print(f"Starting Great Renaming Fix in {root_dir}...")
    
    for target in TARGET_DIRS:
        base_path = os.path.join(root_dir, target)
        if not os.path.exists(base_path):
            continue
            
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if file.endswith(".py"):
                    process_file(os.path.join(root, file))

    print(f"{GREEN}Refactoring complete.{RESET}")

if __name__ == "__main__":
    main()