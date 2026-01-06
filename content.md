简要回答：
分析发现了两个严重问题：
1.  **标准库缺陷**: `const_probe` 直接透传了原始值（`int`），违反了 v3.1 的 Ref-Based 协议。它必须将数据存入 `ObjectStore` 并返回 `Ref`。
2.  **测试缺陷**: 集成测试中注册用户代码的逻辑依赖于“物理 ID 包含函数名”的错误假设。实际上物理 ID 是基于哈希的，导致代码注册表为空。

我将生成一个包含两个 `fix` 操作的计划来解决这些问题。

## [WIP] fix(std & test): 修复 const_probe 的 Ref 转换及测试注册逻辑

### 错误分析
1.  `AttributeError: 'int' object has no attribute 'uri'`: `LocalComputeService` 接收到了 `int` 类型的输入，说明 `const_probe` 没有将常量值转换为 `Ref`。物理层必须只流转 `Ref`。
2.  `KeyError`: 代码注册表为空。测试代码试图通过匹配字符串 `add_one` 来注册函数，但物理节点 ID 是纯哈希，不包含函数名。

### 用户需求
1.  修改 `cascade.std.probe.const`，使其与 `ObjectStore` 交互，输出 `Ref`。
2.  重构集成测试中的代码注册逻辑，使用 `GraphIR` 正确映射节点 ID 和函数。

### 目标
1.  更新 `packages/cascade-std/src/cascade/std/probe/const.py`。
2.  更新 `packages/cascade-vm/tests/integration/test_ref_architecture.py`。

### 基本原理
**Ref-Based 协议**: 所有进入物理图的数据（包括常量）都必须在源头被“物化”为 `Ref`。`Probe` 节点的职责正是连接“非 Ref 世界”（环境、常量）和“Ref 世界”。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #ai/instruct #task/domain/vm #task/object/probe #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 const_probe 以返回 Ref

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/const.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    return {"out": Token(payload=val_token.payload, trace=val_token.trace)}
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")
    ref = store.put(raw_value)

    return {"out": Token(payload=ref, trace=val_token.trace)}
~~~~~

#### Acts 2: 修复集成测试的代码注册逻辑

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
    # 3. Register user code in the CodeRegistry
    # The key is the canonical hash, found in the symbol table
    code_registry = CodeRegistry()
    for node_id, canonical_hash in assembly.symbol_table.items():
        if "add_one" in node_id:
            code_registry.register(canonical_hash, add_one.func)
        elif "square" in node_id:
            code_registry.register(canonical_hash, square.func)

    # 4. Build the function map for the Reactor (Standard Library ICs)
~~~~~
~~~~~python.new
    # 3. Register user code in the CodeRegistry
    # We need to map the physical ID back to the function.
    # We use the GraphIR to find the node ID for each task name.
    code_registry = CodeRegistry()
    
    # Helper to find canonical hash for a named task
    def register_task(task_name, func):
        # Find the NodeIR
        node_ir = next(n for n in graph_ir.nodes if n.name == task_name)
        # Construct the physical worker ID (Convention from PhysicalIdGenerator)
        worker_id = f"{node_ir.current_node_instance_hash}.worker"
        # Lookup canonical hash
        canonical_hash = assembly.symbol_table[worker_id]
        code_registry.register(canonical_hash, func)

    register_task("add_one", add_one.func)
    register_task("square", square.func)

    # 4. Build the function map for the Reactor (Standard Library ICs)
~~~~~

### 下一步建议
再次运行测试 `test_ref_architecture.py`。这次应该能通过。
