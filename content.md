这是一个实现 **任务 1.2: `cs.subflow`** 的构建计划。

我们将引入 `cs.subflow` 提供者，它允许用户动态加载外部 Python 文件中定义的 `LazyResult`，并在一个隔离的 `Engine` 实例中执行它。这是实现“组合优于封装”原则的关键机制。

## [WIP] feat(providers): Implement `cs.subflow` for modular workflows

### 用户需求
1.  实现 `cs.subflow(path, target, params)` 提供者。
2.  该提供者应动态加载 `path` 指定的 Python 模块。
3.  它应从该模块中提取名为 `target` 的变量（通常是一个 `LazyResult`）。
4.  它应在一个**新的、隔离的** `Engine` 实例中执行该目标，并将 `params` 传递给子引擎。
5.  子流程的执行结果应作为 `cs.subflow` 任务的返回值。

### 评论
`cs.subflow` 是 Cascade 实现模块化和复用的核心。与传统的函数调用不同，`subflow` 在运行时动态组装和执行计算图。这种“隔离执行”模式确保了子流程的独立性，避免了全局状态污染，同时也为未来可能的远程执行或分布式执行奠定了基础。

### 目标
1.  创建 `src/cascade/providers/subflow.py`，实现动态加载和隔离执行逻辑。
2.  在 `pyproject.toml` 中注册 `subflow` 入口点。
3.  创建集成测试，验证父流程能否正确调用子流程并获取结果。

### 基本原理
我们利用 Python 的 `importlib` 机制来动态加载模块。为了保证执行的独立性，我们在 `_subflow_task` 内部实例化了一个全新的 `Engine`。这意味着子流程拥有自己的事件总线、资源管理器和参数解析上下文。这是一种“Engine-in-a-Task”的模式。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #scope/api #task/domain/core #task/object/subflow-provider #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 `cs.subflow` 提供者

我们将创建 `src/cascade/providers/subflow.py`。该实现包含文件加载逻辑和内嵌的 Engine 执行逻辑。

~~~~~act
write_file
src/cascade/providers/subflow.py
~~~~~
~~~~~python
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus


class SubflowProvider(Provider):
    name = "subflow"

    def create_factory(self) -> LazyFactory:
        return _subflow_task


@task(name="subflow")
async def _subflow_task(
    path: str, target: str, params: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Dynamically loads a workflow from a file and executes it in an isolated engine.

    Args:
        path: Path to the Python file containing the workflow definition.
        target: The variable name in the module that holds the LazyResult (or callable).
        params: Parameters to inject into the sub-workflow.
    """
    # 1. Validate and Load Module
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Subflow file not found: {file_path}")

    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for subflow file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"Error executing subflow definition file '{file_path}': {e}")

    # 2. Extract Target
    target_obj = getattr(module, target, None)
    if target_obj is None:
        raise ValueError(f"Target '{target}' not found in {file_path}")

    # 3. Create Isolated Engine
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus.
    # For now, subflow logs are not forwarded to the parent bus to keep things clean.
    # Errors will propagate as exceptions.
    sub_bus = MessageBus()
    sub_engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=sub_bus,
        # TODO: Consider passing system_resources from parent?
        # For now, use default (unlimited) or let OS handle resource contention.
    )

    # 4. Execute
    return await sub_engine.run(target_obj, params=params)
~~~~~

#### Acts 2: 注册入口点

在 `pyproject.toml` 中添加 `subflow` 的注册信息。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
"http.request" = "cascade.providers.http:HttpRequestProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
~~~~~
~~~~~toml
"http.request" = "cascade.providers.http:HttpRequestProvider"
subflow = "cascade.providers.subflow:SubflowProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
~~~~~

#### Acts 3: 添加集成测试

我们将创建一个测试，该测试会动态生成一个 Python 文件作为子流程，然后尝试调用它。

~~~~~act
write_file
tests/providers/test_subflow.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.fixture
def subflow_file(tmp_path):
    """Creates a temporary python file defining a subflow."""
    p = tmp_path / "my_flow.py"
    content = """
import cascade as cs

# Define a parameter
multiplier = cs.Param("multiplier", default=1)

@cs.task
def process(val, m):
    return val * m

# Define the workflow
result_node = process(10, multiplier)
"""
    p.write_text(content)
    return str(p)


@pytest.mark.asyncio
async def test_subflow_execution(subflow_file):
    """Test calling a subflow with parameters."""
    
    # Define a parent workflow that calls the subflow
    # subflow is loaded via provider registry
    sub_result = cs.subflow(
        path=subflow_file,
        target="result_node",
        params={"multiplier": 5}
    )

    @cs.task
    def finalize(val):
        return f"Final: {val}"

    workflow = finalize(sub_result)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    
    # 10 * 5 = 50 -> "Final: 50"
    result = await engine.run(workflow)
    
    assert result == "Final: 50"


@pytest.mark.asyncio
async def test_subflow_file_not_found():
    """Test error handling for missing file."""
    
    workflow = cs.subflow(path="non_existent.py", target="foo")
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    
    with pytest.raises(FileNotFoundError):
        await engine.run(workflow)


@pytest.mark.asyncio
async def test_subflow_target_not_found(subflow_file):
    """Test error handling for missing target variable."""
    
    workflow = cs.subflow(path=subflow_file, target="missing_var")
    
    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    
    with pytest.raises(ValueError, match="Target 'missing_var' not found"):
        await engine.run(workflow)
~~~~~

### 下一步建议
我们已经拥有了强大的 IO/Net 基础 (`cs.io`, `cs.http`) 和模块化机制 (`cs.subflow`)。
接下来的第三阶段是 **验证组合模式**。我们将以 `LLM` 调用为例，不编写任何新的 Python 代码（除了示例本身），仅通过组合 `cs.template`, `cs.http`, `cs.param` 和 `cs.subflow` 来构建一个功能完整的 OpenAI 客户端模式。这将证明我们架构设计的有效性。
