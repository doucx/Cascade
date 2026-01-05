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