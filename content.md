这是一次非常关键的诊断。Pyright 的报错清晰地揭示了当前 Monorepo 架构中三个核心的技术债：

1.  **命名空间包 (Namespace Package) 碎片化**：虽然我们为几个核心包添加了 `extend_path`，但 Monorepo 中还有大量的包（如 `cascade-sdk`, `cascade-connector-*` 等）缺失了这一声明，导致 Python 的导入系统在这些包面前“断流”。
2.  **核心工具模块丢失**：代码中引用的 `cascade.internal.inputs` 和 `cascade.context` 并没有在任何地方被真正创建。
3.  **基类接口不完备**：`Node` 基类缺少子类中常用的属性（如 `mapping_factory`），导致 NodeProcessor 在处理泛型节点时出现类型校验失败。

我将生成一个跨越多个包的修复计划，彻底解决这些阻塞性的架构问题。

## [WIP] fix(arch): 统一命名空间声明并补全核心工具模块

### 错误分析
- **Import "cascade.*" could not be resolved**: 这是因为命名空间扩展代码必须在**所有**参与该命名空间的物理目录（即所有包的 `src/cascade/` 目录）中存在。目前 `cascade-sdk` 等包缺失了该声明，导致其下的 `internal` 等子包无法被识别。
- **AttributeError/reportAttributeAccessIssue**: `Node` 基类在定义时过于精简，而运行时逻辑（如 `ArgumentResolver`）经常通过基类引用访问子类特有属性（如 `has_complex_inputs`）。
- **reportMissingImports (cascade.context/internal.inputs)**: 这些是设计中存在但在文件系统中尚未落地的“幻肢”模块。

### 用户需求
修复所有 Pyright 报错，确保跨包导入和类型检查在 Monorepo 环境下正常运行。

### 评论
这是一个典型的“基础设施同步”任务。在 Monorepo 早期，保持所有子项目的 `__init__.py` 样板代码同步至关重要，否则开发体验 (DX) 会迅速恶化。

### 目标
1.  **全面扩展命名空间**：为剩余所有包补全 `pkgutil.extend_path`。
2.  **落地核心模块**：创建 `cascade.internal.inputs` 和 `cascade.context`。
3.  **增强基类健壮性**：在 `Node` 类中添加缺失的类型提示和默认值。
4.  **修正 Provider 逻辑**：处理 `NoReturn` 异步等待和可选库的防御性编程。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/state #scope/core #ai/brainstorm #task/domain/build-system #task/object/monorepo-interop #task/action/restoration #task/state/begin

---

### Script

#### Acts 1: 补全所有缺失的命名空间声明

我们需要确保 Monorepo 中每一个子包的 `cascade` 顶层目录都能“伸缩自如”。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-connector-local/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows 'cascade' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 创建核心工具模块 `cascade.internal.inputs`

这个模块承载了 DSL 与引擎之间的“秘密握手”。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/internal/inputs.py
~~~~~
~~~~~python
from typing import Any
from cascade.spec.task import task

@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """Internal task to collect multiple LazyResults into a list."""
    return list(args)

@task(name="_get_param_value", pure=True)
def _get_param_value(name: str, params_context: Any = None) -> Any:
    """Internal task to retrieve a parameter from the execution context."""
    if params_context is None:
        return None
    return params_context.get(name)

@task(name="_get_env_var", pure=True)
def _get_env_var(name: str) -> Any:
    """Internal task to retrieve an environment variable."""
    import os
    return os.environ.get(name)
~~~~~

#### Acts 3: 创建全局上下文管理器 `cascade.context`

解决 `Param` 和 `Env` 注册时的导入错误。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/context.py
~~~~~
~~~~~python
from typing import Dict, List, Any
from cascade.spec.input import InputSpec

class CascadeContext:
    def __init__(self):
        self._specs: Dict[str, InputSpec] = {}

    def register(self, spec: InputSpec):
        self._specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self._specs.values())

# Global singleton for the DSL
_current_context = CascadeContext()

def get_current_context() -> CascadeContext:
    return _current_context
~~~~~

#### Acts 4: 增强 `Node` 基类

通过在基类定义缺失属性，消除 `Processor` 和 `Resolver` 中的类型报错。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Node:
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    # The static definition of the task.
    definition: TaskDef

    # Node-specific type ("task", "map", "param")
    # Kept for serialization and legacy checks, but logic should prefer isinstance.
    node_type: str = "task"

    # Instance-specific configuration common to most executable nodes
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass
class Node:
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    # The static definition of the task.
    definition: TaskDef

    # Node-specific type ("task", "map", "param")
    # Kept for serialization and legacy checks, but logic should prefer isinstance.
    node_type: str = "task"

    # Instance-specific configuration common to most executable nodes
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # --- Type Checker Hints ---
    # These properties are defined in subclasses but accessed via Node references
    # in runtime components. We define them here as defaults to satisfy Pyright.
    has_complex_inputs: bool = False
    mapping_factory: Optional[Callable] = None
~~~~~

#### Acts 5: 修复 S3 Provider 的类型错误

`NoReturn` 是因为我们在未安装库时引发了异常，Pyright 认为该路径不返回 awaitable。我们将异常封装在异步函数内部。

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/s3.py
~~~~~
~~~~~python.old
@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)
~~~~~
~~~~~python.new
@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    if aiobotocore is None:
        raise ImportError("aiobotocore is required for S3 tasks.")
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)
~~~~~

### 下一步建议
1.  **执行修复**：以上操作将解决约 80% 的导入和基类访问错误。
2.  **清理剩余错误**：剩下的主要是 `reportOptionalMemberAccess`（如 `cursor` 可能为 `None`）和 `reportArgumentType`。这些通常需要添加简单的 `if obj is not None:` 判断。
3.  **重新运行 Pyright**：执行完本计划后，请再次运行 `pyright **/src/**.py` 确认修复效果。
