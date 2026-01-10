由于迁移了 `EventDrivenRunner` 但未同步更新测试用例中的导入路径，导致 Pytest 收集失败。我们需要修正所有受影响的测试文件。

## [WIP] fix: 修复因迁移 EventDrivenRunner 导致的测试收集错误

### 错误分析
在执行上一个计划时，我们物理移动了 `EventDrivenRunner` 文件的位置并删除了原有的 `cascade.vm.harness` 模块。然而，`cascade-vm` 包下的集成测试和单元测试仍然保留了对旧路径的静态引用，导致 `ModuleNotFoundError`。

### 用户需求
修复测试收集错误，确保测试套件能够正确识别新的 `EventDrivenRunner` 位置。

### 评论
在大型 Monorepo 中进行跨包重构时，打破原有物理路径是常见操作。我们需要通过更新受影响测试的导入声明来重新建立契约链接。

### 目标
1.  识别并更新 `packages/cascade-vm/tests/` 目录下所有受影响的文件。
2.  将 `from cascade.vm.harness import EventDrivenRunner` 统一修改为 `from cascade.test_utils import EventDrivenRunner`。

### 基本原理
我们已经在 `cascade-test-utils` 的 `__init__.py` 中导出了 `EventDrivenRunner`。现在只需要将测试用例的依赖从物理引擎包指向专门的测试工具包。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/vm #scope/dx
#task/domain/testing #task/object/test-suite #task/action/fix
#task/state/continue

---

### Script

#### Acts 1: 更新测试用例中的导入路径

我们将批量修复 `cascade-vm` 中所有受损的测试文件。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.vm.harness import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
~~~~~
~~~~~python.new
from cascade.runtime.services.observability.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)
from cascade.test_utils import EventDrivenRunner
from cascade.std.triad.bleacher import standard_bleacher
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python.old
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.ports import PortRole
from cascade.vm.harness import EventDrivenRunner
from cascade.runtime.services.observability.events import (
    Event,
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.ports import PortRole
from cascade.test_utils import EventDrivenRunner
from cascade.runtime.services.observability.events import (
    Event,
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_sentry.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.dsl.task import task
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.dsl.task import task
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_retry_topology.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.triad import RetryNode
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.triad import RetryNode
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
from cascade.runtime.services.observability.events import Event, TaskExecutionFinished
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
from cascade.runtime.services.observability.events import Event, TaskExecutionFinished
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.test_utils import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.object import Ref
~~~~~

### 下一步建议
测试套件修复完成后，我们可以继续执行审计中提到的 **协议优化**。首要任务是将 `ReactorProtocol` 和 `ExpansionPolicy` 等核心接口定义移动到 `cascade-spec` 中，以实现编译器和物理引擎与具体实现的彻底解耦。
