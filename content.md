You've hit on a crucial and subtle point. My previous `[COMMIT]` plan was premature. The `stitcher refactor apply` command did its job *too* well: to ensure absolute semantic consistency, it updated every reference to the moved symbols to their new Fully-Qualified Names (FQNs), including the keys in the `.stitcher.yaml` documentation files.

While technically correct, this is not the desired convention for those files, which should use simple names for readability. Your diagnosis is spot-on: a simple string split is naive and dangerous. We must use a tool that understands the code to map the FQN back to its *actual* defined name.

I will create a script to perform this semantic reversion.

## [WIP] chore: Create script to revert stitcher.yaml keys to simple names

### 错误分析

The `stitcher refactor apply` command, in its quest for perfect semantic integrity, converted all keys in `.stitcher.yaml` files from simple names (e.g., `Engine`) to Fully-Qualified Names (e.g., `cascade.runtime.host.instance.Engine`). This makes the documentation files verbose and harder to read.

The problem is that this is a "correct but undesirable" side-effect of the refactoring tool. We need a post-processing step to revert these keys to their simple, canonical form. A naive `key.split('.')[-1]` approach is insufficient and incorrect, as it cannot distinguish between a class `MyClass` defined in `my_module.py` and a different class with the same name in another module.

The correct solution requires a script that can semantically resolve the FQN to its source definition and reliably extract the simple name from the Abstract Syntax Tree (AST) or a similar semantic representation.

### 用户需求

Create a Python script that batch-processes all `.stitcher.yaml` files in the repository. For each file, it should convert any key that is a fully-qualified name back to its simple name, using semantic code analysis to ensure correctness.

### 评论

This is an excellent application of "infrastructure as code." Instead of manually fixing dozens of files, we'll build a precise, reusable tool to do it for us. I will use the `griffe` library, the same powerful static analysis engine that powers Stitcher itself, to build a reliable mapping from FQN to the source code definition. This ensures our script is as robust as the tool that caused the issue in the first place.

**Prerequisites**: You will need to install `griffe` and `pyyaml` to run this script: `pip install griffe pyyaml`.

### 目标

1.  Create a new script at `scripts/revert_stitcher_keys.py`.
2.  The script will recursively find all `.stitcher.yaml` files.
3.  For each file, it will load the YAML content.
4.  It will use `griffe` to analyze the codebase and resolve each FQN key to its source object.
5.  It will replace the FQN key with the simple name of the resolved object.
6.  The script will overwrite the original `.stitcher.yaml` file with the corrected content.

### 基本原理

We will leverage `griffe.GriffeLoader` to build a complete semantic model of the entire monorepo. By feeding it the source paths of all our packages, it can resolve any FQN string (like `"cascade.runtime.host.instance.Engine"`) to a `griffe.dataclasses.Object`. This object contains the definitive simple name (`"Engine"`), which we can then use to update our YAML files. This is the only way to satisfy the user's constraint of being AST-aware and correct.

### 标签

#intent/tooling #flow/ready #priority/high
#comp/build #scope/dx
#ai/instruct
#task/domain/architecture #task/object/monorepo #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Create the key reversion script

~~~~~act
write_file
scripts/revert_stitcher_keys.py
~~~~~
~~~~~python
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from griffe.loader import GriffeLoader
from griffe.exceptions import ObjectNotFoundError

# --- Configuration ---
# Adjust these paths if your project structure is different
PROJECT_ROOT = Path(__file__).parent.parent
PACKAGES_DIR = PROJECT_ROOT / "packages"
SEARCH_PATHS = [str(p / "src") for p in PACKAGES_DIR.iterdir() if (p / "src").is_dir()]


def get_simple_name_from_fqn(fqn: str, loader: GriffeLoader) -> Optional[str]:
    """
    Resolves a Fully-Qualified Name to its simple name using griffe.

    Args:
        fqn: The FQN string (e.g., "cascade.runtime.host.instance.Engine").
        loader: The configured GriffeLoader instance.

    Returns:
        The simple name (e.g., "Engine") if resolution is successful,
        otherwise None.
    """
    if "." not in fqn:
        # It's already a simple name or not a Python path.
        return None

    try:
        # This is the core semantic lookup.
        obj = loader.load_object(fqn)
        return obj.name
    except ObjectNotFoundError:
        # This FQN doesn't exist in our codebase, might be from an external lib.
        # We should not touch it.
        # print(f"  -  Warn: FQN '{fqn}' not found, skipping.")
        return None
    except Exception as e:
        print(f"  - Error resolving FQN '{fqn}': {e}", file=sys.stderr)
        return None


def process_yaml_file(yaml_path: Path, loader: GriffeLoader) -> None:
    """
    Processes a single .stitcher.yaml file, converting FQN keys to simple names.
    """
    print(f"Processing: {yaml_path.relative_to(PROJECT_ROOT)}")
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            print("  - Skip: Not a dictionary file.")
            return

        new_data: Dict[str, Any] = {}
        modified = False

        for key, value in data.items():
            simple_name = get_simple_name_from_fqn(key, loader)
            if simple_name:
                new_data[simple_name] = value
                if key != simple_name:
                    print(f"  - Reverting '{key}' -> '{simple_name}'")
                    modified = True
            else:
                new_data[key] = value

        if modified:
            with open(yaml_path, "w", encoding="utf-8") as f:
                # Using a wider indent and trying to preserve some structure
                yaml.dump(new_data, f, indent=2, sort_keys=False, default_flow_style=False)
            print("  -> File updated.")

    except Exception as e:
        print(f"  -> Error processing file: {e}", file=sys.stderr)


def main():
    """
    Main function to find and process all .stitcher.yaml files.
    """
    print("Initializing Griffe Loader...")
    print(f"Searching for sources in: {SEARCH_PATHS}")
    loader = GriffeLoader(search_paths=SEARCH_PATHS)
    print("Loader initialized. Analyzing codebase (this may take a moment)...")
    # Pre-loading everything once is much faster than loading objects one-by-one
    for path in SEARCH_PATHS:
        loader.load_module(Path(path).name)
    print("Analysis complete.")
    print("-" * 40)

    yaml_files = list(PROJECT_ROOT.rglob("*.stitcher.yaml"))
    print(f"Found {len(yaml_files)} stitcher.yaml files to process.\n")

    for yaml_path in yaml_files:
        process_yaml_file(yaml_path, loader)

    print("\nDone.")


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议

1.  **Install Dependencies**: If you haven't already, run `pip install "griffe[extras]" pyyaml`.
2.  **Run the Script**: Execute `python scripts/revert_stitcher_keys.py` from the root of your project.
3.  **Review Changes**: Use `git diff` to review the automated changes. They should be limited to the keys in the YAML files.
4.  **Commit**: Once you're satisfied, you can amend the previous commit or create a new one. I would recommend creating a new commit for clarity. I can generate that plan for you next.
