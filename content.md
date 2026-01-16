我也收到了关于 `cascade-vm` 包的强耦合检查报告。

在 `cascade-vm` 中，`compute` 子包及其服务类（`LocalComputeService`, `BridgedComputeService`）之间存在明显的绝对导入导致的循环依赖。例如，`adapters.py` 尝试通过 `cascade.vm.compute.contract` 导入 `ComputeRequest`，这会在 `cascade.vm.compute` 包初始化期间触发对自身的再次加载。

我将按照相同的逻辑，将 `cascade-vm` 内部的所有绝对导入重构为相对导入，以彻底消除这些循环路径。

## [WIP] refactor: 解耦 cascade-vm 包内的循环依赖，将绝对导入改为相对导入

### 用户需求
修复 `cascade-vm` 包内发现的强耦合组件问题，通过将绝对导入改为相对导入来消除子包间的循环依赖。

### 评论
与 `cascade-spec` 类似，`cascade-vm` 作为执行核心，其内部组件（如 Reactor, Machine, ComputeService）之间的引用非常频繁。使用绝对导入不仅增加了循环依赖的风险，还使得包在动态加载环境下的表现不够健壮。通过相对导入，我们能够确保导入链始终限制在当前的物理目录结构内，避免触发不必要的包根初始化。

### 目标
1. 修复 `cascade.vm.compute` 子包内的循环引用。
2. 修复 `cascade.vm.kernel`, `cascade.vm.services` 以及根模块（`reactor.py`, `machine.py`）中的绝对导入。
3. 确保 VM 的核心逻辑（如物理内核驱动和计算任务分发）能够正常初始化。

### 基本原理
相对导入（`.`, `..`）直接利用 Python 的模块命名空间层级，而不通过 `sys.path` 重新查找。这对于解决由于子模块引用父包定义的类型（或反之）而导致的 `Partially Initialized Module` 错误至关重要。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/vm #task/object/vm-package #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修复 `cascade.vm.compute` 子包的导入

我们将 `adapters.py` 和 `service.py` 中指向同级或父级的绝对导入改为相对导入。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.contract import ComputeRequest
~~~~~
~~~~~python.new
from ..registry import CodeRegistry
from .contract import ComputeRequest
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.contract import ComputeRequest
~~~~~
~~~~~python.new
from ..registry import CodeRegistry
from .contract import ComputeRequest
~~~~~

#### Acts 2: 修复 `cascade.vm.kernel` 和 `cascade.vm.services` 的导入

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/kernel/core.py
~~~~~
~~~~~python.old
from cascade.vm.resource_registry import ResourceRegistry
~~~~~
~~~~~python.new
from ..resource_registry import ResourceRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/services/chronos.py
~~~~~
~~~~~python.old
from cascade.vm.services.contracts import DelayRequest
~~~~~
~~~~~python.new
from .contracts import DelayRequest
~~~~~

#### Acts 3: 修复 `cascade.vm` 根级模块的导入

修复 `machine.py` 和 `reactor.py` 中的交叉引用。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
from cascade.vm.services.chronos import ChronosService
~~~~~
~~~~~python.new
from .services.chronos import ChronosService
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from cascade.vm.memory import VolatileMemory
from cascade.vm.kernel import PhysicsKernel
~~~~~
~~~~~python.new
from .memory import VolatileMemory
from .kernel import PhysicsKernel
~~~~~

### 下一步建议
1. **引导检查**: 尝试运行 `python3 -c "from cascade.vm.machine import Machine; print('Import OK')"` 来验证核心组件的加载。
2. **集成测试**: 重点运行物理引擎的集成测试（如果存在），确保 Reactor 能够正确调用 Kernel 并且 Machine 能够正确驱动 Services。
3. **继续重构**: 报告中还提到了 `cascade-compiler` 的 16 个文件强耦合组件，那是接下来的重构重点。
