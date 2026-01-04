好的，我将开始执行这项重构任务。

根据你的指示，我将严格限定操作范围，仅修改 `packages/cascade-engine/src` 目录下的文件，将 `MessageBus` 重命名为 `EventBus`，并更新所有内部引用。

这是一个 [WIP] 计划，专注于核心代码的重构。

## [WIP] refactor(engine): 将运行时的 MessageBus 重命名为 EventBus

### 用户需求

将 `cascade-engine` 包中的 `MessageBus` 类及其文件名重命名为 `EventBus`，以解决与 `cascade-common` 中的 `MessageBus` 的命名冲突，并提高代码的语义清晰度。

### 评论

这是一个关键的架构改进。它消除了一个主要的歧义来源，使得内部事件系统（Engine's EventBus）和面向用户的反馈系统（Common's MessageBus）之间的区别变得清晰明确。此举将显著提升代码的可读性和可维护性。

### 目标

1.  将 `packages/cascade-engine/src/cascade/runtime/bus.py` 重命名为 `event_bus.py`。
2.  将 `packages/cascade-engine/src/cascade/runtime/bus.stitcher.yaml` 重命名为 `event_bus.stitcher.yaml`。
3.  更新新文件中 `MessageBus` 类的定义为 `EventBus`。
4.  更新 `cascade.runtime` 的 `__init__.py` 以导出新的 `EventBus`。
5.  更新 `cascade-engine` 包内所有对旧 `MessageBus` 的引用，使其指向新的 `EventBus`。

### 基本原理

我们将采用一个分阶段的原子化重构流程：
1.  **重命名核心文件**: 首先对 `bus.py` 和 `bus.stitcher.yaml` 进行重命名，建立新的规范位置。
2.  **更新核心定义**: 修改新文件中的类名和文档字符串，使其与新文件名保持一致。
3.  **更新模块 API**: 修改 `runtime/__init__.py`，确保模块的公共接口反映了这一变化。
4.  **更新内部消费者**: 最后，逐一修改 `cascade-engine` 包内部所有使用到该总线的模块，将它们的导入和类型注解更新为 `EventBus`。

这种方法确保了变更的逻辑性和完整性，每一步都建立在前一步的基础上。

### 标签

#intent/refine #flow/ready #priority/high #comp/engine #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/message-bus #task/action/rename #task/state/begin

---

### Script

#### Acts 1: 重命名核心文件

首先，我们将 `bus.py` 和 `bus.stitcher.yaml` 重命名为 `event_bus.py` 和 `event_bus.stitcher.yaml`。

~~~~~act
move_file
packages/cascade-engine/src/cascade/runtime/bus.py
packages/cascade-engine/src/cascade/runtime/event_bus.py
~~~~~

~~~~~act
move_file
packages/cascade-engine/src/cascade/runtime/bus.stitcher.yaml
packages/cascade-engine/src/cascade/runtime/event_bus.stitcher.yaml
~~~~~

#### Acts 2: 更新重命名后的文件内容

现在，更新新文件中的类名和文档内容。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/event_bus.py
~~~~~
~~~~~python
from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from .events import Event

# Define a Handler type alias for clarity
Handler = Callable[[Any], None]


class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Handler]] = defaultdict(list)
        self._wildcard_subscribers: List[Handler] = []

    def subscribe(self, event_type: Type[Event], handler: Handler):
        if event_type is Event:
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        # 1. Dispatch to handlers explicitly subscribed to this event type
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)

        # 2. Dispatch to wildcard handlers (subscribed to Event)
        for handler in self._wildcard_subscribers:
            handler(event)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/event_bus.stitcher.yaml
~~~~~
~~~~~yaml.old
"MessageBus": |-
  A simple in-memory message bus for dispatching events to subscribers.
"MessageBus.publish": |-
  Dispatch an event to all relevant subscribers.
"MessageBus.subscribe": |-
  Register a handler for a specific event type.
~~~~~
~~~~~yaml.new
"EventBus": |-
  A simple in-memory event bus for dispatching events to subscribers.
"EventBus.publish": |-
  Dispatch an event to all relevant subscribers.
"EventBus.subscribe": |-
  Register a handler for a specific event type.
~~~~~

#### Acts 3: 更新模块的 `__init__.py`

