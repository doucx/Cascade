这将显著改善项目结构，不仅消除了命名混淆，还解除了 `cascade-compiler` 对 `cascade-std` 的不必要依赖（编译器应当只依赖规范，不依赖标准库实现）。

我将把 `cascade.std.specs` 移动到 `cascade.spec.components`。

## [WIP] refactor(spec): 将组件规范从 std 移至 spec 包

### 用户需求
1.  将 `packages/cascade-std/src/cascade/std/specs/` 下的所有文件移动到 `packages/cascade-spec/src/cascade/spec/` 下。
2.  重命名该模块以避免混淆（选定名称：`components`）。
3.  更新所有相关引用。

### 评论
这是一个非常好的架构清理。
1.  **解耦**: `cascade-compiler` 目前为了获取 `BleacherSpec` 等定义而依赖了 `cascade-std`，这在逻辑上是反向的（编译器应该只知道 Spec，不知道 StdLib 实现）。移动后，编译器只依赖 `cascade-spec`，依赖关系更清晰。
2.  **语义正确性**: Spec 定义（Interface）本就属于 `cascade-spec` 包，Implementation 才属于 `cascade-std`。
3.  **消除歧义**: 将 `specs` 重命名为 `components`，避免了与包名 `spec` 的口语混淆。

### 目标
1.  在 `cascade-spec` 中创建 `components` 模块。
2.  迁移 `triad.py`, `resource.py`, `system.py` 及 `__init__.py`。
3.  批量更新 `cascade-std` 和 `cascade-compiler` 中的导入路径。

### 基本原理
我们将使用 `move_file` 物理移动文件，然后使用 `patch_file` 修正代码中的导入语句。所有 `from cascade.std.specs` 的引用将被重定向到 `from cascade.spec.components`。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/spec #comp/std #comp/compiler #scope/core
#task/domain/architecture #task/object/specs #task/action/move
#task/state/continue

---

### Script

#### Acts 1: 创建目标目录并移动文件

首先建立新的目录结构，并将文件迁移过去。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-spec/src/cascade/spec/components
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-std/src/cascade/std/specs/* packages/cascade-spec/src/cascade/spec/components/
~~~~~

~~~~~act
delete_file
packages/cascade-std/src/cascade/std/specs
~~~~~

#### Acts 2: 更新 `__init__.py` 导出

修正新位置下的 `__init__.py`，确保它导出 `components` 模块中的内容。因为文件移动后内容没变，这步可能不需要修改代码，但在导入路径改变的情况下，检查一下是明智的。原 `__init__.py` 使用的是相对导入（`.resource` 等），所以移动后只要文件名保持一致，内容无需修改。

#### Acts 3: 修正 `cascade-std` 中的引用

更新标准库实现中的引用。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
from cascade.std.specs import ContinuousAllocatorSpec, ContinuousReclaimerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import ContinuousAllocatorSpec, ContinuousReclaimerSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import DiscreteAllocatorSpec, DiscreteReclaimerSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
from cascade.std.specs import ResourceRequestorSpec
~~~~~
~~~~~python.new
from cascade.spec.components import ResourceRequestorSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
from cascade.std.specs import DrainerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import DrainerSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/egress.py
~~~~~
~~~~~python.old
from cascade.std.specs import EgressSpec
~~~~~
~~~~~python.new
from cascade.spec.components import EgressSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/gate.py
~~~~~
~~~~~python.old
from cascade.std.specs import GateSpec
~~~~~
~~~~~python.new
from cascade.spec.components import GateSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/retry.py
~~~~~
~~~~~python.old
from cascade.std.specs import RetrySpec
~~~~~
~~~~~python.new
from cascade.spec.components import RetrySpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
from cascade.std.specs import TerminatorSpec
~~~~~
~~~~~python.new
from cascade.spec.components import TerminatorSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
from cascade.std.specs import BleacherSpec
~~~~~
~~~~~python.new
from cascade.spec.components import BleacherSpec
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python.old
from cascade.std.specs import WorkerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import WorkerSpec
~~~~~

#### Acts 4: 修正 `cascade-compiler` 中的引用

更新编译器中的引用，这是解除循环依赖/反向依赖的关键一步。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
~~~~~
~~~~~python.old
from cascade.std.specs import EgressSpec
~~~~~
~~~~~python.new
from cascade.spec.components import EgressSpec
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python.old
from cascade.std.specs import StainerSpec, BleacherSpec, EgressSpec
~~~~~
~~~~~python.new
from cascade.spec.components import StainerSpec, BleacherSpec, EgressSpec
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
~~~~~
~~~~~python.old
from cascade.std.specs import ObservabilitySpec, BleacherSpec, StainerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import ObservabilitySpec, BleacherSpec, StainerSpec
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
from cascade.std.specs import StainerSpec
~~~~~
~~~~~python.new
from cascade.spec.components import StainerSpec
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python.old
from cascade.std.specs import BleacherSpec
~~~~~
~~~~~python.new
from cascade.spec.components import BleacherSpec
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
from cascade.std.specs import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    GateSpec,
)
~~~~~
~~~~~python.new
from cascade.spec.components import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    GateSpec,
)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.std.specs import BleacherSpec
~~~~~
~~~~~python.new
from cascade.spec.components import BleacherSpec
~~~~~

### 下一步建议

现在 Specs 已经安全地落户在 `cascade-spec` 中，我们可以回到 Dyad 架构的实现上了。

下一步：
1.  在 `packages/cascade-spec/src/cascade/spec/components` 中新建 `dyad.py`，定义 `LauncherSpec` 和 `LanderSpec`。
2.  在 `cascade-std` 中实现这两个新组件。
