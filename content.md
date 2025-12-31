好的，测试通过。我们现在进入“架构硬化”任务的第二阶段。

你的问题非常关键，它触及了这次重构的核心战略：“我们应该如何处理旧的 `cascade-graph` 包？”

**答案是：我们不应该让 `cascade-graph` 反向依赖 `cascade-compiler`。**

这会违反我们的“焦土政策”。`cascade-graph` 是一个注定要被废弃的遗留包。让它依赖一个全新的、代表未来的包，会创造一个混乱的、循环的依赖关系，并拖延我们最终将其彻底删除的目标。

正确的策略是：
1.  **物理迁移**：将 `cascade-graph` 中有价值的、可重用的核心组件（`ReflectionAnalyzer`, `HashingService`）物理地移动到 `cascade-compiler` 中，使 `compiler` 包自包含。
2.  **暂时修复**：`cascade-graph` 中的 `build.py` 会因此损坏。为了在过渡期间保持旧的 `GraphExecutionStrategy` 仍然可用（以便通过现有测试），我们将**临时**地修改 `build.py`，让它从 `cascade.compiler` 中导入这些组件。
3.  **最终废弃**：一旦 `VMExecutionStrategy` 实现了功能对等并成为默认策略，我们就可以安全地删除整个 `cascade-graph` 包，这个临时的依赖关系也会随之消失。

我将生成一个计划来执行第一步和第二步。

## [WIP] refactor(compiler): Decouple compiler from cascade-graph

### 用户需求
1.  将核心分析和哈希组件（`ReflectionAnalyzer`, `HashingService`）从 `cascade-graph` 迁移到 `cascade-compiler`。
2.  使 `cascade-compiler` 包完全独立，不再依赖于 `cascade-graph`。
3.  确保旧的 `cascade-graph` 在过渡期内仍然可以工作。

### 评论
这是一个决定性的步骤，旨在实现 `cascade-compiler` 的完全解耦和自包含。通过物理迁移代码而非仅仅改变依赖关系，我们明确了 `cascade-compiler` 作为新架构核心的地位，并为最终移除 `cascade-graph` 铺平了道路。临时修复 `cascade-graph` 的导入是一个务实的妥协，它保证了在过渡阶段我们现有的测试套件和旧的执行路径依然能够运行，从而降低了重构的风险。

### 目标
1.  将 `cascade-graph/src/cascade/graph/analysis/` 目录移动到 `cascade-compiler/src/cascade/compiler/analysis/`。
2.  将 `cascade-graph/src/cascade/graph/hashing.py` 文件移动到 `cascade-compiler/src/cascade/compiler/hashing.py`。
3.  更新 `cascade-compiler/src/cascade/compiler/frontend.py` 中的导入语句，使其使用内部的、新移动过来的组件。
4.  更新 `cascade-graph/src/cascade/graph/build.py` 中的导入语句，使其临时从 `cascade.compiler` 导入所需的组件，以保持旧图构建逻辑的兼容性。

### 基本原理
根据“焦土政策”，`cascade-compiler` 必须成为一个完全独立的单元，不能依赖于任何将被废弃的包。本次迁移将 `ReflectionAnalyzer` 和 `HashingService` 这两个纯逻辑组件的所有权正式移交给 `compiler`。修改 `frontend.py` 使用相对导入可以确保 `compiler` 的内部一致性。同时，为了避免在重构过程中完全破坏旧的 `GraphExecutionStrategy`，我们通过修改 `cascade-graph` 的 `build.py` 来创建一个临时的、从新包到旧包的依赖桥梁。这个桥梁将在未来的清理阶段被拆除。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/graph #concept/dependency-management #scope/core #ai/instruct #task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 物理迁移核心组件

我们将 `analysis` 目录和 `hashing.py` 文件从 `cascade-graph` 移动到 `cascade-compiler`。

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/analysis
packages/cascade-compiler/src/cascade/compiler/analysis
~~~~~

~~~~~act
move_file
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~

#### Acts 2: 更新 `cascade-compiler` 的内部导入

现在 `compiler` 包已经自包含，我们更新 `frontend.py` 以使用相对导入来引用这些新移入的组件。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
from cascade.graph.analysis.reflection import ReflectionAnalyzer
from cascade.graph.hashing import HashingService
~~~~~
~~~~~python.new
from .analysis.reflection import ReflectionAnalyzer
from .hashing import HashingService
~~~~~

#### Acts 3: 临时修复 `cascade-graph` 的依赖关系

为了让旧的 `GraphExecutionStrategy` 在过渡期内继续工作，我们修改 `cascade-graph` 的 `build.py`，让它从 `cascade.compiler` 中导入所需的组件。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
from .hashing import HashingService
from .analysis.reflection import ReflectionAnalyzer
~~~~~
~~~~~python.new
from cascade.compiler.hashing import HashingService
from cascade.compiler.analysis.reflection import ReflectionAnalyzer
~~~~~

### 下一步建议
我们已经完成了代码的物理迁移和依赖关系的初步调整。现在，我们需要验证这次重构的正确性。

我建议依次运行以下两个测试套件：
1.  `pytest packages/cascade-compiler/`：验证 `cascade-compiler` 在解耦后是否能独立、正确地工作。
2.  `pytest packages/cascade-graph/`：验证我们为 `cascade-graph` 建立的临时依赖桥梁是否有效，确保旧的图构建逻辑没有被完全破坏。

如果两组测试都通过，我们就可以确认本次迁移是成功的。
