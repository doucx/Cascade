import os
import sys

import libcst as cst

# Configuration: Target mappings
# Key: Old Name
# Value: (Target Classes/Contexts, New Name, Attribute Variable Whitelist)
RENAME_MAP = {
    "structural_id": (
        {"Node", "TaskNode", "MapNode", "ParamNode"},
        "current_node_instance_hash",
        None,  # None means replace all occurrences globally (safe)
    ),
    "source_id": (
        {"EdgeIR"},
        "source_node_instance_hash",
        None,
    ),
    "target_id": (
        {"EdgeIR"},
        "target_node_instance_hash",
        None,
    ),
    "id": (
        {"NodeIR", "Instruction", "Call", "Return"},  # Be careful with 'id'
        "current_node_instance_hash",  # Only for NodeIR effectively
        [
            "node",
            "n",
            "node_ir",
            "ir_node",
        ],  # Whitelist for attribute access (e.g. node.id)
    ),
}

# Explicitly exclude certain calls or contexts if necessary
EXCLUDED_CALLS = {"uuid4", "id"}


class IdentifierRefactorTransformer(cst.CSTTransformer):
    def __init__(self):
        self.class_stack = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.class_stack.append(node.name.value)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self.class_stack.pop()
        return updated_node

    def leave_AnnAssign(
        self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
    ) -> cst.AnnAssign:
        """
        Handles class field definitions:
        class NodeIR:
            id: str  -> current_node_instance_hash: str
        """
        if not self.class_stack:
            return updated_node

        current_class = self.class_stack[-1]

        if isinstance(original_node.target, cst.Name):
            old_name = original_node.target.value
            if old_name in RENAME_MAP:
                target_classes, new_name, _ = RENAME_MAP[old_name]

                # Special handling for 'id': Only rename in NodeIR context, not Instruction/Call/Return which use 'id' differently potentially
                # Actually, Instruction.id is likely different (an instruction ID), not a node hash.
                # Let's be strict: Only NodeIR.id maps to current_node_instance_hash.
                if old_name == "id" and current_class != "NodeIR":
                    return updated_node

                if current_class in target_classes:
                    return updated_node.with_changes(target=cst.Name(new_name))

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """
        Handles constructor calls:
        NodeIR(id=...) -> NodeIR(current_node_instance_hash=...)
        """
        func_name = None
        if isinstance(original_node.func, cst.Name):
            func_name = original_node.func.value

        if not func_name:
            return updated_node

        new_args = []
        modified = False

        for arg in updated_node.args:
            if arg.keyword and isinstance(arg.keyword, cst.Name):
                kwd = arg.keyword.value
                if kwd in RENAME_MAP:
                    target_classes, new_name, _ = RENAME_MAP[kwd]

                    # Logic for matching class constructors
                    if func_name in target_classes:
                        # Special check for 'id' again
                        if kwd == "id" and func_name != "NodeIR":
                            new_args.append(arg)
                            continue

                        new_args.append(arg.with_changes(keyword=cst.Name(new_name)))
                        modified = True
                        continue

            new_args.append(arg)

        if modified:
            return updated_node.with_changes(args=new_args)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """
        Handles attribute access:
        node.structural_id -> node.current_node_instance_hash
        node.id -> node.current_node_instance_hash (heuristically)
        """
        attr_name = original_node.attr.value

        if attr_name in RENAME_MAP:
            _, new_name, whitelist = RENAME_MAP[attr_name]

            should_rename = False

            if whitelist is None:
                # Safe to replace globally (e.g. structural_id)
                should_rename = True
            else:
                # Heuristic check on the object being accessed
                if isinstance(original_node.value, cst.Name):
                    obj_name = original_node.value.value
                    # Check if obj_name contains any hint from whitelist
                    # Matches "node", "n" (exact), "node_ir"
                    if obj_name in whitelist or any(
                        hint in obj_name for hint in ["node", "ir_"]
                    ):
                        should_rename = True

            if should_rename:
                return updated_node.with_changes(attr=cst.Name(new_name))

        return updated_node

    def leave_SimpleString(
        self, original_node: cst.SimpleString, updated_node: cst.SimpleString
    ) -> cst.SimpleString:
        """
        Handles string literals, primarily for serialization keys and dict access.
        "structural_id" -> "current_node_instance_hash"
        """
        # Strip quotes
        raw_val = original_node.value
        quote = raw_val[0]
        content = raw_val[1:-1]

        if content in RENAME_MAP:
            # We NEVER automatically rename "id" string literals, too dangerous.
            if content == "id":
                return updated_node

            _, new_name, _ = RENAME_MAP[content]
            return updated_node.with_changes(value=f"{quote}{new_name}{quote}")

        return updated_node


def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    try:
        source_tree = cst.parse_module(source_code)
        transformer = IdentifierRefactorTransformer()
        modified_tree = source_tree.visit(transformer)

        new_code = modified_tree.code

        if new_code != source_code:
            print(f"Refactoring {file_path}...")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_code)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python refactor_identifiers.py <directory>")
        sys.exit(1)

    target_dir = sys.argv[1]
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                process_file(os.path.join(root, file))


if __name__ == "__main__":
    main()
