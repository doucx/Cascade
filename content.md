简要回答
发现两个关键 Bug：运行时解析器无法识别 `Param` 任务（因对象比对错误），以及 CLI 测试中存在变量作用域遮蔽。我将修复解析器逻辑并清理测试代码。

## [WIP] fix: 修复 ArgumentResolver 中的内部任务识别逻辑及测试中的作用域错误

### 错误分析

1.  **TypeError: `_get_param_value` missing argument**:
    *   **现象**: `tests/providers/test_http.py`, `tests/runtime/test_input_execution.py` 等测试失败，报错 `TypeError: _get_param_value() missing 1 required positional argument: 'params_context'`.
    *   **原因**: 在 `src/cascade/runtime/resolvers.py` 中，`ArgumentResolver` 试图拦截 `_get_param_value` 任务以注入 `params_context`。判断逻辑 `if node.callable_obj is _get_param_value:` 是错误的。
        *   `node.callable_obj` 是原始函数 (因为 `GraphBuilder` 取的是 `result.task.func`)。
        *   `_get_param_value` (导入自 `cascade.internal.inputs`) 是被 `@task` 装饰后的 `Task` 实例。
        *   两者不相等，导致拦截失败，逻辑落入默认参数解析流程。默认流程在 `node.literal_inputs` 中找不到 `params_context`，导致调用时参数缺失。
    *   **修复**: 修改判断逻辑为 `if node.callable_obj is _get_param_value.func:`。

2.  **NameError: cannot access free variable**:
    *   **现象**: `tests/tools/test_cli.py` 报错。
    *   **原因**: 测试函数 `test_cli_generator_from_context` 内部定义了闭包 `workflow_def`，其中引用了 `get_current_context`。但在闭包定义之后、调用之前，测试函数内部又执行了 `from cascade.context import get_current_context`。这导致 Python 编译器将 `get_current_context` 视为局部变量，但在 `workflow_def` 执行时该局部变量尚未赋值（UnboundLocalError 的变体，闭包场景下报 free variable 访问错误）。
    *   **修复**: 删除测试函数内部多余的局部导入，使用模块级导入。

### 用户需求
修复导致测试失败的 Bug，确保 `Param` 机制正常工作，以及 CLI 测试通过。

### 评论
这些是重构过程中典型的集成问题。一个是运行时标识符匹配不精确，一个是测试代码的 Python 作用域陷阱。修复它们将使 v1.3 的核心机制跑通。

### 目标
1.  修改 `src/cascade/runtime/resolvers.py`，正确识别内部任务。
2.  修改 `tests/tools/test_cli.py`，修复作用域错误。

### 基本原理
通过精确匹配函数对象来确保参数注入逻辑生效。清理测试代码中的遮蔽变量以符合 Python 作用域规则。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #task/domain/core #task/object/param #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 ArgumentResolver

修正 `ArgumentResolver` 中对 `_get_param_value` 的识别逻辑。

~~~~~act
patch_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        # 0. Special handling for internal input tasks
        # Local import to avoid circular dependency with internal.inputs -> spec.task -> runtime
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs
~~~~~
~~~~~python
        # 0. Special handling for internal input tasks
        # Local import to avoid circular dependency with internal.inputs -> spec.task -> runtime
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            # Inject params_context directly
            # The literal_inputs should contain 'name'
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs
~~~~~

#### Acts 2: 修复 CLI 测试中的作用域问题

删除 `test_cli_generator_from_context` 中多余的局部导入。

~~~~~act
patch_file
tests/tools/test_cli.py
~~~~~
~~~~~python
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # Debug: Verify context is populated
    from cascade.context import get_current_context
    specs = get_current_context().get_all_specs()
    assert len(specs) == 2, f"Context should have 2 specs, got {len(specs)}"

    # 3. 生成 CLI
~~~~~
~~~~~python
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # Debug: Verify context is populated
    specs = get_current_context().get_all_specs()
    assert len(specs) == 2, f"Context should have 2 specs, got {len(specs)}"

    # 3. 生成 CLI
~~~~~

### 下一步建议
执行测试以验证修复。如果通过，可以继续推进 v1.3 的其他清理工作或文档更新。
