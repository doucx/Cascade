import sys
import importlib.metadata
from pathlib import Path

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_header(title):
    print(f"\n--- {YELLOW}{title}{RESET} ---")


def check(condition, success_msg, failure_msg):
    if condition:
        print(f"  {GREEN}✅ {success_msg}{RESET}")
        return True
    else:
        print(f"  {RED}❌ {failure_msg}{RESET}")
        return False


def main():
    print_header("Step 1: Environment Sanity Check")
    py_executable = sys.executable
    print(f"  - Python Executable: {py_executable}")
    check(
        ".venv" in py_executable or "pyvenv" in py_executable,
        "Running in a virtual environment.",
        "Warning: Not running in a .venv or pyvenv. Results may be unpredictable.",
    )
    print("  - sys.path entries:")
    # Filter to show only workspace paths for clarity
    workspace_root = Path(__file__).parent.parent
    for p in sys.path:
        if str(workspace_root) in p:
            print(f"    - {p}")

    print_header("Step 2: Discovering Entry Points via importlib.metadata")
    try:
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group="cascade.providers")
        else:
            entry_points = importlib.metadata.entry_points().get(
                "cascade.providers", []
            )

        if check(entry_points, f"Found {len(entry_points)} entry points.", "No entry points found for 'cascade.providers'."):
            for ep in sorted(entry_points, key=lambda x: x.name):
                print(f"    - Found: '{ep.name}' -> '{ep.value}'")
    except Exception as e:
        print(f"  {RED}❌ Failed to query entry points: {e}{RESET}")
        entry_points = []


    print_header("Step 3: Attempting to Load Entry Points")
    all_loaded = True
    loaded_providers = {}
    if not entry_points:
        print(f"  {YELLOW}Skipping, no entry points found in Step 2.{RESET}")
    else:
        for ep in entry_points:
            try:
                provider_cls = ep.load()
                loaded_providers[ep.name] = provider_cls
                print(f"  {GREEN}✅ Successfully loaded '{ep.name}'{RESET}")
            except Exception as e:
                print(f"  {RED}❌ FAILED to load '{ep.name}': {type(e).__name__}: {e}{RESET}")
                all_loaded = False
        check(all_loaded, "All discovered providers loaded successfully.", "One or more providers failed to load.")


    print_header("Step 4: Simulating Registry Initialization")
    registry_instance = None
    try:
        from cascade.providers.registry import ProviderRegistry
        registry_instance = ProviderRegistry()
        # Directly call the discovery method to bypass caching
        registry_instance._discover_entry_points()
        check(True, "Instantiated and ran discovery on ProviderRegistry.", "")
        
        provider_names = sorted(registry_instance._providers.keys())
        if check(provider_names, f"Registry found {len(provider_names)} providers.", "Registry is empty after discovery."):
             for name in provider_names:
                 print(f"    - Registered: '{name}'")

    except Exception as e:
        check(False, "", f"Failed to initialize or run registry: {type(e).__name__}: {e}")

    print_header("Step 5: Simulating `cs.http.get` Access")
    try:
        import cascade as cs
        check(True, "Successfully imported `cascade as cs`", "Failed to import cascade.")
        
        # Test a nested provider
        http_provider = cs.http
        check(http_provider is not None, "cs.http resolved to an object.", "cs.http is None or raised AttributeError.")
        
        http_get_task = cs.http.get
        check(http_get_task is not None, "cs.http.get resolved to an object.", "cs.http.get is None or raised AttributeError.")

        # Test a direct provider
        shell_task = cs.shell
        check(shell_task is not None, "cs.shell resolved to an object.", "cs.shell is None or raised AttributeError.")
        
    except Exception as e:
        check(False, "", f"Accessing providers failed: {type(e).__name__}: {e}")

    print_header("Conclusion")
    if all_loaded and registry_instance and 'http.get' in registry_instance._providers:
        print(f"{GREEN}Diagnosis: Provider loading mechanism appears to be working correctly.{RESET}")
    else:
        print(f"{RED}Diagnosis: Provider loading is broken. Check for missing `__init__.py` files in namespace packages (especially `cascade/providers/`), or installation issues.{RESET}")


if __name__ == "__main__":
    main()