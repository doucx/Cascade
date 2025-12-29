#!/usr/bin/env python3
import sys
import re
from collections import defaultdict
from pathlib import Path

# Standard namespace package declaration patterns
NAMESPACE_PATTERNS = [
    re.compile(r"^__path__\s*=\s*__import__\(['\"]pkgutil['\"]\)\.extend_path\(__path__,\s*__name__\)\s*$"),
    re.compile(r"^__import__\(['\"]pkg_resources['\"]\)\.declare_namespace\(__name__\)\s*$"),
]

def is_namespace_package_boilerplate(file_path):
    """
    Checks if an __init__.py file contains only namespace declaration boilerplate,
    comments, or whitespace.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        # If we can't read it, assume it's substantive (better safe than sorry)
        return False

    has_code = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        
        # If we find a line of code, check if it matches known boilerplate
        matched = False
        for pattern in NAMESPACE_PATTERNS:
            if pattern.match(stripped):
                matched = True
                break
        
        if not matched:
            # Found a line of code that isn't boilerplate
            return False
            
    # If we get here, all code lines were boilerplate (or there were no code lines)
    return True

def find_duplicate_modules(root_dir="."):
    """
    Scans the 'packages' directory to find modules defined in multiple packages.
    Distinguishes between strict file conflicts and namespace package merges.
    """
    packages_dir = Path(root_dir) / "packages"
    if not packages_dir.is_dir():
        print(f"Error: Directory not found: {packages_dir}", file=sys.stderr)
        return 1

    # Map of module_name -> list of (package_name, is_substantive)
    definitions = defaultdict(list)
    package_dirs = [d for d in packages_dir.iterdir() if d.is_dir()]

    for package_path in package_dirs:
        package_name = package_path.name
        src_path = package_path / "src"

        if not src_path.is_dir():
            continue

        for path in src_path.rglob("*"):
            module_name = None
            is_substantive = True

            # Case 1: It's a package directory (contains __init__.py)
            if path.is_file() and path.name == "__init__.py":
                module_parts = path.parent.relative_to(src_path).parts
                module_name = ".".join(module_parts)
                # Check if it's just a namespace placeholder
                if is_namespace_package_boilerplate(path):
                    is_substantive = False
            
            # Case 2: It's a module file (.py)
            elif path.is_file() and path.suffix == ".py":
                # Exclude __init__.py files as they are handled above
                if path.stem == "__init__":
                    continue
                
                module_parts = list(path.relative_to(src_path).parts)
                module_parts[-1] = path.stem # remove .py extension
                module_name = ".".join(module_parts)
                # Regular .py files are always substantive definitions
                is_substantive = True
            
            if module_name:
                definitions[module_name].append({
                    "package": package_name,
                    "is_substantive": is_substantive,
                    "path": str(path)
                })

    conflicts = {}

    for module, defs in definitions.items():
        # Filter for substantive definitions (those containing actual code)
        substantive_defs = [d for d in defs if d["is_substantive"]]
        
        # Conflict Condition 1: Multiple packages define substantive logic for the same module/package
        if len(substantive_defs) > 1:
            conflicts[module] = {
                "reason": "Multiple substantive definitions (logic collision)",
                "sources": [f"{d['package']} ({'substantive' if d['is_substantive'] else 'namespace'})" for d in defs]
            }
        # Conflict Condition 2: Regular module file (.py) vs Package dir (__init__.py)
        # This is implicitly handled because one would be 'foo' and the other 'foo'
        # But we need to make sure we don't have a file 'foo.py' and a dir 'foo/' both substantive.
        # (The script logic above maps them to the same dotted name, so len > 1 catches this too)

    if conflicts:
        print("❌ Found duplicate module definitions:", file=sys.stderr)
        print("-------------------------------------", file=sys.stderr)
        sorted_conflicts = sorted(conflicts.items())
        for module, info in sorted_conflicts:
            print(f"- Module: {module}", file=sys.stderr)
            print(f"  Reason: {info['reason']}", file=sys.stderr)
            print(f"  Defined in:", file=sys.stderr)
            for src in info['sources']:
                print(f"    * {src}", file=sys.stderr)
            print("", file=sys.stderr)
        return 1
    else:
        print("✅ No duplicate module definitions found.")
        return 0

if __name__ == "__main__":
    # Assuming the script is run from the repository root
    repo_root = Path(__file__).parent.parent.resolve()
    sys.exit(find_duplicate_modules(repo_root))