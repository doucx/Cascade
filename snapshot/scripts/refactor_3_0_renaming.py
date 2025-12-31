import libcst as cst
from libcst import matchers as m
import os
import sys

# Configuration
TARGET_DIRS = ["packages/cascade-compiler", "packages/cascade-spec", "packages/cascade-graph"]

# Mapping for unambiguous fields
GLOBAL_MAP = {
    "structural_id": "current_node_instance_hash",
    "source_id": "source_node_instance_hash",
    "target_id": "target_node_instance_hash",
}

class CascadeRenamer(cst.CSTTransformer):
    """
    Handles renaming of Cascade architecture symbols.
    """
    def __init__(self):
        self.in_node_ir_class = False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        if node.name.value == "NodeIR":
            self.in_node_ir_class = True
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        if original_node.name.value == "NodeIR":
            self.in_node_ir_class = False
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.Name:
        """
        Renames references to the symbols in variable names (if any local vars use these names).
        Note: We define 'id' renaming in leave_AnnAssign/Attribute/Call, not here to avoid renaming built-in id().
        """
        if original_node.value in GLOBAL_MAP:
            return updated_node.with_changes(value=GLOBAL_MAP[original_node.value])
        return updated_node

    def leave_AnnAssign(self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign) -> cst.AnnAssign:
        """
        Handles field definitions in dataclasses/classes.
        e.g., structural_id: str -> current_node_instance_hash: str
        """
        if isinstance(original_node.target, cst.Name):
            name = original_node.target.value
            
            # Global replacements
            if name in GLOBAL_MAP:
                return updated_node.with_changes(
                    target=original_node.target.with_changes(value=GLOBAL_MAP[name])
                )
            
            # Context-sensitive 'id' replacement
            if name == "id" and self.in_node_ir_class:
                return updated_node.with_changes(
                    target=original_node.target.with_changes(value="current_node_instance_hash")
                )
                
        return updated_node

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.Attribute:
        """
        Handles attribute access.
        e.g., node.structural_id -> node.current_node_instance_hash
        """
        attr_name = original_node.attr.value
        
        # Global replacements
        if attr_name in GLOBAL_MAP:
            return updated_node.with_changes(
                attr=updated_node.attr.with_changes(value=GLOBAL_MAP[attr_name])
            )
            
        # Context-sensitive 'id' replacement
        # Heuristic: variable names that imply a Node object
        if attr_name == "id":
            owner = original_node.value
            if isinstance(owner, cst.Name):
                name = owner.value
                # Heuristic whitelist of variable names likely to be Node/NodeIR objects
                target_vars = {"node", "n", "node_ir", "source", "target", "source_node", "target_node", "nd"}
                if name in target_vars or "node" in name:
                    return updated_node.with_changes(
                        attr=updated_node.attr.with_changes(value="current_node_instance_hash")
                    )
        
        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        Handles keyword arguments in function/constructor calls.
        e.g., NodeIR(id=...) -> NodeIR(current_node_instance_hash=...)
        """
        new_args = []
        modified = False
        
        for arg in updated_node.args:
            if arg.keyword:
                kw_name = arg.keyword.value
                
                # Global replacements
                if kw_name in GLOBAL_MAP:
                    new_args.append(arg.with_changes(
                        keyword=arg.keyword.with_changes(value=GLOBAL_MAP[kw_name])
                    ))
                    modified = True
                    continue
                
                # Context-sensitive 'id' replacement
                if kw_name == "id":
                    # Check if function being called is NodeIR
                    is_node_ir = m.matches(updated_node.func, m.Name("NodeIR"))
                    # Also common in tests: _create_dummy_node_ir(id=...) -> No, that usually takes node_id positional
                    # But if we see NodeIR constructor, definitely rename.
                    if is_node_ir:
                        new_args.append(arg.with_changes(
                            keyword=arg.keyword.with_changes(value="current_node_instance_hash")
                        ))
                        modified = True
                        continue
                        
                new_args.append(arg)
            else:
                new_args.append(arg)
        
        if modified:
            return updated_node.with_changes(args=new_args)
        return updated_node


def process_file(path):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        cst_tree = cst.parse_module(source)
    except Exception as e:
        print(f"Failed to parse {path}: {e}")
        return

    transformer = CascadeRenamer()
    modified_tree = cst_tree.visit(transformer)

    if not modified_tree.deep_equals(cst_tree):
        print(f"Refactoring {path}...")
        with open(path, "w", encoding="utf-8") as f:
            f.write(modified_tree.code)

def main():
    print("Starting The Great Renaming (Phase 3.0)...")
    cwd = os.getcwd()
    
    for relative_dir in TARGET_DIRS:
        target_dir = os.path.join(cwd, relative_dir)
        if not os.path.exists(target_dir):
            print(f"Skipping {target_dir} (not found)")
            continue
            
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    process_file(full_path)
    
    print("Refactoring complete.")

if __name__ == "__main__":
    main()