更新 `runtime` 模块的公共 API，导出 `EventBus`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/__init__.py
~~~~~
~~~~~python.old
from .bus import MessageBus
from .engine import Engine
from .subscribers import HumanReadableLogSubscriber
from .events import Event
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from cascade.spec.protocols import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
    "MessageBus",
    "Engine",
~~~~~
~~~~~python.new
from .event_bus import EventBus
from .engine import Engine
from .subscribers import HumanReadableLogSubscriber
from .events import Event
from .exceptions import DependencyMissingError
from .resource_manager import ResourceManager
from cascade.spec.protocols import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
    "EventBus",
    "Engine",
~~~~~

#### Acts 4: 更新 `cascade-engine` 内部的消费者

逐一更新包内所有使用 `MessageBus` 的地方。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
~~~~~
~~~~~python.new
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.spec.resource import ResourceDefinition
from cascade.spec.constraint import GlobalConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.event_bus import EventBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
~~~~~
~~~~~python.new
class Engine:
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: EventBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python.old
from cascade.spec.protocols import Executor, StateBackend, Solver
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
~~~~~
~~~~~python.new
from cascade.spec.protocols import Executor, StateBackend, Solver
from cascade.runtime.event_bus import EventBus
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python.old
class NodeProcessor:
    def __init__(
        self,
        executor: Executor,
        bus: MessageBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
~~~~~
~~~~~python.new
class NodeProcessor:
    def __init__(
        self,
        executor: Executor,
        bus: EventBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.graph.registry import NodeRegistry
from cascade.reflection import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
~~~~~
~~~~~python.new
from cascade.graph.registry import NodeRegistry
from cascade.reflection import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.jump import Jump
from cascade.runtime.event_bus import EventBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
~~~~~
~~~~~python.new
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: EventBus,
        wakeup_event: asyncio.Event,
    ):
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python.old
import platform
import os
import asyncio
from datetime import datetime, timezone
from .bus import MessageBus
from cascade.common.messaging import bus
from .events import (
~~~~~
~~~~~python.new
import platform
import os
import asyncio
from datetime import datetime, timezone
from .event_bus import EventBus
from cascade.common.messaging import bus
from .events import (
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python.old
class HumanReadableLogSubscriber:
    def __init__(self, event_bus: MessageBus):
        # Subscribe to relevant events from the core event_bus
        event_bus.subscribe(RunStarted, self.on_run_started)
        event_bus.subscribe(RunFinished, self.on_run_finished)
~~~~~
~~~~~python.new
class HumanReadableLogSubscriber:
    def __init__(self, event_bus: EventBus):
        # Subscribe to relevant events from the core event_bus
        event_bus.subscribe(RunStarted, self.on_run_started)
        event_bus.subscribe(RunFinished, self.on_run_finished)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python.old
class TelemetrySubscriber:
    def __init__(self, event_bus: MessageBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
~~~~~
~~~~~python.new
class TelemetrySubscriber:
    def __init__(self, event_bus: EventBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python.old
from contextlib import ExitStack
from typing import Any, Dict, Callable, Union, Generator, Set

from cascade.graph.model import Graph
from cascade.spec.resource import ResourceDefinition, Inject
from contextlib import contextmanager

from cascade.runtime.bus import MessageBus
from cascade.runtime.events import ResourceAcquired, ResourceReleased
~~~~~
~~~~~python.new
from contextlib import ExitStack
from typing import Any, Dict, Callable, Union, Generator, Set

from cascade.graph.model import Graph
from cascade.spec.resource import ResourceDefinition, Inject
from contextlib import contextmanager

from cascade.runtime.event_bus import EventBus
from cascade.runtime.events import ResourceAcquired, ResourceReleased
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python.old
class ResourceContainer:
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}
~~~~~
~~~~~python.new
class ResourceContainer:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}
~~~~~

### 下一步建议

我们已经成功将 `cascade-engine` 内部的 `MessageBus` 重构为 `EventBus`。下一步，我建议：
1.  **提交变更**: 创建一个 `[COMMIT]` 计划，将这些修改作为一个独立的、逻辑完整的单元提交到版本控制中。
2.  **重构 `cascade-common`**: 接着，我们可以开始第二阶段的重构，将 `cascade-common` 中的 `MessageBus` 重命名为 `FeedbackBus` 或其他合适的名称，以彻底解决命名冲突问题。

如果你同意，我将为你生成 `[COMMIT]` 计划。
