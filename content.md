简要回答
你的怀疑非常正确。`LispTranspiler` 的实现与我们刚刚完成的运行时重构**完全脱节**，并且确实**缺乏专门的测试覆盖**。

## [WIP] feat(lisp): 更新 Lisp 转译器以适配统一的 ParamNode 模型并增加测试

### 错误分析
`cascade/tools/lisp.py` 中的 `LispTranspiler` 存在两个严重问题：

1.  **架构不一致（过时的实现）**: 它依然保留了 `elif isinstance(node, ParamNode):` 的特殊分支。这与我们将 `ParamNode` 视为标准 `TaskNode` 的核心重构思想背道而驰。正确的做法应该是检查 `node.name == "_get_param_value"`，因为节点的 **语义** 来自于它执行的函数，而不是它的 Python 类。

2.  **实现逻辑脆弱**: 在这个特殊分支中，它试图通过 `node.param_spec.name` 获取参数名。这个属性在某些情况下（如从序列化恢复）可能为 `None`。我们已经确定，参数名的**唯一事实来源**应该是 `node.input_bindings['name']`。

这两个问题共同导致了转译器在面对 `cs.Param` 时行为不可预测，一旦遇到之前测试未覆盖的场景就会失败。

### 用户需求
1.  重构 `LispTranspiler`，使其不再特殊处理 `ParamNode` 类型，而是通过检查节点名称 `_get_param_value` 来识别参数节点，并从 `input_bindings` 中安全地提取参数名。
2.  为 `LispTranspiler` 补充必要的单元测试，确保其能够正确处理包含 `cs.Param` 的各种图结构。

### 评论
这是一个典型的“重构后遗症”。我们更新了核心运行时，但忘记了与之配套的工具链。增加测试不仅是修复当前问题的必要步骤，更是确保未来重构不会再次破坏此功能的关键保障。

### 目标
1.  修改 `packages/cascade-sdk/src/cascade/tools/lisp.py` 中的 `_render_expr` 方法，使其基于 `node.name` 而非 `isinstance(node, ParamNode)` 来生成 `(param ...)` 表达式。
2.  创建新的测试文件 `packages/cascade-sdk/tests/tools/test_lisp.py`。
3.  在该测试文件中，添加至少三个核心测试用例：
    *   一个 `cs.Param` 的直接转译。
    *   `cs.Param` 作为另一个任务的依赖。
    *   `cs.Param` 作为 `Router` 的选择器。

### 基本原理
通过将转译器的逻辑与运行时的逻辑对齐（都基于 `_get_param_value` 这个可执行任务的身份来识别参数），我们消除了架构上的不一致性。同时，通过从 `input_bindings` 读取参数名，我们确保了数据来源的稳定性和正确性。补充测试则将这一行为固化为协议的一部分。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/cli #concept/parser #scope/dx #ai/brainstorm #task/domain/tooling #task/object/lisp-transpiler #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 Lisp 转译器

我们将修改 `_render_expr` 方法，使其不再以类型区分 `ParamNode`，而是通过检查节点名称来识别并处理参数。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
        # Function Name
        if isinstance(node, MapNode):
            func_name = self._sanitize_name(node.definition.name)
            parts.append(f"map {func_name}")
        elif isinstance(node, ParamNode):
            # Safe access with fallback if param_spec is missing (e.g. from restore)
            p_name = node.param_spec.name if node.param_spec else "unknown"
            return f'(param "{p_name}")'
        else:
            func_name = self._sanitize_name(node.name)
            parts.append(func_name)
~~~~~
~~~~~python.new
        # Function Name
        if isinstance(node, MapNode): 
            func_name = self._sanitize_name(node.definition.name) 
            parts.append(f"map {func_name}") 
        elif node.name == "_get_param_value":
            # Correctly identify Param nodes by their callable's name, not their class.
            # The parameter name is reliably stored in input_bindings.
            p_name = node.input_bindings.get("name", "unknown")
            return f'(param "{p_name}")'
        else: 
            func_name = self._sanitize_name(node.name) 
            parts.append(func_name)
~~~~~

#### Acts 2: 增加 Lisp 转译器测试

创建新的测试文件并添加必要的测试用例，确保 `cs.Param` 在不同场景下都能被正确转译。

~~~~~act
write_file
packages/cascade-sdk/tests/tools/test_lisp.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.tools.lisp import to_lisp

# Skip if typer is not installed (dependency of cs.create_cli, often in same env)
pytest.importorskip("typer")


# --- Test Cases ---

def test_lisp_transpile_simple_param():
    """Tests that a standalone Param is correctly transpiled."""
    target = cs.Param("my_param", description="A test parameter")
    lisp_code = to_lisp(target)
    assert lisp_code == '(param "my_param")'


def test_lisp_transpile_param_as_dependency():
    """Tests transpilation when a Param is an input to another task."""

    @cs.task
    def process_data(data, scale: int = 1):
        pass

    target = process_data(cs.Param("user_input"), scale=10)
    lisp_code = to_lisp(target)

    # Note: Param is not shared, so it's inlined.
    expected = "(process-data (param \"user_input\") :scale 10)"
    assert lisp_code == expected


def test_lisp_transpile_shared_param_in_let():
    """Tests that a Param used multiple times is hoisted to a let* block."""

    @cs.task
    def task_a(dep):
        pass

    @cs.task
    def task_b(dep):
        pass

    @cs.task
    def gather(a, b):
        pass

    # 'user_input' is shared between task_a and task_b
    param = cs.Param("user_input")
    target = gather(task_a(param), task_b(param))

    lisp_code = to_lisp(target)
    print(lisp_code)

    # We expect 'user-input' to be defined in let* and referenced by name.
    # The name is sanitized from the node name (_get_param_value)
    expected_lines = [
        "(let* (",
        "  (get-param-value (param \"user_input\"))",
        ")",
        "  (gather (task-a get-param-value) (task-b get-param-value)))",
    ]
    assert lisp_code == "\n".join(expected_lines)


def test_lisp_transpile_router_with_param_selector():
    """Tests a complex case where a Param acts as a router selector."""

    @cs.task
    def branch_a():
        pass

    @cs.task
    def branch_b():
        pass

    router = cs.Router(
        selector=cs.Param("mode"), routes={"a": branch_a(), "b": branch_b()}
    )

    @cs.task
    def consumer(val):
        pass

    target = consumer(router)
    lisp_code = to_lisp(target)
    print(lisp_code)
    
    # The param is shared (as a selector), so it's hoisted.
    expected_lines = [
        "(let* (",
        "  (get-param-value (param \"mode\"))",
        ")",
        '  (consumer (case get-param-value (("a") (branch-a)) (("b") (branch-b)))))',
    ]

    assert lisp_code == "\n".join(expected_lines)

~~~~~

### 下一步建议
运行我们刚刚创建的新测试文件 `packages/cascade-sdk/tests/tools/test_lisp.py`，以验证我们的修复是否正确且全面。
