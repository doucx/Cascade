好的，测试全部通过，VM 的核心执行链路已经打通。现在我们来实现通过环境变量切换默认后端的功能。

这是一个非常好的开发者体验（DX）改进，它允许我们在不修改任何代码的情况下，轻松地在传统的图执行策略和新的 VM 执行策略之间进行切换，便于测试和性能对比。

我将生成一个计划来实现这个功能。

## [WIP] feat: 通过环境变量 CASCADE_BACKEND 切换默认执行策略

### 错误分析
无错误，此为新功能实现。

### 用户需求
当环境变量 `CASCADE_BACKEND` 被设置为 `vm` 时，`Engine` 实例在未指定 `strategy` 参数的情况下，应自动加载并使用 `VMExecutionStrategy` 作为其默认执行策略。如果环境变量未设置或设置为其他值，则应保持现有的默认行为（加载基于图的策略）。

### 评论
这是一个重要的工程实践，它将运行时的行为与环境配置解耦，极大地增强了系统的灵活性和可测试性。通过支持 `CASCADE_BACKEND=vm`，我们为未来将 VM 作为默认后端铺平了道路，同时保留了与旧版执行器的兼容性。

### 目标
1.  修改 `Engine` 的 `__init__` 方法，使其在初始化时检查 `CASCADE_BACKEND` 环境变量。
2.  实现一个新的私有方法 `_resolve_default_strategy`，根据环境变量的值来决定加载哪个策略。
3.  创建一个 `_load_vm_strategy` 方法，负责实例化 `VMExecutionStrategy`。
4.  将现有的 `_load_default_strategy` 重命名为 `_load_graph_strategy`，以明确其职责，并作为默认的回退选项。

### 基本原理
我们将在 `Engine` 的构造函数中引入一个决策点。该决策点将优先使用用户显式传入的 `strategy`。如果没有，它将查询 `os.getenv("CASCADE_BACKEND")`。如果值为 `'vm'`，则调用 VM 策略加载器；否则，调用传统的图策略加载器。这种方式清晰地隔离了不同策略的加载逻辑，并确保了向后兼容性。

### 标签
#intent/build #flow/ready #priority/medium #comp/runtime #concept/config #scope/dx #ai/instruct #task/domain/runtime #task/object/engine-strategy #task/action/configure #task/state/begin

---

### Script

#### Acts 1: 修改 Engine 以支持后端切换

我们将对 `packages/cascade-runtime/src/cascade/runtime/host/instance.py` 文件进行一次集中的 `patch` 操作。这次修改将包括：
1.  导入 `os` 和 `VMExecutionStrategy`。
2.  更新 `__init__` 方法以调用新的策略解析器 `_resolve_default_strategy`。
3.  添加 `_resolve_default_strategy` 和 `_load_vm_strategy` 方法。
4.  重命名 `_load_default_strategy` 为 `_load_graph_strategy`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.dsl.resources import ResourceDefinition
~~~~~
~~~~~python.new
import os
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.dsl.resources import ResourceDefinition
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
        self.resource_container = ResourceContainer(self.bus)

        if strategy:
            self.strategy = strategy
        else:
            self.strategy = self._load_default_strategy()

        self._managed_subscribers = []

    def _load_default_strategy(self) -> ExecutionStrategy:
        try:
            # Dynamic imports to break hard dependency
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            # Reconstruct the legacy stack
            node_processor = NodeProcessor(
                executor=self.executor,
                bus=self.bus,
                resource_manager=self.resource_manager,
                constraint_manager=self.constraint_manager,
                solver=self.solver,
            )

            return GraphExecutionStrategy(
                solver=self.solver,
                node_processor=node_processor,
                resource_container=self.resource_container,
                constraint_manager=self.constraint_manager,
                bus=self.bus,
                wakeup_event=self._wakeup_event,
            )
        except ImportError:
            raise RuntimeError(
                "No execution strategy provided and 'cascade-execution-graph' package not found. "
                "Please install 'cascade-execution-graph' or provide a custom strategy."
            )
~~~~~
~~~~~python.new
        self.resource_container = ResourceContainer(self.bus)

        if strategy:
            self.strategy = strategy
        else:
            self.strategy = self._resolve_default_strategy()

        self._managed_subscribers = []

    def _resolve_default_strategy(self) -> ExecutionStrategy:
        backend_choice = os.getenv("CASCADE_BACKEND", "graph").lower()
        if backend_choice == "vm":
            return self._load_vm_strategy()
        else:
            return self._load_graph_strategy()

    def _load_vm_strategy(self) -> ExecutionStrategy:
        from cascade.runtime.strategies.vm import VMExecutionStrategy

        return VMExecutionStrategy(executor=self.executor, bus=self.bus)

    def _load_graph_strategy(self) -> ExecutionStrategy:
        try:
            # Dynamic imports to break hard dependency
            from cascade.execution.graph.logic.processor import NodeProcessor
            from cascade.execution.graph.strategy import GraphExecutionStrategy

            # Reconstruct the legacy stack
            node_processor = NodeProcessor(
                executor=self.executor,
                bus=self.bus,
                resource_manager=self.resource_manager,
                constraint_manager=self.constraint_manager,
                solver=self.solver,
            )

            return GraphExecutionStrategy(
                solver=self.solver,
                node_processor=node_processor,
                resource_container=self.resource_container,
                constraint_manager=self.constraint_manager,
                bus=self.bus,
                wakeup_event=self._wakeup_event,
            )
        except ImportError:
            raise RuntimeError(
                "No execution strategy provided and 'cascade-execution-graph' package not found. "
                "Please install 'cascade-execution-graph' or provide a custom strategy."
            )
~~~~~

### 下一步建议

功能已经实现，但我们还没有为它编写测试。我建议下一步是创建一个新的测试文件 `packages/cascade-runtime/tests/unit/host/test_engine_init.py`，并在其中添加一个测试用例，该用例使用 `monkeypatch` 来设置 `CASCADE_BACKEND` 环境变量，然后断言 `Engine` 实例化的 `strategy` 属性是我们期望的类型（`VMExecutionStrategy` 或 `GraphExecutionStrategy`）。

这将确保我们的新功能是健壮且可维护的。如果你同意，我将生成创建该测试的计划。
