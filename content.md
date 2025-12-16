简要回答：
测试失败揭示了两个问题：一是测试预期的 `qualname` 错误，模块级函数不包含 `<locals>`；二是 Python 装饰器的副作用——模块属性指向的是包装后的 `Task` 对象而非原函数，导致反序列化时类型不一致。我将修复测试断言，并在反序列化逻辑中增加对 `Task` 对象的自动解包。

## [WIP] fix(core): 修复序列化测试与 Task 对象解包逻辑

### 用户需求
修复 `tests/graph/test_serialize.py` 中的测试失败，并确保存储了原始函数的 `Node` 在反序列化后仍然持有原始函数，而不是被 `@task` 装饰后的 `Task` 对象。

### 评论
这是一个典型的“装饰器改变了被装饰对象”导致的问题。在 Python 中，`@task` 使得 `module.func` 变成了 `Task` 实例。我们的图构建逻辑正确地提取了原始函数存入 `Node`，但在反序列化时，通过 `import_module` + `getattr` 拿回来的却是 `Task` 实例。这破坏了 `Node.callable_obj` 的类型一致性（从 `function` 变成了 `Task`），导致调用失败。
解决方案是在 `_load_func_from_path` 中增加智能判断：如果加载回来的对象是 `Task` 实例，则自动剥离包装，取回 `.func`。

### 目标
1.  修正 `test_serialize_basic_graph` 中错误的 `qualname` 断言。
2.  修改 `src/cascade/graph/serialize.py`，处理反序列化时的 `Task` 解包。

### 基本原理
保持 `Node.callable_obj` 始终为“执行逻辑的载体”（即原始函数）对于运行时的一致性至关重要。反序列化层充当了适配器，负责屏蔽 Python 导入机制带来的这种差异。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #concept/state #task/domain/core #task/object/serialization #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复测试断言

首先修正测试代码中对 `qualname` 的错误预期。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
    # Check Callable Metadata
    node_simple = next(n for n in data["nodes"] if n["name"] == "simple_task")
    assert node_simple["callable"]["qualname"] == "test_serialize_basic_graph.<locals>.simple_task"
    # Note: local functions might have issues with importlib if not top-level, 
    # but for structure check it's fine.
~~~~~
~~~~~python
    # Check Callable Metadata
    node_simple = next(n for n in data["nodes"] if n["name"] == "simple_task")
    assert node_simple["callable"]["qualname"] == "simple_task"
    # Note: local functions might have issues with importlib if not top-level, 
    # but for structure check it's fine.
~~~~~

#### Acts 2: 增强反序列化逻辑

修改 `serialize.py`，导入 `Task` 类（需要注意避免循环引用，这里使用类型检查或局部导入），并在加载对象时检查并解包。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.routing import Router
from ..spec.task import RetryPolicy

# --- Serialization Helpers ---
~~~~~
~~~~~python
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.routing import Router
from ..spec.task import RetryPolicy, Task

# --- Serialization Helpers ---
~~~~~

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
        for part in qualname.split('.'):
            obj = getattr(obj, part)
        return obj
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Could not restore function {module_name}.{qualname}: {e}")

# --- Graph to Dict ---
~~~~~
~~~~~python
        for part in qualname.split('.'):
            obj = getattr(obj, part)
        
        # If the object is a Task wrapper (due to @task decorator), unwrap it
        if isinstance(obj, Task):
            return obj.func
            
        return obj
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Could not restore function {module_name}.{qualname}: {e}")

# --- Graph to Dict ---
~~~~~

### 下一步建议
现在测试应该可以通过了。通过后，我们可以将序列化功能合并，然后开始实现 **任务映射 (`.map`)**，这是支持动态并行工作流的关键特性。
