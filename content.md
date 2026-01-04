简要回答：
你说得完全正确，我提到了 `CASCADE_TEST_BACKEND` 标志但没有实现它，这是一个疏漏。我将添加这个逻辑，使其能够通过环境变量来选择执行策略。为了通用性，我将使用 `CASCADE_BACKEND` 作为环境变量名。

## [WIP] feat(engine): 添加环境变量以选择执行策略

### 用户需求
用户指出，我遗漏了通过环境变量（如 `CASCADE_BACKEND=vm`）来选择 `VMExecutionStrategy` 的逻辑，并要求我将其补全。

### 评论
这是一个非常重要的补充。通过环境变量控制后端，可以极大地简化 CI/CD 和本地测试流程，允许我们在不修改任何调用代码的情况下，对整个测试套件进行后端切换，这对于评估 v3.0 的差距至关重要。

### 目标
1.  在 `cascade-engine` 的 `Engine.run` 方法中，添加读取 `CASCADE_BACKEND` 环境变量的逻辑。
2.  确保显式传递的 `use_vm` 参数优先级高于环境变量。
3.  更新代码以根据组合逻辑选择正确的执行策略 (`GraphExecutionStrategy` 或 `VMExecutionStrategy`)。

### 基本原理
在策略选择阶段，我们将检查 `use_vm` 参数。如果它为 `True`，则直接使用 VM 策略。如果为 `False`（默认值），则进一步检查 `os.getenv("CASCADE_BACKEND") == "vm"`。这种 `or` 逻辑提供了一个灵活的覆盖机制，既支持代码驱动的显式选择，也支持环境驱动的全局切换。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/config #scope/dx #ai/instruct #task/domain/runtime #task/object/vm-strategy #task/action/continue

---

### Script

#### Acts 1: 在 Engine 中实现策略选择逻辑

我们将修改 `engine.py` 文件，导入 `os` 模块并更新 `run` 方法中的策略选择部分。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
~~~~~
~~~~~python.new
import os
import sys
import time
import asyncio
from typing import Any, Dict, Optional, Callable
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
            # 3. Select Strategy
            strategy = self.vm_strategy if use_vm else self.graph_strategy

            # 4. Execute
~~~~~
~~~~~python.new
            # 3. Select Strategy
            # The explicit `use_vm` flag takes precedence.
            # Otherwise, fall back to the environment variable for testing/experimental runs.
            should_use_vm = use_vm or os.getenv("CASCADE_BACKEND") == "vm"
            strategy = self.vm_strategy if should_use_vm else self.graph_strategy

            # 4. Execute
~~~~~

### 下一步建议
逻辑已经添加完毕。现在你可以设置环境变量 `export CASCADE_BACKEND=vm` 并运行现有的 `pytest` 测试套件，这将自动通过 `VMExecutionStrategy` 路径执行，从而开始暴露 v3.0 原型与 v2.0 产品之间的真实差距。
