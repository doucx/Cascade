import sys
import importlib.metadata

def diagnose_providers():
    """
    Scans the environment for installed Cascade providers and reports findings.
    """
    print("--- Cascade Provider Discovery Diagnostics ---")
    
    group_name = "cascade.providers"
    found_ipfs = False
    
    print(f"\nQuerying for entry points in group: '{group_name}'...")

    try:
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group=group_name)
        else:
            # Legacy way for Python < 3.10
            entry_points = importlib.metadata.entry_points().get(group_name, [])

        if not entry_points:
            print("\n[FAIL] No entry points found for this group.")
            print_conclusion(False)
            return

        print(f"\n[OK] Found {len(entry_points)} entry points. Listing them:")
        print("-" * 30)
        
        for ep in sorted(entry_points, key=lambda e: e.name):
            status = " "
            if ep.name.startswith("ipfs."):
                status = "*"
                found_ipfs = True
            
            print(f"[{status}] {ep.name:<25} -> {ep.value}")
            
        print("-" * 30)
        print("(*) marks providers relevant to the current issue.")

        print_conclusion(found_ipfs)

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        print("This might indicate a problem with the Python environment or metadata discovery.")

def print_conclusion(found_ipfs: bool):
    print("\n--- Conclusion ---")
    if found_ipfs:
        print("[SUCCESS] IPFS providers were successfully discovered in the environment.")
        print("This suggests the problem is more complex, possibly related to pytest's specific environment setup or caching.")
    else:
        print("[FAILURE] IPFS providers were NOT discovered.")
        print("This is the likely cause of the 'AttributeError: ... has no attribute ipfs'.")
        print("\nRecommendation:")
        print("  Run the following command from the project root to install all packages in editable mode:")
        print("  $ uv pip install -e .")
        print("  This will register the entry points with your Python environment.")

if __name__ == "__main__":
    diagnose_providers()