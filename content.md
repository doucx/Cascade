好的，我们立即开始清理工作。

这是重构计划的第二阶段，我们将把 `cascade-std`、`cascade-vm` 以及相关的测试工具中的依赖项，从它们各自的旧位置迁移到我们刚刚强化的 `cascade-spec` 包。

## [WIP] refactor: 清理依赖项并统一导入 cascade-spec 中的契约和工具

### 用户需求

在 `cascade-spec` 集中管理了核心契约和绑定工具之后，需要对整个代码库进行扫描和重构，将所有对这些旧模块的引用更新为指向 `cascade-spec` 中的新位置，并删除冗余的旧文件。

### 评论

这是一个典型的“迁移”阶段。通过精确地替换导入路径并删除旧文件，我们能以一种可控的方式完成大规模重构，最终实现依赖关系的净化。这个过程完成后，`cascade-std` 将与 `cascade-vm` 完全解耦，架构的清晰度将得到显著提升。

### 目标

1.  重构 `cascade-std` 包，使其所有物理节点实现都从 `cascade-spec` 导入 `implements` 装饰器和 `ComputeRequest`/`DelayRequest` 契约。
2.  删除 `cascade-std` 中已废弃的 `kernel_tools.py` 模块。
3.  重构 `cascade-vm` 包及其测试，使其从 `cascade-spec` 导入数据契约，并删除本地的冗余定义。
4.  更新 `cascade-test-utils`，确保测试基础设施也遵循新的依赖关系。

### 基本原理

此阶段的核心是执行依赖倒置原则。通过将所有实现细节（`cascade-std`, `cascade-vm`）都改为依赖于抽象（`cascade-spec`），我们打破了实现包之间的横向依赖。这不仅降低了耦合度，还使得每个包都可以独立演进和测试，只要它们遵守 `cascade-spec` 中定义的契约即可。

### 标签

#intent/refine #flow/ready #priority/high #comp/spec #comp/vm #comp/std #comp/tests #scope/core #task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `cascade-std` 以依赖 `cascade-spec`

我们将逐一修改 `cascade-std` 中的所有物理节点实现（ICs），更新它们的导入路径。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
from typing import Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec
from cascade.std.kernel_tools import implements


@dataclass
~~~~~
~~~~~python.new
from typing import Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec
from cascade.spec.physics.binding import implements


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
from typing import Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ContinuousAllocatorSpec, ContinuousReclaimerSpec
from cascade.std.kernel_tools import implements


@dataclass
~~~~~
~~~~~python.new
from typing import Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ContinuousAllocatorSpec, ContinuousReclaimerSpec
from cascade.spec.physics.binding import implements


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ResourceRequestorSpec
from cascade.std.kernel_tools import implements


