简要回答：
测试失败是因为 `restored_node.callable_obj` 是原始函数，而测试代码中比较的对象 `simple_task` 是被 `@task` 装饰后的 `Task` 实例。我将修正测试断言，并在序列化逻辑中增加对 `Task` 对象的支持，以确保 `map` 节点等场景下的序列化也能正常工作。

## [WIP] fix(core): 修复反序列化测试断言及 Task 序列化支持

### 用户需求
1.  修正 `test_round_trip_top_level_functions` 中的断言错误，正确比较原始函数。
2.  增强 `_get_func_path`，使其能够处理 `Task` 实例（解包出原始函数进行路径提取），防止因 `Task` 对象缺失 `__qualname__` 导致序列化失败。

### 评论
当前的失败揭示了对象身份的不匹配。反序列化层正确地还原了“执行逻辑”（原始函数），但测试用例却在与“接口包装器”（Task对象）进行比较。此外，为了支持即将到来的 `.map()` 功能（它会存储 `Task` 实例作为 `mapping_factory`），序列化器必须能够主动解包 `Task` 对象，提取其内部函数的路径信息，实现完美的闭环：序列化时解包存路径，反序列化时加载包装器并再次解包。

### 目标
1.  修改 `tests/graph/test_serialize.py`。
2.  修改 `src/cascade/graph/serialize.py`。

### 基本原理
序列化/反序列化的核心契约是：**内存中的 Graph 应该持有最底层的可执行单元（函数）**。装饰器只是用户侧的语法糖，系统内部应尽量透明化。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #concept/state #task/domain/core #task/object/serialization #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正测试断言

将断言对象从 `Task` 实例改为 `Task.func`。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
    # Verify function restoration
    restored_node = next(n for n in restored_graph.nodes if n.name == "simple_task")
    assert restored_node.callable_obj == simple_task
    assert restored_node.callable_obj(1) == 2
~~~~~
~~~~~python
    # Verify function restoration
    restored_node = next(n for n in restored_graph.nodes if n.name == "simple_task")
    assert restored_node.callable_obj == simple_task.func
    assert restored_node.callable_obj(1) == 2
~~~~~

#### Acts 2: 增强序列化逻辑以支持 Task 对象

修改 `_get_func_path`，在提取路径前先检查是否为 `Task` 实例并解包。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
# --- Serialization Helpers ---

def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    """Extracts module and qualname from a callable."""
    if func is None:
        return None
    # Handle wrapped functions or partials if necessary in future
    return {
        "module": func.__module__,
        "qualname": func.__qualname__
    }
~~~~~
~~~~~python
# --- Serialization Helpers ---

def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    """Extracts module and qualname from a callable."""
    if func is None:
        return None
    
    # If it's a Task instance, serialize the underlying function
    if isinstance(func, Task):
        func = func.func

    # Handle wrapped functions or partials if necessary in future
    return {
        "module": func.__module__,
        "qualname": func.__qualname__
    }
~~~~~

### 下一步建议
通过测试后，我们可以将序列化功能合并。然后进入 **任务映射 (`.map`)** 的开发。这将完成阶段三的所有核心功能。
