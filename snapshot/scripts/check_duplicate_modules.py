#!/usr/bin/env python3
import sys
from collections import defaultdict
from pathlib import Path

def find_duplicate_modules(root_dir="."):
    """
    Scans the 'packages' directory to find modules defined in multiple packages.
    """
    packages_dir = Path(root_dir) / "packages"
    if not packages_dir.is_dir():
        print(f"Error: Directory not found: {packages_dir}", file=sys.stderr)
        return 1

    module_map = defaultdict(list)
    package_dirs = [d for d in packages_dir.iterdir() if d.is_dir()]

    for package_path in package_dirs:
        package_name = package_path.name
        src_path = package_path / "src"

        if not src_path.is_dir():
            continue

        for path in src_path.rglob("*"):
            module_parts = []
            
            # Case 1: It's a package directory (contains __init__.py)
            if path.is_file() and path.name == "__init__.py":
                module_parts = path.parent.relative_to(src_path).parts
            
            # Case 2: It's a module file (.py)
            elif path.is_file() and path.suffix == ".py":
                # Exclude __init__.py files as they are handled by their parent dir
                if path.stem == "__init__":
                    continue
                
                module_parts_with_stem = list(path.relative_to(src_path).parts)
                module_parts_with_stem[-1] = path.stem # remove .py extension
                module_parts = module_parts_with_stem
            
            if module_parts:
                # Handle the case where the src dir itself is a module root (e.g., src/cascade)
                module_name = ".".join(module_parts)
                module_map[module_name].append(package_name)

    duplicates = {
        module: sorted(packages)
        for module, packages in module_map.items()
        if len(packages) > 1
    }

    if duplicates:
        print("❌ Found duplicate module definitions:", file=sys.stderr)
        print("-------------------------------------", file=sys.stderr)
        sorted_duplicates = sorted(duplicates.items())
        for module, packages in sorted_duplicates:
            print(f"- Module: {module}", file=sys.stderr)
            print(f"  Defined in: {', '.join(packages)}\n", file=sys.stderr)
        return 1
    else:
        print("✅ No duplicate module definitions found.")
        return 0

if __name__ == "__main__":
    # Assuming the script is run from the repository root
    repo_root = Path(__file__).parent.parent.resolve()
    sys.exit(find_duplicate_modules(repo_root))