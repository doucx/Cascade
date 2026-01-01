import sys
import importlib.metadata
import traceback

def diagnose_providers():
    """
    Scans the environment for installed Cascade providers AND attempts to load them
    to simulate the Registry's behavior.
    """
    print("--- Cascade Provider Loading Diagnostics ---")
    
    group_name = "cascade.providers"
    
    print(f"\nScanning group: '{group_name}'...")

    try:
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group=group_name)
        else:
            entry_points = importlib.metadata.entry_points().get(group_name, [])

        if not entry_points:
            print("\n[FAIL] No entry points found.")
            return

        print(f"\nFound {len(entry_points)} entry points. Attempting to load 'ipfs.*' providers...\n")
        
        ipfs_providers = [ep for ep in entry_points if ep.name.startswith("ipfs.")]
        
        if not ipfs_providers:
            print("[FAIL] No 'ipfs.*' entry points found in the list!")
            return

        all_success = True
        
        for ep in ipfs_providers:
            print(f"[*] Testing Provider: {ep.name}")
            print(f"    Entry Point: {ep.value}")
            
            try:
                # 1. Load Class
                print("    -> Loading class...", end=" ")
                provider_cls = ep.load()
                print("OK")
                
                # 2. Instantiate
                print("    -> Instantiating...", end=" ")
                provider_instance = provider_cls()
                print("OK")
                
                # 3. Check Protocol
                if not hasattr(provider_instance, "create_factory") or not hasattr(provider_instance, "name"):
                    print("\n    [WARN] Does not implement Provider protocol.")
                    continue

                # 4. Create Factory (Crucial Step: checks dependencies like aiohttp)
                print("    -> Calling create_factory()...", end=" ")
                _ = provider_instance.create_factory()
                print("OK")
                
                print(f"    [SUCCESS] '{ep.name}' loaded and verified.\n")
                
            except Exception:
                all_success = False
                print("FAIL")
                print(f"\n    [ERROR] Failed to load provider '{ep.name}'!")
                print("    Traceback:")
                traceback.print_exc(file=sys.stdout)
                print("-" * 40 + "\n")

        print_conclusion(all_success)

    except Exception as e:
        print(f"\n[ERROR] Diagnostic script crashed: {e}")
        traceback.print_exc()

def print_conclusion(success: bool):
    print("--- Conclusion ---")
    if success:
        print("[SUCCESS] All IPFS providers loaded correctly.")
        print("If the test still fails, the issue might be related to how 'cascade-sdk' lazy-loads the registry.")
    else:
        print("[FAILURE] Some IPFS providers failed to load.")
        print("This confirms why 'cs.ipfs' is failing: the providers are being ignored by the registry due to load errors.")
        print("Check the tracebacks above for missing dependencies (e.g. aiohttp) or import errors.")

if __name__ == "__main__":
    diagnose_providers()