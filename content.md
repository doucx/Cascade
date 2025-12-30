## [WIP] feat(compiler): 初始化编译器前端包并建立 TDD RED 状态

### 用户需求
根据 TDD 重构路线图的 "Phase 1: Compiler Frontend"，我们需要创建一个新的包 `cascade-compiler`。此阶段的目标是实现一个能将 `LazyResult` 转换为 `GraphIR` 的前端。当前的具体的任务是初始化包结构，并创建处于 RED 状态（失败状态）的测试用例。

### 评论
这将是 Cascade 从即时执行模式转向编译运行模式的第一步。我们将严格遵循 TDD 流程，先写测试。测试用例将覆盖单一任务编译、线性依赖解析，并强制检查架构公理中规定的长命名哈希规范。

### 目标
1.  创建 `packages/cascade-compiler` 的基础包结构（符合 uv/hatch 规范）。
2.  在根目录 `pyproject.toml` 中注册新包。
3.  创建 `packages/cascade-compiler/tests/test_frontend.py`，包含针对 `Frontend.compile()` 的测试用例。这些测试目前会因为 `ImportError` 而失败（RED 状态）。

### 基本原理
1.  **包隔离**: `cascade-compiler` 被设计为一个独立的包，以实现构建逻辑与运行时逻辑的物理解耦。
2.  **TDD 启动**: 通过编写 `test_compile_single_task_structure` 和 `test_compile_linear_dependency`，我们定义了编译器的输入（`LazyResult`）和输出（`GraphIR`）契约。
3.  **公理强制**: 测试中显式断言了 `current_code_structure_hash` 的存在，确保从第一行代码开始就遵守哈希命名公理。

### 标签
#intent/tooling #flow/draft #priority/high #comp/build #concept/ir #task/domain/refactor #task/object/compiler-frontend #task/action/init #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-compiler` 包结构

首先创建包的元数据文件和命名空间入口。

~~~~~act
write_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-compiler"
version = "0.1.0"
description = "Compiler frontend and backend for Cascade."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-graph", # Temporarily depend on graph for reflection analysis logic
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 注册新包到 Workspace

更新根目录的配置，使新包成为工作区的一部分。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-connector-local = { workspace = true }

[tool.hatch.workspaces]
~~~~~
~~~~~toml.new
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }

[tool.hatch.workspaces]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/cascade-library",
    "packages/cascade-connector-local",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml.new
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-compiler",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "ruff",
]
~~~~~
~~~~~toml.new
  "cascade-cli-observer",
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-compiler",
  "ruff",
]
~~~~~

#### Acts 3: 创建 RED 状态的测试文件

创建测试文件。注意我们使用了 `xfail` 标记，并预期 `ImportError` 或 `NameError`，因为 `Frontend` 类尚未实现。这标志着 TDD 的 RED 阶段。

~~~~~act
write_file
packages/cascade-compiler/tests/test_frontend.py
~~~~~
~~~~~python
import pytest

# NOTE: The 'cascade.compiler.frontend' module does not exist yet.
# This is the expected RED state for Phase 1.
try:
    from cascade.compiler.frontend import Frontend
    from cascade.spec.task import task
    from cascade.spec.ir.models import GraphIR
except ImportError:
    pass


@pytest.mark.xfail(reason="Frontend not implemented", raises=(ImportError, NameError))
def test_compile_single_task_structure():
    """
    Case 1: Single Task
    Verify that Frontend.compile transforms a single LazyResult into a GraphIR.
    Also verifies the 'Hash Naming Axiom' by checking fingerprint keys.
    """
    @task
    def simple_task(x: int) -> int:
        return x + 1

    # 1. Prepare Input
    lazy = simple_task(x=10)

    # 2. Execute Compilation (Will fail here)
    ir = Frontend.compile(lazy)

    # 3. Verify Graph Structure
    assert isinstance(ir, GraphIR)
    assert len(ir.nodes) == 1
    assert len(ir.edges) == 0
    
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.inputs["x"] == 10
    
    # 4. Axiom Check: Enforce Long Hash Naming
    # We don't check the value, but the KEY must be the long form.
    fp = node.definition.fingerprint
    assert "current_code_structure_hash" in fp
    # Ensure no short names are present
    assert "hash" not in fp
    assert "id" not in fp
    assert "structure_hash" not in fp


@pytest.mark.xfail(reason="Frontend not implemented", raises=(ImportError, NameError))
def test_compile_linear_dependency():
    """
    Case 2: Linear Dependency (t2 -> t1)
    Verify that EdgeIR is correctly generated for dependencies.
    """
    @task
    def producer(): return 1
    
    @task
    def consumer(val): return val + 1

    # t2 depends on t1
    t1 = producer()
    t2 = consumer(val=t1)

    ir = Frontend.compile(t2)

    assert len(ir.nodes) == 2
    assert len(ir.edges) == 1
    
    edge = ir.edges[0]
    
    # Verify edge connectivity
    target_node = next(n for n in ir.nodes if n.definition.name == "consumer")
    source_node = next(n for n in ir.nodes if n.definition.name == "producer")
    
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg == "val"
~~~~~

### 下一步建议
我们已经建立了 TDD 的 RED 状态。下一步是实现 `cascade.compiler.frontend.Frontend` 类，使其通过上述测试。

在实现过程中，我们需要：
1.  创建一个 `Frontend` 类，提供静态方法 `compile`。
2.  移植（并净化）原 `GraphBuilder` 的遍历逻辑。
3.  确保在生成 `NodeIR` 时，正确调用哈希计算逻辑，并填充 `fingerprint` 中的 `current_code_structure_hash`。
