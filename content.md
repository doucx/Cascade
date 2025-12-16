简要回答
好的，这是为您准备的 TDD 测试实现计划。它将创建和更新一系列测试文件，以定义 Cascade v1.3 重构后的预期行为。

## [WIP] test: 添加 v1.3 重构的 TDD 测试用例

### 用户需求
实施 TDD 流程的第一步：编写针对 Cascade v1.3 架构重构（同构图模型、输入契约解耦、FlowManager）的测试用例。这些测试将引用尚未存在的模块（如 `cascade.context`），从而确立重构的目标。

### 评论
这是一个教科书式的 TDD 开局。我们正在通过代码明确定义 v1.3 的行为契约。这些测试在当前代码库上运行将必然失败（主要也是因为 ImportError），这将作为我们后续实现工作的红灯（Red Light）。

### 目标
1.  定义 `WorkflowContext` 和 `InputSpec` 的注册行为。
2.  定义同构图构建行为（`Param` 变为标准 `Task`）。
3.  定义 `Engine` 执行内部参数获取任务的行为。
4.  定义 `cs.cli` 基于上下文而非图的生成行为。
5.  定义 `FlowManager` 的动态剪枝逻辑。

### 基本原理
通过预先编写测试，我们强制解耦了设计与实现，确保新的架构边界（如 `cs.cli` 不依赖图构建）得到严格遵守。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/core #ai/instruct
#task/domain/core #task/object/v1.3-refactor #task/action/tdd-setup #task/state/begin

---

### Script

#### Acts 1: 定义输入契约与上下文测试
创建测试以验证新的 `InputSpec` 体系和 `WorkflowContext` 注册机制。

~~~~~act
write_file
tests/spec/test_input_context.py
~~~~~
~~~~~python
import pytest
from cascade.context import get_current_context, WorkflowContext
from cascade.spec.input import ParamSpec, EnvSpec

def test_context_isolation():
    """验证上下文是隔离的。"""
    ctx1 = WorkflowContext()
    ctx2 = WorkflowContext()
    
    spec = ParamSpec(name="p1")
    ctx1.register(spec)
    
    assert len(ctx1.get_all_specs()) == 1
    assert len(ctx2.get_all_specs()) == 0

def test_param_factory_registration():
    """验证调用 cs.Param() 会自动注册 spec 到全局上下文。"""
    import cascade as cs
    
    # 获取并清理上下文
    ctx = get_current_context()
    # 模拟清理方法，具体实现待定
    if hasattr(ctx, "input_specs"):
        ctx.input_specs.clear()
    
    # 调用工厂函数
    result = cs.Param("env", default="dev", description="Environment")
    
    # 1. 验证注册
    specs = ctx.get_all_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert isinstance(spec, ParamSpec)
    assert spec.name == "env"
    assert spec.default == "dev"
    assert spec.description == "Environment"
    
    # 2. 验证返回类型 (不再是 Param 对象，而是 LazyResult)
    from cascade.spec.lazy_types import LazyResult
    assert isinstance(result, LazyResult)
    # 验证内部任务名称
    assert result.task.name == "_get_param_value"

def test_env_factory_registration():
    """验证调用 cs.Env() 的行为。"""
    import cascade as cs
    ctx = get_current_context()
    if hasattr(ctx, "input_specs"):
        ctx.input_specs.clear()
    
    result = cs.Env("API_KEY")
    
    specs = ctx.get_all_specs()
    assert len(specs) == 1
    assert isinstance(specs[0], EnvSpec)
    assert specs[0].name == "API_KEY"
    
    assert result.task.name == "_get_env_var"
~~~~~

#### Acts 2: 更新图构建测试以反映同构性
修改 `test_build.py`，断言 `Param` 和 `Env` 现在生成的是标准的 `task` 节点。

~~~~~act
write_file
tests/graph/test_build.py
~~~~~
~~~~~python
import cascade as cs
from cascade.graph.build import build_graph

def test_build_linear_graph():
    @cs.task
    def t1():
        return 1

    @cs.task
    def t2(x):
        return x + 1

    r1 = t1()
    r2 = t2(r1)

    graph = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert edge.source.name == "t1"
    assert edge.target.name == "t2"
    assert edge.arg_name == "0"  # first positional arg

def test_build_graph_with_param_factory():
    """
    [V1.3 更新] 验证 cs.Param() 现在生成一个标准的任务节点，
    而不是旧版的 'param' 类型节点。
    """
    # 定义工作流
    param_node = cs.Param("x", default=1)
    
    @cs.task
    def process(val):
        return val + 1
        
    target = process(param_node)
    
    graph = build_graph(target)
    
    assert len(graph.nodes) == 2
    
    # 找到参数节点
    # 注意：我们不能再通过 node_type="param" 来查找了
    # 我们需要通过任务名称或 ID 查找
    p_node = next(n for n in graph.nodes if n.name == "_get_param_value")
    
    # 断言节点类型统一为 task
    assert p_node.node_type == "task" 
    
    # 断言它包含正确的 literal_inputs (这是内部任务需要的参数)
    assert "name" in p_node.literal_inputs
    assert p_node.literal_inputs["name"] == "x"

