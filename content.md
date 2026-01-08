在此计划中，我们将修复因缺少 `build.py` 导致的测试错误，并将 `cascade-graph` 的剩余资产彻底清理和迁移，完成“绞杀”。

## [WIP] refactor(graph): 实现 build 兼容层并彻底移除 cascade-graph 包

### 用户需求
1.  修复因 `cascade.runtime.graph.build` 模块缺失导致的广泛测试失败。
2.  将 `cascade-graph` 的测试套件迁移至 `cascade-runtime`。
3.  彻底删除 `cascade-graph` 包，并清理相关依赖。
4.  修正 `BlueprintHasher` 迁移后的遗留引用。

### 评论
这是一个关键的架构收敛步骤。通过在 Runtime 中重建 `build.py` 作为兼容层（内部调用 Compiler + Adapter），我们既保持了 API 兼容性，又在实质上完成了底层逻辑的切换。这将验证 Compiler 路径的正确性。

### 目标
1.  创建 `cascade.runtime.graph.build` 模块。
2.  迁移并能够运行原 `cascade-graph` 的测试。
3.  删除 `cascade-graph` 目录。
4.  更新所有 `pyproject.toml`。

### 基本原理
直接修改所有下游测试去使用 `IRGenerator` 工作量过大且容易产生噪音。建立一个与旧接口一致的 `build_graph` 函数，但在内部使用新的 `Compiler` 栈，是实现“无痛迁移”的最佳策略。

### 标签
#intent/refine #flow/ready #priority/critical #comp/runtime #comp/graph #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-graph #task/action/terminate #task/state/end

---

### Script

#### Acts 1: 创建兼容层 `build.py`

我们在 `cascade-runtime` 中重建 `build_graph` 函数，但其实现现在代理给 Compiler 和 Adapter。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/graph/build.py
~~~~~
~~~~~python
from typing import Any, Tuple, Dict, Callable, Optional
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.model import Graph, Node
from cascade.runtime.graph.registry import NodeRegistry


def build_graph(
    target: Any, registry: Optional[NodeRegistry] = None
) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
    """
    Legacy compatibility layer for graph building.
    Internally uses the Cascade Compiler (IRGenerator) and Runtime Adapter.
    """
    # 1. Generate Intermediate Representation (IR)
    ir = IRGenerator().generate(target)

    # 2. Adapt IR to Runtime Object Model
    # We pass the registry to ensure node interning/deduplication works as expected
    adapter = IRToRuntimeAdapter(registry=registry)
    return adapter.adapt(ir)
~~~~~

#### Acts 2: 迁移 BlueprintHasher 引用

上一轮我们移动了 `BlueprintHasher`，但没有更新导入路径。

#### Acts 3: 迁移测试

将 `cascade-graph` 的测试移动到 `cascade-runtime` 下，作为 legacy_graph 测试。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-runtime/tests/legacy_graph
cp -r packages/cascade-graph/tests/* packages/cascade-runtime/tests/legacy_graph/
rm -rf packages/cascade-graph/tests
~~~~~

#### Acts 4: 删除 `cascade-graph` 包

现在 `cascade-graph` 应该是空的或者只包含废弃文件了。我们将其彻底移除。

#### Acts 5: 清理依赖配置

从所有 `pyproject.toml` 中移除 `cascade-graph` 依赖。

~~~~~act
run_command
~~~~~
~~~~~bash
find packages -name "pyproject.toml" -print0 | xargs -0 sed -i '/"cascade-graph",/d'
~~~~~

同时更新根目录的 `pyproject.toml`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "cascade-sdk",
    "cascade-graph",
    "cascade-library",
~~~~~
~~~~~toml.new
    "cascade-sdk",
    "cascade-library",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-reflection = { workspace = true }
cascade-graph = { workspace = true }
cascade-library = { workspace = true }
~~~~~
~~~~~toml.new
cascade-reflection = { workspace = true }
cascade-library = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/cascade-provider-ipfs",
    "packages/cascade-graph",
    "packages/cascade-library",
~~~~~
~~~~~toml.new
    "packages/cascade-provider-ipfs",
    "packages/cascade-library",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-runtime/src", "packages/cascade-graph/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~
~~~~~toml.new
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-runtime/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~

#### Acts 6: 修复 Runtime 自身导出

确保 `cascade.runtime.graph` 正确导出了 `build_graph`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/__init__.py
~~~~~
~~~~~python.old
from .adapter import IRToRuntimeAdapter
from .hashing import BlueprintHasher

__all__ = [
~~~~~
~~~~~python.new
from .adapter import IRToRuntimeAdapter
from .hashing import BlueprintHasher
from .build import build_graph

__all__ = [
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/__init__.py
~~~~~
~~~~~python.old
    "from_json",
    "IRToRuntimeAdapter",
    "BlueprintHasher",
]
~~~~~
~~~~~python.new
    "from_json",
    "IRToRuntimeAdapter",
    "BlueprintHasher",
    "build_graph",
]
~~~~~

### 下一步建议

运行完整的测试套件，特别是新迁移的 `packages/cascade-runtime/tests/legacy_graph`，以确保新的 Compiler 路径能够正确通过所有旧的测试用例。如果测试通过，说明我们成功完成了“绞杀”。
