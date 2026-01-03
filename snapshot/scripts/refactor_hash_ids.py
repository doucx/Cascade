import libcst as cst
import sys
import os
from typing import Dict, Set, Optional, Tuple, List

# ==============================================================================
# Refactoring Configuration
# ==============================================================================

# Configuration: Target mappings
# Key: Old Name
# Value: (
#   Target Classes/Contexts (Set or None for global),
#   New Name,
#   Attribute Variable Whitelist (for heuristic matching on attribute access)
# )
RENAME_MAP: Dict[str, Tuple[Optional[Set[str]], str, Optional[List[str]]]] = {
    "structural_id": (
        None,  # None means this rule applies globally
        "current_node_instance_hash",
        None,  # None means rename all attribute accesses
    ),
    # This rule is VERY specific to avoid renaming the wrong 'id'
    "id": (
        {"NodeIR"},  # Only apply to AnnAssign/Call inside NodeIR class
        "current_node_instance_hash",
        ["node_ir", "ir_node", "ir"],  # Heuristics for attribute access
    ),
}


class IdentifierRefactorTransformer(cst.CSTTransformer):
    """
    A LibCST transformer to safely refactor ambiguous identifiers based on RENAME_MAP.
    It handles:
    1. Class attribute definitions (AnnAssign).
    2. Constructor keyword arguments (Call).
    3. Attribute access (Attribute).
    4. String literals used as dict keys (SimpleString).
    """

    def __init__(self):
        super().__init__()
        self.class_stack: List[str] = []

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

                if target_classes is None or current_class in target_classes:
                    return updated_node.with_changes(target=cst.Name(new_name))

        return updated_node

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.BaseExpression:
        """
        Handles constructor calls:
        NodeIR(id=...) -> NodeIR(current_node_instance_hash=...)
        """
        func_name: Optional[str] = None
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

                    if target_classes is None or (
                        func_name in target_classes if target_classes else False
                    ):
                        new_args.append(arg.with_changes(keyword=cst.Name(new_name)))
                        modified = True
                        continue

            new_args.append(arg)

        if modified:
            return updated_node.with_changes(args=new_args)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """
        Handles attribute access:
        node.structural_id -> node.current_node_instance_hash
        node_ir.id -> node_ir.current_node_instance_hash (heuristically)
        """
        attr_name = original_node.attr.value

        if attr_name in RENAME_MAP:
            _, new_name, whitelist = RENAME_MAP[attr_name]

            should_rename = False
            if whitelist is None:
                # Safe to replace globally (e.g. structural_id)
                should_rename = True
            elif isinstance(original_node.value, cst.Name):
                # Heuristic check on the object being accessed
                obj_name = original_node.value.value
                if obj_name in whitelist:
                    should_rename = True

            if should_rename:
                return updated_node.with_changes(attr=cst.Name(new_name))

        return updated_node

    def leave_SimpleString(
        self, original_node: cst.SimpleString, updated_node: cst.SimpleString
    ) -> cst.BaseExpression:
        """
        Handles string literals, primarily for serialization keys and dict access.
        "structural_id" -> "current_node_instance_hash"
        """
        # Strip quotes to get the raw content
        raw_val = original_node.value
        quote = raw_val[0]
        content = raw_val[1:-1]

        if content in RENAME_MAP:
            # SAFETY: Never automatically rename "id" string literals, it's too ambiguous and dangerous.
            if content == "id":
                return updated_node

            _, new_name, _ = RENAME_MAP[content]
            return updated_node.with_changes(value=f"{quote}{new_name}{quote}")

        return updated_node


def process_file(file_path: str, dry_run: bool = False):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        source_tree = cst.parse_module(source_code)
        transformer = IdentifierRefactorTransformer()
        modified_tree = source_tree.visit(transformer)

        if modified_tree.code != source_code:
            print(f"Refactoring target found in: {file_path}")
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(modified_tree.code)
    except cst.ParserSyntaxError as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
    except Exception as e:
        print(
            f"An unexpected error occurred processing {file_path}: {e}", file=sys.stderr
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/refactor_hash_ids.py <directory> [--dry-run]")
        sys.exit(1)

    target_dir = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.isdir(target_dir):
        print(f"Error: '{target_dir}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning directory: {target_dir}")
    if dry_run:
        print("--- DRY RUN MODE ---")

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                process_file(os.path.join(root, file), dry_run=dry_run)

    print("Refactoring scan complete.")


if __name__ == "__main__":
    main()
