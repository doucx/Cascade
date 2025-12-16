Excellent. The core refactoring is complete and stable. Now, let's make the new `JsonRenderer` accessible to the user and add dedicated tests to ensure its correctness.

This plan will introduce a `log_format` option to both `cs.run` and the generated CLI, allowing users to easily switch between human-readable and machine-parsable log formats.

## [WIP] feat: Add log_format option to select JSON or human-readable output

### 用户需求
为 `cs.run` 函数和 `cs.cli` 生成的命令行工具添加一个 `log_format` 选项，允许用户选择使用 "human"（默认）或 "json" 格式的日志输出。

### 评论
这是完成结构化日志功能的关键一步。它将新实现的 `JsonRenderer` 从一个内部组件转变为一个对用户可用的、有价值的功能。通过在核心 API 和开发者工具中同时支持此选项，我们确保了 Cascade 在不同使用场景下（作为库或作为 CLI 工具）都能提供一致的可观测性体验。

### 目标
1.  **更新 `cs.run`**：为其添加 `log_format` 参数，并根据该参数的值选择并实例化正确的 `Renderer`。
2.  **增强 `cs.cli`**：为生成的 CLI 自动添加 `--log-format` 命令行选项。
3.  **创建 Renderer 测试**: 新建一个专门的测试文件 `tests/messaging/test_renderer.py`，为 `CliRenderer` 和 `JsonRenderer` 添加单元测试。
4.  **更新 CLI 测试**: 扩展 `tests/tools/test_cli.py`，验证 `--log-format` 选项是否正常工作。

### 基本原理
通过将格式选择逻辑集中在顶层的 `cs.run` 函数中，我们为所有 Cascade 工作流提供了一个统一的配置入口。`cs.cli` 工具则通过元编程将这个配置选项无缝地暴露给命令行用户，体现了 Cascade “开发者体验优先”的设计原则。专门的 Renderer 测试将确保这两种输出格式的正确性和稳定性，独立于 `Engine` 的执行逻辑。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/cli #comp/tests #concept/ui #scope/api #scope/dx #ai/instruct #task/domain/observability #task/object/json-logging #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `cs.run` 以支持 `log_format`

我们将修改 `src/cascade/__init__.py` 中的 `run` 函数，使其能够根据 `log_format` 参数选择渲染器。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
    """
    # 1. Setup the messaging renderer
    renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)
    
    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
~~~~~
~~~~~python
from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer, JsonRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
        log_format: Logging format ("human" or "json"). Defaults to "human".
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
~~~~~

#### Acts 2: 增强 `cs.cli` 以支持 `--log-format`

现在，我们将 `--log-format` 选项添加到 `src/cascade/tools/cli.py` 生成的 CLI 中。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []

    # 1. Add log_level as a standard CLI option
    log_level_param = inspect.Parameter(
~~~~~
~~~~~python
    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
        log_format = kwargs.pop("log_format", "human")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level, log_format=log_format)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []

    # 1. Add standard CLI options
    log_level_param = inspect.Parameter(
~~~~~
~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
    )
    sig_params.append(log_level_param)

    # 2. Add user-defined parameters
    for p in params.values():
        # Determine the default value for Typer
~~~~~
~~~~~python
    )
    log_format_param = inspect.Parameter(
        name="log_format",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=typer.Option(
            "human",
            "--log-format",
            help="Format for logging ('human' or 'json').",
        ),
        annotation=str,
    )
    sig_params.extend([log_level_param, log_format_param])

    # 2. Add user-defined parameters
    for p in params.values():
        # Determine the default value for Typer
~~~~~

#### Acts 3: 创建 Renderer 测试

我们将创建一个新的测试文件 `tests/messaging/test_renderer.py` 来独立测试 `CliRenderer` 和 `JsonRenderer`。

~~~~~act
write_file
tests/messaging/test_renderer.py
~~~~~
~~~~~python
import io
import json
import pytest
from cascade.messaging.renderer import CliRenderer, JsonRenderer
from cascade.messaging.bus import MessageStore

@pytest.fixture
def msg_store():
    store = MessageStore()
    # Manually add a message for testing
    store._messages["test.hello"] = "Hello, {name}!"
    return store


def test_cli_renderer(msg_store):
    output = io.StringIO()
    renderer = CliRenderer(store=msg_store, stream=output)

    renderer.render("test.hello", "info", name="World")

    assert "Hello, World!" in output.getvalue()


def test_json_renderer_structure_and_content():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output)

    renderer.render("user.created", "info", user_id=123, status="active")
    
    log_line = output.getvalue()
    data = json.loads(log_line)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["event_id"] == "user.created"
    assert data["data"]["user_id"] == 123
    assert data["data"]["status"] == "active"


def test_json_renderer_log_level_filtering():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output, min_level="WARNING")

    # This should be rendered
    renderer.render("api.error", "error", code=500)
    # This should be filtered out
    renderer.render("request.start", "info", path="/")

    logs = output.getvalue().strip()
    assert '"level": "ERROR"' in logs
    assert '"level": "INFO"' not in logs
    # Ensure it's a single line of JSON
    assert len(logs.splitlines()) == 1
~~~~~

#### Acts 4: 更新 CLI 测试以验证新选项

最后，我们将向 `tests/tools/test_cli.py` 添加一个测试用例，以验证 `--log-format json` 选项的功能。

~~~~~act
patch_file
tests/tools/test_cli.py
~~~~~
~~~~~python
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "--log-level" in result.stdout
    assert "Minimum level for console logging" in result.stdout


def test_cli_missing_required_param():
~~~~~
~~~~~python
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "--log-level" in result.stdout
    assert "--log-format" in result.stdout
    assert "Format for logging" in result.stdout


def test_cli_json_log_format():
    """Tests that the CLI can produce JSON formatted logs."""
    @cs.task
    def simple_task():
        return "done"

    workflow = simple_task()
    app = cs.cli(workflow)

    result = runner.invoke(app, ["--log-format", "json"])

    assert result.exit_code == 0
    # Engine logs go to stderr by default
    logs = result.stderr.strip()
    
    # Check that each line is a valid JSON
    log_lines = [json.loads(line) for line in logs.splitlines()]
    
    assert any(item["event_id"] == "run.started" for item in log_lines)
    assert any(item["event_id"] == "task.started" and item["data"]["task_name"] == "simple_task" for item in log_lines)
    assert any(item["event_id"] == "run.finished_success" for item in log_lines)


def test_cli_missing_required_param():
~~~~~

### 下一步建议
我们已经成功地将结构化日志功能完全集成并暴露给了用户。代码修改已经完成，现在是时候将这个完整的逻辑单元提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划，其中包含 `git add` 和 `git commit` 指令。