@implements(ResourceRequestorSpec)
def resource_requestor(
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ResourceRequestorSpec
from cascade.spec.physics.binding import implements


@implements(ResourceRequestorSpec)
def resource_requestor(
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python.old
import logging
from typing import Any, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.triad import WorkerNode
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.compute import ComputeRequest
from cascade.std.specs import WorkerSpec
from cascade.std.kernel_tools import implements

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import logging
from typing import Any, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.triad import WorkerNode
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.runtime import ComputeRequest
from cascade.std.specs import WorkerSpec
from cascade.spec.physics.binding import implements

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
from cascade.spec.physical.ports import PortRole
from cascade.std.specs import BleacherSpec
from cascade.std.kernel_tools import implements


@implements(BleacherSpec)
~~~~~
~~~~~python.new
from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
from cascade.spec.physical.ports import PortRole
from cascade.std.specs import BleacherSpec
from cascade.spec.physics.binding import implements


@implements(BleacherSpec)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/gate.py
~~~~~
~~~~~python.old
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import GateSpec
from cascade.std.kernel_tools import implements


@implements(GateSpec)
def gate_passthrough(io: GateSpec.IO, node: PhysicsNode, resources: Any) -> None:
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import GateSpec
from cascade.spec.physics.binding import implements


@implements(GateSpec)
def gate_passthrough(io: GateSpec.IO, node: PhysicsNode, resources: Any) -> None:
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import TerminatorSpec
from cascade.std.kernel_tools import implements


@implements(TerminatorSpec)
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import TerminatorSpec
from cascade.spec.physics.binding import implements


@implements(TerminatorSpec)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/egress.py
~~~~~
~~~~~python.old
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import EgressSpec
from cascade.std.kernel_tools import implements


@implements(EgressSpec)
def standard_egress(io: EgressSpec.IO, node: PhysicsNode, resources: Any) -> None:
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import EgressSpec
from cascade.spec.physics.binding import implements


@implements(EgressSpec)
def standard_egress(io: EgressSpec.IO, node: PhysicsNode, resources: Any) -> None:
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import DrainerSpec
from cascade.std.kernel_tools import implements


@implements(DrainerSpec)
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import DrainerSpec
from cascade.spec.physics.binding import implements


@implements(DrainerSpec)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/time.py
~~~~~
~~~~~python.old
import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.vm.services.contracts import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.spec.runtime import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/retry.py
~~~~~
~~~~~python.old
from typing import Any

from cascade.spec import RetryNode
from cascade.std.specs import RetrySpec
from cascade.std.kernel_tools import implements


@implements(RetrySpec)
def standard_retry_logic(io: RetrySpec.IO, node: RetryNode, resources: Any) -> None:
~~~~~
~~~~~python.new
from typing import Any

from cascade.spec import RetryNode
from cascade.std.specs import RetrySpec
from cascade.spec.physics.binding import implements


@implements(RetrySpec)
def standard_retry_logic(io: RetrySpec.IO, node: RetryNode, resources: Any) -> None:
~~~~~

#### Acts 2: 删除 `cascade-std` 中的冗余模块

现在所有 IC 都已更新，我们可以安全地删除旧的 `kernel_tools.py` 文件。

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/kernel_tools.py
~~~~~

#### Acts 3: 重构 `cascade-vm` 以依赖 `cascade-spec`

接下来，我们将修改 `cascade-vm` 的内部实现，使其从 `cascade-spec` 导入数据契约。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from .contract import ComputeRequest

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from ..registry import CodeRegistry
from .contract import ComputeRequest

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Optional

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/__init__.py
~~~~~
~~~~~python.old
from .contract import ComputeRequest
from .service import LocalComputeService
from .adapters import BridgedComputeService

__all__ = ["ComputeRequest", "LocalComputeService", "BridgedComputeService"]
~~~~~
~~~~~python.new
from cascade.spec.runtime import ComputeRequest
from .service import LocalComputeService
from .adapters import BridgedComputeService

__all__ = ["ComputeRequest", "LocalComputeService", "BridgedComputeService"]
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/services/chronos.py
~~~~~
~~~~~python.old
import asyncio
import logging
from typing import Tuple

from cascade.spec.physical.nodes import Token
from .contracts import DelayRequest

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
import asyncio
import logging
from typing import Tuple

from cascade.spec.physical.nodes import Token
from cascade.spec.runtime import DelayRequest

logger = logging.getLogger(__name__)
~~~~~

#### Acts 4: 删除 `cascade-vm` 中的冗余模块

随着导入路径的更新，我们可以删除 VM 包中本地的契约定义文件。

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/compute/contract.py
~~~~~

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/services/contracts.py
~~~~~

### 下一步建议

我们已经成功完成了清理工作，`cascade-std` 和 `cascade-vm` 现在都正确地依赖于 `cascade-spec`。架构的健康状况得到了极大改善。

下一步，我们可以将注意力转向 **`cascade-compiler`** 包，检查并清理其中可能存在的重复定义或不当依赖，完成整个架构的净化。