def test_build_graph_with_env_factory():
    """验证 cs.Env() 生成标准任务节点。"""
    env_node = cs.Env("HOME")
    
    @cs.task
    def echo(val):
        return val
        
    target = echo(env_node)
    graph = build_graph(target)
    
    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert e_node.literal_inputs["name"] == "HOME"
~~~~~

#### Acts 3: 定义输入任务的执行逻辑
创建测试以验证 `Engine` 能够正确注入参数并执行内部获取任务。

~~~~~act
write_file
tests/runtime/test_input_execution.py
~~~~~
~~~~~python
import pytest
import cascade as cs
# 注意：在实现阶段需要确保这些模块存在
# from cascade.context import get_current_context

@pytest.mark.asyncio
async def test_engine_executes_param_task():
    """验证 Engine 能正确地将 params 注入到 _get_param_value 任务中。"""
    
    # 定义参数
    p = cs.Param("count", type=int)
    
    # 定义简单的下游任务
    @cs.task
    def double(x):
        return x * 2
        
    workflow = double(p)
    
    engine = cs.Engine()
    
    # 执行，传入 params
    # 这里的关键是 Engine 需要将 {"count": 10} 传递给 _get_param_value 任务
    result = await engine.run(workflow, params={"count": 10})
    
    assert result == 20

@pytest.mark.asyncio
async def test_engine_executes_env_task(monkeypatch):
    """验证 Engine 能正确执行 _get_env_var 任务。"""
    monkeypatch.setenv("TEST_VAR", "cascade_value")
    
    e = cs.Env("TEST_VAR")
    
    engine = cs.Engine()
    result = await engine.run(e)
    
    assert result == "cascade_value"
~~~~~

#### Acts 4: 更新 CLI 测试以反映解耦架构
重写 `test_cli.py`，验证 CLI 生成器现在基于上下文而非图结构。

~~~~~act
write_file
tests/tools/test_cli.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner
import cascade as cs
from cascade.context import get_current_context

# Skip if typer is not installed
pytest.importorskip("typer")

runner = CliRunner()

def test_cli_generator_from_context():
    """
    [V1.3 更新] 验证 CLI 生成器是从全局上下文读取 ParamSpec，
    而不是解析图结构。
    """
    # 1. 定义工作流构建函数
    # 这是一个新模式：为了让 CLI 扫描到参数，我们需要执行定义逻辑
    def workflow_def():
        # 清理上下文以确保测试隔离
        if hasattr(get_current_context(), "input_specs"):
            get_current_context().input_specs.clear()
        
        name = cs.Param("name", description="User name")
        count = cs.Param("count", default=1, type=int)
        
        @cs.task
        def greet(n, c):
            return f"Hello {n} " * c
            
        return greet(name, count)
    
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # 3. 生成 CLI
    # 注意：v1.3 cs.cli 可能既支持 LazyResult (为了兼容)，
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.cli(target) 
    
    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "User name" in result.stdout

    # 5. 验证执行
    result = runner.invoke(app, ["--name", "World", "--count", "2"])
    assert result.exit_code == 0
    # Engine logs 默认可能在 stderr
    output = result.stdout + result.stderr
    assert "Hello World Hello World" in output
~~~~~

#### Acts 5: 定义 FlowManager 的行为
创建测试以验证 `FlowManager` 的动态剪枝逻辑。

~~~~~act
write_file
tests/runtime/test_flow_manager.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.graph.model import Node, Edge, EdgeType
from cascade.runtime.flow import FlowManager

def create_mock_node(id):
    return Node(id=id, name=id)

def test_flow_manager_pruning_logic():
    """测试 FlowManager 的动态剪枝算法。"""
    
    nodes = [create_mock_node(n) for n in ["S", "A", "B", "C"]]
    n_map = {n.id: n for n in nodes}
    
    edges = [
        # S->A (route=a), S->B (route=b) via ROUTER_ROUTE
        Edge(n_map["S"], n_map["A"], arg_name="x", edge_type=EdgeType.ROUTER_ROUTE),
        Edge(n_map["S"], n_map["B"], arg_name="x", edge_type=EdgeType.ROUTER_ROUTE),
        
        # C 依赖 A (DATA)
        Edge(n_map["A"], n_map["C"], arg_name="arg_a", edge_type=EdgeType.DATA),
        # C 依赖 B (DATA)
        Edge(n_map["B"], n_map["C"], arg_name="arg_b", edge_type=EdgeType.DATA),
    ]
    
    graph = MagicMock()
    graph.nodes = nodes
    graph.edges = edges
    
    # 初始化 FlowManager
    manager = FlowManager(graph, target_node_id="C")
    
    # 模拟 Router 决定：S 完成，选择了 Route "A"，因此剪枝 B
    # 假设我们有一个内部方法 _decrement_demand_and_prune(node_id)
    if hasattr(manager, "_decrement_demand_and_prune"):
        manager._decrement_demand_and_prune("B")
        
        # 断言 B 被标记为 Skipped/Pruned
        assert manager.is_skipped("B")
        
        # C 强依赖 B，所以 C 也应该被剪枝
        assert manager.is_skipped("C")
~~~~~

### 下一步建议
运行 `pytest`。预期结果是所有测试都将失败（主要是 ImportError）。确认这一点后，我们将开始“第一阶段：基础架构与输入契约”的实现工作。
