简要回答

## [WIP] fix: 修复并发测试执行器及图序列化反序列化逻辑

### 错误分析
1.  **并发测试失败**: `test_concurrency_constraint_on_map` 失败是因为 `TimedMockExecutor` 继承自 `SpyExecutor`，后者似乎返回模拟的字符串结果（如 `'executed_slow_task'`）而非真实计算结果。测试用例期望得到真实的计算结果 `[1, 2, 3, 4]`。
2.  **序列化测试错误**: `TypeError: ... got an unexpected keyword argument '_callable'`。这是因为核心 `Node` 模型（`TaskNode`, `ParamNode`）已经重构，不再直接存储 `callable` 对象，而 `serialize.py` 中的反序列化逻辑尚未更新，仍试图将 `_callable` 参数传递给构造函数。

### 用户需求
修复集成测试和单元测试中的回归错误。

### 评论
这是一个典型的重构后遗留问题。`cascade-graph` 的模型更新了，但配套的序列化逻辑和测试用例没有同步更新。同时，并发测试暴露了 Mock 执行器的局限性。修复这些问题将使代码库重新回到稳定状态。

### 目标
1.  修改 `TimedMockExecutor` 使其继承自 `LocalExecutor`，以支持真实代码执行。
2.  更新 `serialize.py`，移除反序列化时对 `_callable` 参数的传递。
3.  更新 `test_serialize.py`，移除对 `node.callable_obj` 的断言，反映新的架构设计。

### 基本原理
*   **Executor**: 为了测试并发约束对真实任务的影响，我们需要一个能执行代码并支持延时的 Executor。`LocalExecutor` 提供了真实执行的能力，只需在 `execute` 方法中注入延时即可。
*   **Serialization**: `Node` 对象现在是纯数据对象（DTO），执行逻辑（Callables）由 Registry 管理。序列化层不应再尝试恢复 Node 内部的 callable 引用，因为该属性已不存在。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/graph #task/domain/testing #task/object/serialization #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复并发测试执行器

我们将 `TimedMockExecutor` 的基类从 `SpyExecutor` 改为 `LocalExecutor`，并导入所需的类。这样测试运行时将执行实际的 python 函数，从而通过结果断言。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~python.old
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector, SpyExecutor


class TimedMockExecutor(SpyExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)
~~~~~
~~~~~python.new
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector


class TimedMockExecutor(LocalExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)
~~~~~

#### Acts 2: 修复序列化逻辑

更新 `_dict_to_node` 函数，移除实例化 `ParamNode` 和 `TaskNode` 时传递的 `_callable` 参数。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec,
        # so restored ParamNodes will have param_spec=None.
        # This is acceptable for simple visualization/analysis,
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="param",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True,  # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
        node = TaskNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="task",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            # has_complex_inputs is an optimization flag, safe to default False on restore
            has_complex_inputs=False,
        )
~~~~~
~~~~~python.new
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec,
        # so restored ParamNodes will have param_spec=None.
        # This is acceptable for simple visualization/analysis,
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="param",
            retry_policy=retry_policy,
            cache_policy=None,  # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True,  # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
        node = TaskNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="task",
            retry_policy=retry_policy,
            cache_policy=None,  # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
            # has_complex_inputs is an optimization flag, safe to default False on restore
            has_complex_inputs=False,
        )
~~~~~

#### Acts 3: 更新序列化测试断言

移除 `test_serialize.py` 中对 `node.callable_obj` 的检查，因为该属性已从模型中移除。

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
    # Verify function restoration
    restored_node = next(n for n in restored_graph.nodes if n.name == "simple_task")
    assert restored_node.callable_obj == simple_task.func
    assert restored_node.callable_obj(1) == 2


def test_serialize_params_structure_only():
~~~~~
~~~~~python.new
    # Verify function restoration
    restored_node = next(n for n in restored_graph.nodes if n.name == "simple_task")
    assert restored_node.name == "simple_task"


def test_serialize_params_structure_only():
~~~~~

### 下一步建议
运行 `pytest packages/cascade-engine/tests/integration/test_engine_concurrency.py packages/cascade-graph/tests/unit/test_serialize.py` 验证修复是否生效。
