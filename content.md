简要回答
测试失败揭示了两个问题：
1.  **任务名称解析不一致**: 期望的 `MyCalcTask` 未出现，取而代之的是函数名 `calc`。这表明 `IRGenerator` 或 `TaskDef` 提取名称时可能优先使用了函数名而非装饰器提供的 `name` 参数，或者物理节点命名的启发式解析有问题。
2.  **Reactor Sink 错误**: `Sink callback failed ... TypeError: object NoneType can't be used in 'await' expression`。这表明 `VMExecutionStrategy` 中定义的 `_result_sink` 回调虽然是一个普通函数，但在 `Reactor` 中被当作异步函数 (`await cb(token)`) 调用了。

## [WIP] fix(vm): 修复 Reactor Sink 调用和 Task 名称解析

### 用户需求
1.  **修复 Sink 调用**: `Reactor.add_sink` 接受的回调可能是同步或异步的，`Reactor._execute_task` 必须兼容这两种情况。
2.  **修复 Task 名称**: 确保 `TaskDef` 正确捕获了装饰器传入的 `name`，并且 `Expander` 在生成物理节点名称时使用了这个逻辑名称。

### 评论
Reactor Sink 的问题是一个典型的 asyncio 陷阱：`await` 一个非协程会报错。我们需要在 `Reactor` 中增加对同步回调的支持。至于任务名称，我们需要检查 `ReflectionAnalyzer`。

### 目标
1.  修改 `Reactor._execute_task` 以支持同步 Sink 回调。
2.  检查并修复 `ReflectionAnalyzer` 的名称提取逻辑。
3.  更新集成测试以通过验证。

### 基本原理
-   **兼容性**: 框架应尽可能宽容地处理回调类型。
-   **一致性**: `Task(name="X")` 在任何地方（逻辑图、物理图、遥测）都应被称为 "X"。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #comp/reflection #task/domain/core #task/object/reactor #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 Reactor Sink 调用

修改 `Reactor._execute_task`，在调用 Sink 回调前检查它是否为协程。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
                # A. Handle Sinks (Direct callback)
                if port_name in node_sinks:
                    for cb in node_sinks[port_name]:
                        try:
                            await cb(token)
                        except Exception as e:
                            logger.exception(
                                f"Sink callback failed for {node.id}:{port_name}: {e}"
                            )
~~~~~
~~~~~python.new
                # A. Handle Sinks (Direct callback)
                if port_name in node_sinks:
                    for cb in node_sinks[port_name]:
                        try:
                            res = cb(token)
                            if inspect.isawaitable(res):
                                await res
                        except Exception as e:
                            logger.exception(
                                f"Sink callback failed for {node.id}:{port_name}: {e}"
                            )
~~~~~

#### Acts 2: 诊断 Task 名称问题

让我们检查 `ReflectionAnalyzer`。`Task` 包装器在初始化时会设置 `self.name`。`ReflectionAnalyzer.analyze` 应该优先使用这个属性。

在 `cascade-reflection/src/cascade/reflection/analyzer.py`:
```python
        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
```
这里有个问题：`func` 可能是被装饰的原始函数，也可能是 `Task` 对象。如果是 `Task` 对象，它有 `name` 属性（来自装饰器参数）。如果是原始函数，它只有 `__name__`。

在 `ReflectionAnalyzer` 中：
```python
        # Check if it's a cascade.spec.task.Task wrapper
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")
```
它提取了底层的 `func` 并赋值给 `func` 变量，然后用 `getattr(func, "__name__", "unknown")` 获取名称。这**丢弃**了 `target` (Task 对象) 上可能存在的自定义 `name`。

我们需要修复 `ReflectionAnalyzer` 以优先使用 `target` 上的 `name`。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/analyzer.py
~~~~~
~~~~~python.old
    def analyze(self, target: Any) -> TaskDef:
        # Determine the underlying function and metadata source
        func = target
        mode = "blocking"

        # Check if it's a cascade.spec.task.Task wrapper
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")

        if not callable(func):
            raise TypeError(
                f"Target {target} must be callable (or enclose a callable) to be analyzed."
            )

        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        docstring = inspect.getdoc(func)
~~~~~
~~~~~python.new
    def analyze(self, target: Any) -> TaskDef:
        # Determine the underlying function and metadata source
        func = target
        mode = "blocking"
        # Default name extraction from the callable itself
        name = getattr(target, "__name__", "unknown")

        # Check if it's a cascade.spec.task.Task wrapper
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")
            # If the wrapper has a specific name override, use it.
            if hasattr(target, "name") and target.name:
                name = target.name
            elif hasattr(func, "__name__"):
                name = func.__name__

        if not callable(func):
            raise TypeError(
                f"Target {target} must be callable (or enclose a callable) to be analyzed."
            )

        # 1. Basic Metadata
        # If name was not resolved by wrapper, try func
        if name == "unknown" and hasattr(func, "__name__"):
            name = func.__name__

        docstring = inspect.getdoc(func)
~~~~~

#### Acts 3: 调整 Expander 的命名逻辑

`Expander` 使用 `node_ir.name` 来生成物理名称 `Bleach({node_ir.name})`。`NodeIR` 的名称来自 `TaskDef`。只要 `ReflectionAnalyzer` 修复了，`NodeIR` 就应该正确。

但是，`Expander` 的代码：
```python
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
```
如果 `node_ir.name` 是 "MyCalcTask"，那么物理名就是 "Bleach(MyCalcTask)"。
标准库的 heuristic：
```python
    if node.name.startswith("Bleach(") and node.name.endswith(")"):
        task_name = node.name[7:-1]
```
这将提取出 "MyCalcTask"。

所以，修复 `ReflectionAnalyzer` 应该是解决名称问题的根本。

### 下一步建议
再次运行 `test_vm_telemetry.py`。现在 Sink 错误应该消失，且任务名称断言应该通过。
