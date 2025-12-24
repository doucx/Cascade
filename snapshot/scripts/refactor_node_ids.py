import os
import re

root_dirs = ["packages", "tests"]
exclude_files = ["ast_analyzer.py"]

# Strict replacements for object attribute access
attr_replacements = [
    (r"\bnode\.id\b", "node.structural_id"),
    (r"\btarget\.id\b", "target.structural_id"),
    (r"\bsource\.id\b", "source.structural_id"),
    (r"\bselector_node\.id\b", "selector_node.structural_id"),
    (r"\bconstraint_node\.id\b", "constraint_node.structural_id"),
    (r"\bneighbor_node\.id\b", "neighbor_node.structural_id"),
    (r"\bparent_node\.id\b", "parent_node.structural_id"),
    (r"\bbranch_root_node\.id\b", "branch_root_node.structural_id"),
    (r"\bselected_node\.id\b", "selected_node.structural_id"),
    (r"\btarget_node\.id\b", "target_node.structural_id"),
]

def process_file(filepath):
    filename = os.path.basename(filepath)
    if filename in exclude_files:
        return

    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content

    # 1. Special handling for model.py definition
    if filepath.endswith("cascade/graph/model.py"):
        # Replace the dataclass field definition
        content = re.sub(r"^    id: str", "    structural_id: str", content, flags=re.MULTILINE)
        # Replace usage in __hash__
        content = content.replace("return hash(self.id)", "return hash(self.structural_id)")
        # Replace usage in Graph.add_node
        content = content.replace("if node.id not in self._node_index:", "if node.structural_id not in self._node_index:")
        content = content.replace("self._node_index[node.id] = node", "self._node_index[node.structural_id] = node")
        content = content.replace("self._node_index.get(node_id)", "self._node_index.get(node_id)") # parameter name stays same

    # 2. Special handling for serialize.py
    if filepath.endswith("cascade/graph/serialize.py"):
        content = content.replace('"id": node.id', '"structural_id": node.structural_id')
        content = content.replace('data["id"]', 'data["structural_id"]')
        content = content.replace('id=data["id"]', 'id=data["structural_id"]')

    # 3. Special handling for build.py Node instantiation
    if filepath.endswith("cascade/graph/build.py"):
        content = content.replace("id=structural_hash,", "structural_id=structural_hash,")
        content = content.replace("id=potential_uuid,", "structural_id=potential_uuid,")

    # 4. Apply attribute replacements
    for pattern, repl in attr_replacements:
        content = re.sub(pattern, repl, content)

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