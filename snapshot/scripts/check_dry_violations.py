#!/usr/bin/env python3
import ast
import sys
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple, Set, Any

# 配置：忽略的常见名称，不参与命名重复检查
IGNORE_NAMES = {
    "__init__", "__str__", "__repr__", "__call__", "__hash__", "__eq__",
    "__enter__", "__exit__", "__getattr__", "__setattr__", "run", "main",
    "setup", "teardown", "validate", "process", "handler"
}

# 配置：忽略极短的代码块（行数阈值），防止误报空函数
MIN_CODE_LINES = 3

class ASTCleaner(ast.NodeTransformer):
    """
    Cleans the AST for comparison:
    1. Removes docstrings.
    2. (Implicitly via ast.dump) Removes line numbers and col offsets.
    """
    def visit_FunctionDef(self, node):
        self._remove_docstring(node)
        return self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._remove_docstring(node)
        return self.generic_visit(node)

    def _remove_docstring(self, node):
        """Remove docstring if it exists as the first statement."""
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            node.body.pop(0)

def get_ast_hash(node: ast.AST) -> str:
    """
    Computes a hash of the AST node structure, ignoring formatting and positions.
    """
    # include_attributes=False ignores lineno and col_offset (Python 3.9+)
    # We strip annotations to focus on logic, not types (optional, strictness choice)
    # For now, we KEEP types because type hints are part of the 'definition'.
    dump = ast.dump(node, include_attributes=False)
    return hashlib.sha256(dump.encode("utf-8")).hexdigest()

def get_loc(node: ast.AST) -> int:
    """Estimate lines of code for the node."""
    # This is rough because we removed attributes, but useful for thresholding
    # We can't use node.lineno because we might have modified the tree.
    # Just counting the complexity of the dump is a decent proxy, 
    # but strictly we assume simple definitions aren't duplicates worth fixing.
    return len(node.body) if hasattr(node, "body") else 0

def analyze_codebase(root_dir: Path):
    packages_dir = root_dir / "packages"
    
    # Storage for Stage 1: AST Duplication
    # Hash -> List[(name, filepath, lineno)]
    ast_hashes: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)
    
    # Storage for Stage 2: Name Duplication
    # Name -> List[filepath]
    symbol_table: Dict[str, Set[str]] = defaultdict(set)

    print(f"🔍 Scanning {packages_dir} ...")

    for py_file in packages_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
            
            tree = ast.parse(source, filename=str(py_file))
            cleaner = ASTCleaner()
            
            # We iterate top-level definitions and nested ones
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    # --- Stage 2: Name Collection ---
                    name = node.name
                    if name not in IGNORE_NAMES and not name.startswith("_"):
                        symbol_table[name].add(str(py_file.relative_to(root_dir)))

                    # --- Stage 1: AST Hash Collection ---
                    # Filter out tiny functions (empty or just pass)
                    if get_loc(node) < MIN_CODE_LINES:
                        continue
                    
                    # Create a detached copy/cleaned version for hashing
                    # We simply clear the docstring in place since we are just reading
                    # But since ast.walk yields references, modifying them affects the tree.
                    # That's fine as we don't write back.
                    cleaner.visit(node)
                    
                    node_hash = get_ast_hash(node)
                    ast_hashes[node_hash].append((name, str(py_file.relative_to(root_dir)), getattr(node, 'lineno', 0)))
                    
        except SyntaxError:
            pass # Ignore unparseable files
        except Exception as e:
            print(f"Warning: Failed to parse {py_file}: {e}", file=sys.stderr)

    return ast_hashes, symbol_table

def report(ast_hashes, symbol_table):
    exit_code = 0
    
    print("\n" + "="*60)
    print("STAGE 1: AST Logic Duplication (Strict Copy-Paste)")
    print("="*60)
    
    duplicate_groups = [v for k, v in ast_hashes.items() if len(v) > 1]
    # Sort by number of duplicates * size of group
    duplicate_groups.sort(key=lambda x: len(x), reverse=True)
    
    found_ast_dupes = False
    for group in duplicate_groups:
        # Check if they are all in the same file (sometimes ok, but still smelly)
        files = {item[1] for item in group}
        names = {item[0] for item in group}
        
        # If it's just the same function name in the same file multiple times, 
        # that's usually impossible in valid python (redefinition), 
        # or it's method overrides in nested scopes.
        
        print(f"\n🔴 Found {len(group)} indentical implementations:")
        print(f"   Names involved: {', '.join(names)}")
        for name, path, lineno in group:
            print(f"   - {path}:{lineno} ({name})")
        found_ast_dupes = True
        exit_code = 1

    if not found_ast_dupes:
        print("✅ No AST logic duplicates found.")

    print("\n" + "="*60)
    print("STAGE 2: Naming Collisions (Potential Conceptual Confusion)")
    print("="*60)
    
    found_name_dupes = False
    # Sort by number of files defining it
    sorted_symbols = sorted(symbol_table.items(), key=lambda x: len(x[1]), reverse=True)
    
    for name, paths in sorted_symbols:
        if len(paths) > 1:
            # Heuristic: If it appears in > 5 files, it might be a generic name like 'Context' or 'Result'
            # We still report it but maybe mark it as 'Generic'
            tag = " [Generic?]" if len(paths) > 5 else ""
            print(f"\n🟡 Symbol '{name}' defined in {len(paths)} files{tag}:")
            for p in sorted(list(paths)):
                print(f"   - {p}")
            found_name_dupes = True
            # We don't fail the build for naming collisions yet, just warn
            # exit_code = 1 
            
    if not found_name_dupes:
        print("✅ No naming collisions found.")

    return exit_code

if __name__ == "__main__":
    root = Path(__file__).parent.parent.resolve()
    hashes, symbols = analyze_codebase(root)
    sys.exit(report(hashes, symbols))