import os
import re

root_dirs = ["packages", "tests"]

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content

    # 1. Fix Node constructor calls: Node(..., id="foo", ...) -> Node(..., structural_id="foo", ...)
    # Look for id= as a keyword argument in Node(...) calls.
    # Simple regex approach: replace `id=` with `structural_id=` if it looks like a kwarg inside a call context.
    # But `id=` is common. We target specific known patterns in tests.
    
    # Target: Node(id=...)
    content = re.sub(r'Node\(\s*id=', 'Node(structural_id=', content)
    
    # Target: Node(..., id=...) - handling multiline or comma separated
    # This is risky globally. Let's be specific to test files where Node is instantiated manually.
    if "tests/" in filepath:
        content = re.sub(r',\s*id=', ', structural_id=', content)
    
    # 2. Fix specific attribute access missed by previous script
    # Log showed: route_node.id
    content = re.sub(r'\broute_node\.id\b', 'route_node.structural_id', content)
    
    # Log showed: node.id in test files might use different variable names
    # Let's fix common test variable names
    test_var_names = ["n", "start_node", "end_node", "task_node", "root_node", "leaf_node"]
    for var in test_var_names:
        content = re.sub(rf'\b{var}\.id\b', f'{var}.structural_id', content)

    # 3. Fix flow.py specific error
    if filepath.endswith("cascade/runtime/flow.py"):
        content = content.replace("route_node.id", "route_node.structural_id")

    if content != original_content:
        print(f"Patching {filepath}")
        with open(filepath, 'w') as f:
            f.write(content)

for root_dir in root_dirs:
    if not os.path.exists(root_dir):
        continue
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                process_file(os.path.join(root, file))