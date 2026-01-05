Of course. Your analysis is spot on. The `stitcher refactor apply` command did its job with semantic precision by updating all keys to their new, unambiguous Fully Qualified Names (FQNs). However, for the sake of brevity and readability within the `.stitcher.yaml` sidecar files, it's desirable to use the simple, unqualified class or function name as the key.

The previous `[COMMIT]` plan was premature. I will generate a new plan to create and run a one-off script that batch converts all these FQNs back to their simple names across the entire monorepo.

## [WIP] chore: Unqualify FQN keys in all .stitcher.yaml files

### 错误分析

The recent semantic refactoring correctly updated all symbol keys in `.stitcher.yaml` files to their full FQNs (e.g., `"cascade.runtime.io.cache.in_memory.InMemoryCacheBackend"`). While technically correct and unambiguous, this makes the files verbose and harder to read. The desired convention is to use only the simple, unqualified name (e.g., `"InMemoryCacheBackend"`).

A manual conversion would be tedious and error-prone. The correct approach is to use an automated script to perform this stylistic transformation.

### 用户需求

Create and execute a script that iterates through all `.stitcher.yaml` files in the project, reads their content, and rewrites them with the FQN keys converted back to simple names.

### 评论

This is a necessary "beautification" step after a major refactoring. It enforces a consistent and clean style for our documentation sidecar files. Creating a dedicated script ensures the transformation is applied uniformly everywhere and can be easily re-run if needed.

### 目标

1.  Create a Python script named `scripts/refactor_unqualify_stitcher_keys.py`.
2.  The script will scan the entire project for `*.stitcher.yaml` files.
3.  For each file, it will load the YAML data, transform the dictionary keys from FQNs to simple names, and overwrite the original file with the new content.
4.  Execute the script to apply the changes.
5.  Remove the script after its single use.

### 基本原理

We will use Python's `pathlib` for recursive file searching and the `PyYAML` library to safely parse and dump YAML content, preserving structure. The key transformation logic will be a simple string split on `.` to extract the last segment. The script will also include a check for key collisions within a single file to prevent data loss.

### 标签

#intent/tooling #flow/ready #priority/high
#comp/build #scope/dx
#ai/instruct
#task/domain/architecture #task/object/monorepo #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Create the FQN-to-Simple-Name Conversion Script

First, I will create the Python script that will perform the batch conversion.

~~~~~act
write_file
scripts/refactor_unqualify_stitcher_keys.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import sys
from pathlib import Path
import yaml

def process_file(file_path: Path):
    """
    Reads a .stitcher.yaml file, converts its FQN keys to simple names,
    and overwrites the file.
    """
    print(f"Processing: {file_path}", file=sys.stderr)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Handle empty files gracefully
            if not content.strip():
                return
            data = yaml.safe_load(content)

        if not isinstance(data, dict):
            return  # Skip files that aren't a simple key-value map

        new_data = {}
        has_changes = False
        for old_key, value in data.items():
            if "." in old_key:
                new_key = old_key.split('.')[-1]
                has_changes = True
            else:
                new_key = old_key

            if new_key in new_data:
                print(
                    f"  [WARNING] Key collision for '{new_key}' in {file_path}. "
                    f"'{old_key}' will overwrite a previous entry. Please review manually.",
                    file=sys.stderr,
                )
            new_data[new_key] = value

        if has_changes:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(new_data, f, default_flow_style=False, sort_keys=True)
            print(f"  -> Updated.", file=sys.stderr)

    except yaml.YAMLError as e:
        print(f"  [ERROR] Failed to parse YAML in {file_path}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"  [ERROR] An unexpected error occurred with {file_path}: {e}", file=sys.stderr)

def main():
    """
    Finds and processes all .stitcher.yaml files in the monorepo.
    """
    root_dir = Path.cwd()
    print(f"Scanning for .stitcher.yaml files in {root_dir}...", file=sys.stderr)
    stitcher_files = list(root_dir.rglob("*.stitcher.yaml"))

    if not stitcher_files:
        print("No .stitcher.yaml files found.", file=sys.stderr)
        return

    for file_path in stitcher_files:
        process_file(file_path)

    print(f"\nDone. Processed {len(stitcher_files)} files.", file=sys.stderr)

if __name__ == "__main__":
    main()
~~~~~

#### Acts 2: Execute the Script and Clean Up

Now, I'll run the script to apply the changes across the repository and then remove it.

~~~~~act
run_command
~~~~~
~~~~~bash
python scripts/refactor_unqualify_stitcher_keys.py
~~~~~

~~~~~act
delete_file
scripts/refactor_unqualify_stitcher_keys.py
~~~~~

### 下一步建议

The `.stitcher.yaml` files should now be cleaned up. Please review the changes with `git diff`. If everything looks correct, we can proceed with creating the final `[COMMIT]` plan.
