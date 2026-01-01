## [WIP] chore: 增强诊断脚本以模拟 Provider 加载过程

### 错误分析
虽然初步诊断显示 `importlib.metadata` 能够发现入口点，但测试依然失败。这强烈暗示问题发生在 **加载** 或 **初始化** 提供者的阶段。

`Cascade` 的 `ProviderRegistry` 在发现入口点后，会立即尝试：
1.  加载类 (`ep.load()`)
2.  实例化类 (`cls()`)
3.  调用工厂方法 (`create_factory()`)

如果在这个过程中发生异常（例如 `ImportError`，或者 `create_factory` 中的依赖检查失败），`ProviderRegistry` 会捕获异常并打印错误（但在测试输出中可能被淹没），导致该提供者被静默忽略。

`IpfsCatProvider` 只有在检测到 `aiohttp` 时才会成功初始化。如果它失败了，`registry` 中就不会有 `ipfs.cat`，导致 `cs.ipfs` 查找失败。我们需要一个脚本来精确模拟这个过程并暴露潜在的错误。

### 目标
更新 `diagnose_providers.py`，不仅列出入口点，还要**尝试加载和实例化它们**，完全复刻 `ProviderRegistry` 的行为，以便捕获并显示任何在加载阶段发生的错误。

### 计划
1.  修改 `diagnose_providers.py`。
2.  增加 `simulate_registry_loading` 函数。
3.  对发现的每个入口点执行 `load()` 和 `create_factory()`。
4.  直接报告任何异常。

### 标签
#intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/provider-discovery #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 更新诊断脚本

~~~~~act
write_file
diagnose_providers.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议

1.  运行更新后的诊断脚本：
    ```bash
    python diagnose_providers.py
    ```
2.  **分析输出**：
    *   这个脚本会执行 `create_factory()`。如果 `aiohttp` 在运行时环境中真的无法导入，或者版本不兼容，这里会直接抛出 Traceback。
    *   请特别留意是否有 `ImportError: The 'aiohttp' library is required...` 这样的错误。
