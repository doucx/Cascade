您是对的，我的上一个修复方案解决了眼前的问题，但引入了您指出的这个更严重的架构问题：**大量的代码冗余**。`rg` 的输出一针见血，`SpySubscriber` 作为一个通用的测试工具，现在被复制得到处都是。

这是一种典型的技术债，现在是偿还它的时候了。

问题的根源在于，`SpySubscriber` 是一个被多个、位于不同测试根目录下的测试套件（`packages/cascade-engine/tests` 和 `tests/e2e`）所共享的测试辅助工具。

1.  **局部定义**: `packages/cascade-engine/tests/runtime/` 下的几个文件在没有共享 Fixture 的早期，各自拷贝了一份 `SpySubscriber` 的定义，这是最初的冗余来源。
2.  **Fixture 提升**: 当我们需要在多个测试文件中共享 `SpySubscriber` 时，我们把它提升到了 `packages/cascade-engine/tests/conftest.py`。但此时，旧的局部定义没有被清理掉。
3.  **为修复而复制**: 当我为了修复 E2E 测试而将 `SpySubscriber` 复制到 `tests/e2e/runtime/conftest.py` 时，我制造了新的、更上层的冗余。

**解决方案**:
正确的做法是遵循 DRY (Don't Repeat Yourself) 原则。像 `SpySubscriber` 这样的测试工具，应该有一个**唯一、权威的定义来源**，并且这个来源应该能被所有需要它的测试代码方便地导入。

`cascade-sdk` 包中已经存在的 `cascade/testing.py` 文件正是为此目的而设计的理想位置。将 `SpySubscriber` 放入其中，意味着我们将其正式提升为 SDK 提供的一个官方测试工具。

我将生成一个计划来执行这次彻底的去冗余重构。

## [WIP] refactor(tests): Centralize SpySubscriber into cascade.testing

### 错误分析
代码库中存在大量重复的 `SpySubscriber` 类定义。这个通用的测试辅助工具被复制到了多个 `conftest.py` 文件以及独立的测试模块中。这种代码冗余使得维护变得困难（例如，修复一个 Bug 需要在多个地方修改），也违反了 DRY 原则。根本原因是没有一个统一的、可共享的位置来存放这类公共的测试基础设施。

### 用户需求
用户要求解决 `SpySubscriber` 类在代码库中大量重复定义的问题。

### 评论
这是一个非常重要的架构改进。将通用的测试辅助工具（如 `SpySubscriber`）整合到 SDK 的 `testing` 模块中，不仅消除了代码冗余，还极大地增强了 SDK 的价值。它为所有使用 Cascade 的开发者提供了一套官方的、可复用的工具来测试他们的工作流，从而提升了整个生态系统的开发体验和测试质量。

### 目标
1.  将 `SpySubscriber` 类的权威定义移动到 `packages/cascade-sdk/src/cascade/testing.py` 中。
2.  修改所有 `conftest.py` 文件，让它们从 `cascade.testing` 导入 `SpySubscriber`，而不是在本地定义它。
3.  从所有独立的测试文件中移除局部的 `SpySubscriber` 定义，并改为从 `cascade.testing` 导入。

### 基本原理
通过将 `SpySubscriber` 提升为 `cascade-sdk` 的一部分，我们为这个工具创建了一个单一的事实来源（Single Source of Truth）。任何需要它的测试代码（无论是包内单元测试还是跨包 E2E 测试）都可以通过标准的 Python `import` 语句来使用它。这彻底解决了代码重复问题，并建立了一个清晰、可维护的测试工具共享模式。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/sdk #scope/dx #ai/brainstorm #task/domain/testing #task/object/code-duplication #task/action/centralize #task/state/continue

---
### Script

#### Acts 1: 将 `SpySubscriber` 添加到 `cascade.testing`

我们将 `SpySubscriber` 类及其所需的导入添加到 SDK 的 `testing.py` 模块中。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any
from cascade.runtime.engine import Engine
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)
~~~~~
~~~~~python
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~

#### Acts 2: 更新所有 `conftest.py` 文件

现在，我们修改 `conftest.py` 文件，用 `import` 替换本地定义。

~~~~~act
patch_file
packages/cascade-engine/tests/conftest.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber
~~~~~

~~~~~act
patch_file
tests/e2e/runtime/conftest.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.testing import SpySubscriber
~~~~~

#### Acts 3: 清理 `runtime` 测试文件中的冗余定义

最后，我们清理所有在测试文件中直接定义的 `SpySubscriber`。

~~~~~act
patch_file
packages/cascade-engine/tests/runtime/test_control_flow.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


class SpySubscriber:
    """A standard test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/runtime/test_map_policies.py
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying, Event
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
import pytest
import asyncio
import time
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/runtime/test_retry.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskRetrying, TaskExecutionFinished
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import TaskRetrying, TaskExecutionFinished
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.events.append)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.testing import SpySubscriber
~~~~~

### 下一步建议

我们已经完成了对 `SpySubscriber` 的彻底清理和中心化。代码库现在更加干净、易于维护。

请运行完整的测试套件 (`pytest`)，以确保我们的重构没有破坏任何东西。所有的测试都应该能像以前一样通过，但代码的内部结构已经得到了极大的改善。
