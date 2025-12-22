import os
import shutil
import subprocess

# Files that were incorrectly deleted from the old `interfaces` package
DELETED_SPEC_FILES = [
    "src/cascade/graph/model.py",
    "src/cascade/interfaces/protocols.py",
    "src/cascade/spec/__init__.py",
    "src/cascade/spec/common.py",
    "src/cascade/spec/constraint.py",
    "src/cascade/spec/input.py",
    "src/cascade/spec/lazy_types.py",
    "src/cascade/spec/resource.py",
    "src/cascade/spec/routing.py",
    "src/cascade/spec/task.py",
    "src/cascade/spec/telemetry.py",
]

def main():
    print("--- Starting Spec Recovery and Migration ---")
    root_dir = os.getcwd()
    old_pkg_path = os.path.join(root_dir, "packages/cascade-interfaces")
    new_pkg_path = os.path.join(root_dir, "packages/cascade-spec")

    # 1. Restore deleted files from Git index
    print("\nStep 1: Restoring deleted spec files...")
    for rel_path in DELETED_SPEC_FILES:
        full_path = os.path.join(old_pkg_path, rel_path)
        print(f"  Restoring {full_path}...")
        try:
            subprocess.run(["git", "restore", full_path], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"  Warning: Failed to restore {full_path}. It might not have been deleted. Stderr: {e.stderr.decode()}")
        except FileNotFoundError:
            print(f"  Warning: 'git' command not found. Skipping restore.")
            break

    # 2. Move restored files to the new spec package
    print("\nStep 2: Moving restored files to cascade-spec...")
    for rel_path in DELETED_SPEC_FILES:
        src_path = os.path.join(old_pkg_path, rel_path)
        # Construct a more logical destination path
        if 'graph/model.py' in rel_path:
             # specific rule for model.py
            dst_rel_path = "src/cascade/spec/model.py"
        else:
            dst_rel_path = rel_path
        
        dst_path = os.path.join(new_pkg_path, dst_rel_path)

        if os.path.exists(src_path):
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            print(f"  Moving {src_path} -> {dst_path}")
            shutil.move(src_path, dst_path)
        else:
            print(f"  Skipping move for {src_path} (not found).")

    # 3. Move the corresponding tests
    print("\nStep 3: Migrating tests from tests/interfaces to tests/spec...")
    old_test_path = os.path.join(root_dir, "tests/interfaces")
    new_test_path = os.path.join(root_dir, "tests/spec")
    
    if os.path.exists(old_test_path):
        if os.path.exists(new_test_path):
            print(f"  Warning: {new_test_path} already exists. Merging contents.")
            for item in os.listdir(old_test_path):
                shutil.move(os.path.join(old_test_path, item), new_test_path)
            shutil.rmtree(old_test_path)
        else:
            print(f"  Renaming {old_test_path} -> {new_test_path}")
            shutil.move(old_test_path, new_test_path)
    else:
        print("  tests/interfaces not found, skipping test migration.")

    # 4. Final cleanup
    print("\nStep 4: Cleaning up old directories...")
    if os.path.exists(old_pkg_path):
        try:
            # Only remove if it's empty after moves
            if not any(os.scandir(old_pkg_path)):
                 shutil.rmtree(old_pkg_path)
                 print(f"  Removed empty directory: {old_pkg_path}")
            else:
                 print(f"  Directory not empty, cleaning up subdirs...")
                 shutil.rmtree(os.path.join(old_pkg_path, 'src'), ignore_errors=True)

        except OSError as e:
            print(f"  Error cleaning up {old_pkg_path}: {e}")

    print("\n--- Recovery and Migration Complete ---")

if __name__ == "__main__":
    main()