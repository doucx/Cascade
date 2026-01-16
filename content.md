你的诊断非常精准。之前的相对导入修复了语法层面的循环，但没有解决**逻辑层面**的循环依赖。`sdk` 模块作为用户入口，不应该依赖其内部的 `tools` 子模块；而 `tools` 子模块作为 `sdk` 的一个功能实现，又需要调用 `sdk` 的核心能力。

**唯一的正确方法是拆分模块，引入一个中立的第三方来承载核心逻辑，打破这个循环。**

你提供的 `cascade-application` 包的结构是解决此问题的关键。`cascade.app` 模块是承载核心应用逻辑（如 `run`, `visualize`, `dry_run`）的理想位置。

我将执行以下战略性重构：
1.  **提取核心逻辑**: 将 `run`, `visualize`, `dry_run` 函数从 `cascade.sdk` 模块中**移除**。
2.  **植入应用层**: 将这些函数**植入**到 `cascade.app` 模块中，因为它们本质上是围绕 `CascadeApp` 类的便捷封装。
3.  **重定向依赖**: 修改 `cascade.sdk` 和 `cascade.tools.cli`，使它们都**单向依赖**于新的 `cascade.app` 模块来获取 `run` 函数。

这样，依赖关系将从 `sdk <--> tools` 的循环，变为 `sdk --> app` 和 `tools --> app` 的健康的有向无环图（DAG）。

## [WIP] refactor(sdk): 通过提取核心应用逻辑到 cascade.app 解耦循环依赖

### 错误分析
`cascade.sdk` 模块和 `cascade.tools.cli` 模块之间存在一个无法通过简单相对导入解决的逻辑循环。`sdk` 模块需要导入 `create_cli` 来向用户暴露它，而 `create_cli` 函数内部又需要调用 `sdk.run` 来执行工作流。这种双向依赖导致了 Python 导入器无法明确初始化顺序，从而引发错误。

### 用户需求
彻底解耦 `cascade.sdk` 和 `cascade.tools.cli`，消除循环依赖。

### 评论
这是一个经典的架构重构案例。将核心业务逻辑（应用执行）与用户接口层（SDK 门面）和工具层（CLI）分离，是遵循依赖倒置原则的体现。`cascade.app` 将成为一个更底层的、稳定的核心，而 `sdk` 和 `tools` 则成为依赖于它的、可独立演进的上层组件。

### 目标
1.  将 `run`, `visualize`, `dry_run` 三个核心执行函数从 `packages/cascade-sdk/src/cascade/sdk.py` 中物理移除。
2.  将这三个函数添加到 `packages/cascade-application/src/cascade/app/__init__.py` 中，使其与 `CascadeApp` 类共存。
3.  更新 `cascade.sdk` 模块，通过延迟导入机制从 `cascade.app` 引入 `run`, `visualize`, `dry_run`。
4.  更新 `cascade.tools.cli` 模块，使其直接从 `cascade.app` 导入 `run` 函数。

### 基本原理
通过引入 `cascade.app` 作为中介，我们将依赖关系重构为：
- `cascade.sdk` -> `cascade.app` (for `run`)
- `cascade.sdk` -> `cascade.tools` (for `create_cli`)
- `cascade.tools` -> `cascade.app` (for `run`)
这样就不再存在直接的 `sdk <-> tools` 循环。

### 标签
#intent/refine #flow/ready #priority/critical #comp/build #concept/dependency-inversion #scope/core #ai/brainstorm #task/domain/sdk #task/object/circular-dependency #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 从 `cascade.sdk` 中移除核心执行函数

我们将 `run`, `visualize`, `dry_run` 函数的定义从 `sdk.py` 中删除。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
# --- Global Functions ---


def run(
    target: Union["LazyResult", List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional["Connector"] = None,
    state_backend: Union[str, Callable[[str], "StateBackend"], None] = None,
) -> Any:
    from cascade.app import CascadeApp

    app = CascadeApp(
        target=target,
        params=params,
        system_resources=system_resources,
        log_level=log_level,
        log_format=log_format,
        connector=connector,
        state_backend=state_backend,
    )
    return app.run()


def visualize(target: Any) -> str:
    from cascade.app import CascadeApp

    app = CascadeApp(target=target)
    return app.visualize()


def dry_run(target: Any) -> None:
    from cascade.app import CascadeApp

    app = CascadeApp(target=target)
    app.dry_run()


# --- Dynamic Import & Provider Loading ---
~~~~~
~~~~~python.new
# --- Dynamic Import & Provider Loading ---
~~~~~

#### Acts 2: 将执行函数植入 `cascade.app`

我们将这些函数添加到 `cascade/app/__init__.py` 文件的末尾。

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        local_bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))
~~~~~
~~~~~python.new
        local_bus.publish(PlanAnalysisFinished(run_id=run_id, total_steps=total_steps))


# --- Global Functions ---


def run(
    target: Union["LazyResult", List[Any], tuple[Any, ...]],
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional["Connector"] = None,
    state_backend: Union[str, Callable[[str], "StateBackend"], None] = None,
) -> Any:
    app = CascadeApp(
        target=target,
        params=params,
        system_resources=system_resources,
        log_level=log_level,
        log_format=log_format,
        connector=connector,
        state_backend=state_backend,
    )
    return app.run()


def visualize(target: Any) -> str:
    app = CascadeApp(target=target)
    return app.visualize()


def dry_run(target: Any) -> None:
    app = CascadeApp(target=target)
    app.dry_run()
~~~~~

#### Acts 3: 更新 `cascade.sdk` 的导入映射

现在，我们让 `sdk.py` 通过 `_IMPORT_MAP` 延迟加载这些来自新位置的函数。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    "create_cli": ("cascade.tools.cli", "create_cli"),
}

# --- Type Checking Imports ---
if TYPE_CHECKING:
~~~~~
~~~~~python.new
    "create_cli": ("cascade.tools.cli", "create_cli"),
    # App-level entry points
    "run": ("cascade.app", "run"),
    "visualize": ("cascade.app", "visualize"),
    "dry_run": ("cascade.app", "dry_run"),
}

# --- Type Checking Imports ---
if TYPE_CHECKING:
~~~~~

#### Acts 4: 更新 `cascade.tools.cli` 的导入路径

最后，我们将 `cli.py` 中对 `run` 的调用指向 `cascade.app`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/cli.py
~~~~~
~~~~~python.old
    }

    def main(**kwargs):
        from ..sdk import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
~~~~~
~~~~~python.new
    }

    def main(**kwargs):
        from cascade.app import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
~~~~~

### 下一步建议
1.  **全面测试**: 运行 `cascade-sdk` 和 `cascade-application` 的所有测试套件，特别是 `test_cli.py`，以确保新的依赖关系正确无误。
2.  **清理 `__all__`**: 检查 `sdk.py` 中的 `__all__` 列表，确保 `run`, `visualize`, `dry_run` 仍然被正确导出，以保持公共 API 的兼容性。
3.  **最终检查**: 运行最后的强耦合组件检查，确认 `cascade-sdk` 相关的循环依赖问题已彻底解决。
