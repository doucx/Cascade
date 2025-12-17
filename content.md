好的，你的分析非常准确。`pytest` 启动时遇到的 `ImportError` 是我上次重构计划中的一个疏漏所导致的。

我将生成一个计划来修正这个问题。

## [WIP] fix: 修复多包重构后损坏的模块间引用

### 错误分析
测试失败的根本原因是，上次的重构将项目拆分为多个独立的包，但这破坏了原有的**相对导入**路径。

1.  **问题核心**: `packages/cascade-runtime/src/cascade/runtime/bus.py` 文件中有一行 `from .events import Event`。在重构前，`events.py` 与 `bus.py` 在同一目录下，所以这个相对导入是有效的。重构后，`events.py` 被移动到了 `packages/cascade-interfaces/src/cascade/interfaces/` 目录下，导致 `bus.py` 无法再通过相对路径找到它。
2.  **疏漏之处**: 我之前使用的 `sed` 命令只替换了**绝对导入**（如 `from cascade.runtime.events ...`），而未能处理这些跨越新包边界的相对导入。
3.  **连锁反应**: 这个初始错误引发了一连串的导入失败，因为许多 `runtime` 模块都依赖于现已移至 `interfaces` 包中的协议和事件定义。

### 用户需求
修复因多包重构导致的 `ModuleNotFoundError`，使项目能够再次正常导入模块并通过测试。

### 评论
这是一个典型的重构后清理任务。通过修正这些导入路径，我们将真正实现包之间的解耦，并使新的 Monorepo 结构变得可用。同时，更新根 `pyproject.toml` 以支持工作区（workspace）模式是让 `pip` 和其他构建工具正确理解我们新结构的关键。

### 目标
1.  系统性地将所有跨包的相对导入修改为绝对导入。
2.  修复 `cascade-runtime` 中对 `cascade-interfaces` 组件（events, protocols, exceptions, models）的引用。
3.  修复 `cascade-py` 中对 `cascade-runtime` 和 `cascade-interfaces` 的引用。
4.  修复 `tests` 目录中所有损坏的引用。
5.  修改根 `pyproject.toml`，移除旧的构建配置，并添加 Hatch 的工作区（workspace）配置，以正确管理多包项目。

### 基本原理
我们将逐个修复存在问题的模块。主要策略是将所有跨越 `packages/*` 边界的引用都改为从顶层 `cascade` 命名空间开始的绝对路径。这得益于 Python 的 Namespace Packages 特性，只要所有包都正确安装（例如，在 editable 模式下），解析器就能找到正确的模块。

### 标签
#intent/fix #flow/ready #priority/high
#comp/build #concept/refactoring #scope/core
#ai/instruct
#task/domain/runtime #task/object/monorepo #task/action/fix_imports #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-runtime` 的核心引用

这是导致当前错误的直接原因。我们将修复 `runtime` 目录下的所有模块。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/bus.py
~~~~~
~~~~~python
from .events import Event
~~~~~
~~~~~python
from cascade.interfaces.events import Event
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend
~~~~~

#### Acts 2: 修复 `cascade-runtime` 的 `graph` 模块引用

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        # Target could be a MappedLazyResult too
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.task import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    # Use EdgeType.CONSTRAINT instead of magic arg_name prefix
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name, # Use resource name as arg_name
                        edge_type=EdgeType.CONSTRAINT
                    )
                    self.graph.add_edge(edge)

        return node
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        # Target could be a MappedLazyResult too
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.lazy_types import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    # Use EdgeType.CONSTRAINT instead of magic arg_name prefix
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name, # Use resource name as arg_name
                        edge_type=EdgeType.CONSTRAINT
                    )
                    self.graph.add_edge(edge)

        return node
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/serialize.py
~~~~~
~~~~~python
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from ..spec.routing import Router
from ..spec.task import Task
~~~~~
~~~~~python
from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task
~~~~~
#### Acts 3: 修复 `cascade-py` 的引用

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
# CLI is now in a separate package, we can try to import it if available, or remove from core API
# For backward compatibility within cascade-py context, we might leave it out or handle it gracefully.
# The user asked for `cascade-cli` to be separate. `cli` tool might logically belong to `cascade-cli`.
# However, `cascade.cli` helper function constructs an app. Let's refer to where we moved it.
# We moved `tools/cli.py` to `packages/cascade-cli/src/cascade/cli/main.py`.
# But `cascade.cli` function logic (as a helper) is useful for `cascade-py` users.
# Let's assume for now we keep the imports pointing to the right places.
# Since `graph` moved to runtime:
from cascade.graph.serialize import to_json, from_json
~~~~~
~~~~~python
# Core Specs
from cascade.spec.task import task
from cascade.spec.lazy_types import LazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import resource, inject
from cascade.spec.constraint import with_constraints

# V1.3 New Core Components
from .context import get_current_context
from cascade.spec.input import ParamSpec, EnvSpec
from .internal.inputs import _get_param_value, _get_env_var

# Runtime
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.interfaces.exceptions import DependencyMissingError
from cascade.interfaces.protocols import Connector
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

# Tools
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from cascade.cli.main import cli
from cascade.graph.serialize import to_json, from_json
~~~~~
~~~~~act
patch_file
packages/cascade-py/src/cascade/testing.py
~~~~~
~~~~~python
from cascade.runtime import Engine
~~~~~
~~~~~python
from cascade.runtime.engine import Engine
~~~~~

#### Acts 4: 修复 `tests` 的引用

~~~~~act
patch_file
tests/conftest.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import Event
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.interfaces.events import Event
~~~~~

#### Acts 5: 更新根 `pyproject.toml` 为 Workspace 模式

这是让多包结构协同工作的关键。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
# http namespace
"http.get" = "cascade.providers.http:HttpGetProvider"
"http.post" = "cascade.providers.http:HttpPostProvider"
"http.put" = "cascade.providers.http:HttpPutProvider"
"http.delete" = "cascade.providers.http:HttpDeleteProvider"
"http.request" = "cascade.providers.http:HttpRequestProvider"
subflow = "cascade.providers.subflow:SubflowProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
# Legacy aliases
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
# New cs.io.local namespace
"io.local.read_text" = "cascade.providers.io:IoLocalReadTextProvider"
"io.local.read_bytes" = "cascade.providers.io:IoLocalReadBytesProvider"
"io.local.write_text" = "cascade.providers.io:IoLocalWriteTextProvider"
"io.local.write_bytes" = "cascade.providers.io:IoLocalWriteBytesProvider"
"io.local.exists" = "cascade.providers.io:IoLocalExistsProvider"
# New cs.io.s3 namespace
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
# New cs.io.stdio namespace
"io.stdout.write" = "cascade.providers.stdio:StdOutWriteProvider"
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml
[tool.hatch.workspaces]
packages = [
    "packages/*",
]
~~~~~
