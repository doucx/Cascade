Excellent. We have successfully completed Phase 0, establishing the foundational data structures for our new architecture.

Now, we will proceed to Phase 1: "Compiler Frontend", following the TDD methodology. The first step is to create the package structure and the initial failing tests that will define the contract for our new compiler.

I will create the necessary package files, update the monorepo configuration to recognize the new `cascade-compiler` package, and then write the initial test file to establish the "RED" state.

## [WIP] feat(compiler): Establish compiler package and initial TDD tests

### 用户需求
根据 TDD 重构路线图 (`01KDQNYD1QYXC9V1HH6AVS8WKJ`)，我们开始实施阶段 1：编译器前端。此计划的目标是创建 `cascade-compiler` 这个新包，并为其编写初始的、会失败的测试用例 (`test_frontend.py`)，从而进入 TDD 流程的 "RED" 状态。

### 评论
这是新编译/运行架构的核心起点。建立一个独立的 `cascade-compiler` 包能够强制实现职责分离，将图的构建逻辑从原有的 `cascade-graph` 和 `cascade-engine` 中彻底解耦出来。首先创建测试文件，明确定义了 `Frontend` 编译器的输入 (`LazyResult`) 和输出 (`GraphIR`) 契约，为后续的实现提供了清晰的目标。

### 目标
1.  创建 `packages/cascade-compiler` 的目录结构和 `pyproject.toml` 文件。
2.  确保新包符合 `uv` 工作区和 PEP 561 类型提示规范。
3.  更新根目录的 `pyproject.toml`，将新包加入工作区和开发依赖。
4.  在 `packages/cascade-compiler/tests/` 中创建 `test_frontend.py` 测试文件。
5.  测试文件将定义两个核心用例：编译单个任务和编译带有线性依赖的任务，并断言生成的 `GraphIR` 结构的正确性。

### 基本原理
我们通过一系列文件系统操作来构建新包的基础设施。首先，使用 `run_command` 创建目录和必要的文件（如 `__init__.py` 和 `py.typed`）。接着，使用 `write_file` 创建包的 `pyproject.toml`，定义其元数据和依赖（它将依赖我们刚在阶段 0 中完善的 `cascade-spec`）。然后，通过 `patch_file` 将新包集成到整个 monorepo 的构建系统中。最后，创建将失败的测试文件，它会尝试导入一个尚不存在的 `cascade.compiler.Frontend` 类，从而完美地建立 TDD 的 "RED" 状态。

### 标签
#intent/build #intent/tooling #flow/ready #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/refactor #task/object/compiler-frontend #task/action/define #task/state/continue

---

### Script

#### Acts 1: 创建 `cascade-compiler` 包的目录结构

我们首先创建新包所需的所有目录和空的 `__init__.py` 文件，以确保它被识别为一个正确的 Python 命名空间包。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-compiler/src/cascade/compiler
mkdir -p packages/cascade-compiler/tests
touch packages/cascade-compiler/src/cascade/__init__.py
touch packages/cascade-compiler/src/cascade/compiler/__init__.py
touch packages/cascade-compiler/src/cascade/py.typed
~~~~~

#### Acts 2: 设置命名空间包

为了符合项目的显式命名空间包规范，我们需要在 `src/cascade/__init__.py` 文件中添加 `pkgutil` 代码。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 3: 创建 `cascade-compiler` 的 `pyproject.toml`

此文件定义了新包的元数据、依赖项（`cascade-spec` 和 `cascade-graph`）和构建配置。

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
description = "Compiler frontend, optimizer, and backend for Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec",
  "cascade-graph"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-graph = { workspace = true }
~~~~~

#### Acts 4: 将新包集成到根 `pyproject.toml`

我们将 `cascade-compiler` 添加到 `uv` 的源和 `dev` 依赖中，以便 monorepo 中的其他包可以发现和使用它。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
~~~~~
~~~~~toml.new
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-compiler = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "ruff",
]
~~~~~
~~~~~toml.new
  "cascade-connector-mqtt",
  "cascade-connector-local",
  "cascade-compiler",
  "ruff",
]
~~~~~

#### Acts 5: 创建 TDD 的 "RED" 测试文件

这是此计划的核心步骤。我们创建 `test_frontend.py`，它会因为 `cascade.compiler.Frontend` 不存在而失败。

~~~~~act
write_file
packages/cascade-compiler/tests/test_frontend.py
~~~~~
~~~~~python
import pytest

# This import will fail, which is the point of this TDD step.
# We mark the tests as xfail to acknowledge this.
try:
    from cascade.compiler import Frontend
except ImportError:
    pass

# We need these to construct the test cases
from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR


@pytest.mark.xfail(raises=(ImportError, NameError), reason="Frontend not yet implemented")
def test_compile_single_task():
    """
    Tests compiling a single, dependency-free task.
    Asserts: The resulting IR contains exactly one node and zero edges.
    """
    @task
    def my_task():
        return "hello"

    target = my_task()
    frontend = Frontend()
    graph_ir: GraphIR = frontend.compile(target)

    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1
    assert len(graph_ir.edges) == 0

    node = graph_ir.nodes[0]
    assert isinstance(node, NodeIR)
    assert node.definition.name == "my_task"


@pytest.mark.xfail(raises=(ImportError, NameError), reason="Frontend not yet implemented")
def test_compile_linear_dependency():
    """
    Tests compiling two tasks where one depends on the other.
    Asserts: The resulting IR has two nodes and one connecting edge.
    """
    @task
    def upstream(data: str):
        return data.upper()

    @task
    def downstream():
        return "source"

    target = upstream(downstream())
    frontend = Frontend()
    graph_ir: GraphIR = frontend.compile(target)

    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 2
    assert len(graph_ir.edges) == 1

    # Find nodes by name for easier assertion
    node_map = {n.definition.name: n for n in graph_ir.nodes}
    assert "upstream" in node_map
    assert "downstream" in node_map

    edge = graph_ir.edges[0]
    assert isinstance(edge, EdgeIR)
    
    # Verify the edge direction and argument name
    assert edge.source_id == node_map["downstream"].id
    assert edge.target_id == node_map["upstream"].id
    assert edge.target_arg == "data" # Matches the parameter name in 'upstream'
~~~~~

### 下一步建议
我们已经成功地为编译器前端设置了 TDD 的 "RED" 状态。下一步是进入 "GREEN" 状态：
1.  在 `packages/cascade-compiler/src/cascade/compiler/` 中创建 `frontend.py`。
2.  实现 `Frontend` 类及其 `compile` 方法，使其能够处理 `LazyResult` 并生成正确的 `GraphIR`，从而让刚刚创建的测试通过。

你可以运行以下命令来确认当前的失败状态：

~~~~~act
echo
~~~~~
~~~~~
uv run pytest packages/cascade-compiler/
~~~~~
