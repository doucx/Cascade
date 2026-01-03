import os
import libcst as cst
from libcst.codemod import VisitorBasedCodemodCommand, CodemodContext, transform_module

class RenameStructuralIdCommand(VisitorBasedCodemodCommand):
    DESCRIPTION = "Rename structural_id to current_node_instance_hash"

    def leave_Attribute(self, original_node, updated_node):
        if original_node.attr.value == "structural_id":
            return updated_node.with_changes(
                attr=updated_node.attr.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_AnnAssign(self, original_node, updated_node):
        if isinstance(original_node.target, cst.Name) and original_node.target.value == "structural_id":
             return updated_node.with_changes(
                target=updated_node.target.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_Arg(self, original_node, updated_node):
        if original_node.keyword and original_node.keyword.value == "structural_id":
            return updated_node.with_changes(
                keyword=updated_node.keyword.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_Param(self, original_node, updated_node):
        if original_node.name.value == "structural_id":
            return updated_node.with_changes(
                name=updated_node.name.with_changes(value="current_node_instance_hash")
            )
        return updated_node

def process_directory(root_dir):
    print(f"Starting refactoring in {root_dir}...")
    count = 0
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r") as f:
                    source = f.read()
                
                try:
                    transformer = RenameStructuralIdCommand(CodemodContext())
                    new_source = transform_module(transformer, source)
                    
                    if new_source != source:
                        print(f"Modifying {filepath}")
                        with open(filepath, "w") as f:
                            f.write(new_source)
                        count += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
    print(f"Refactoring complete. Modified {count} files.")

if __name__ == "__main__":
    process_directory("packages")