好的，遵照你的指示和项目路线图 (Phase 4: Ecosystem Tooling)，我将开始创建 `cs-observer` 和 `cs-controller` 这两个 CLI 工具。

我将为每个工具创建独立的包，以保持项目结构的清晰和模块化，这完全符合现有的 monorepo 布局。计划将首先搭建好这两个新包的骨架文件和目录结构。

## [WIP] feat(tooling): Scaffold cascade-cli-observer and cascade-cli-controller packages

### 用户需求
创建 `cs-observer` 和 `cs-controller` 这两个 CLI 工具的基础包结构，为后续的功能开发做准备。

### 评论
这是实施路线图第四阶段“生态工具链”的关键第一步。通过创建独立的包，我们确保了这些工具可以独立发展和分发，同时与 Cascade 核心库保持解耦。这种并行开发工具和核心功能的方式，体现了路线图中“共生演进”的核心原则，外部工具将成为验证和驱动内部引擎能力的最佳实践。

### 目标
1.  创建 `packages/cascade-cli-observer` 包的完整骨架，包括 `pyproject.toml`、`src` 目录和基本的 `app.py` 文件。
2.  创建 `packages/cascade-cli-controller` 包的完整骨架，同样包括所有必要的配置文件和源码目录。
3.  在 `pyproject.toml` 中为每个工具定义好初始依赖（如 `typer`）和控制台脚本入口点。

### 基本原理
我们将采用与 `cascade-py`、`cascade-runtime` 等现有包完全一致的目录结构和 `hatchling` 构建体系。通过 `run_command` 创建目录和空文件，然后使用 `write_file` 写入 `pyproject.toml` 和 `app.py` 的初始内容。这确保了新包能立刻融入现有的开发和构建流程中。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/cli-scaffolding #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 `cs-observer` 包结构

首先，我们为 `cs-observer` 工具创建完整的目录结构和初始文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-cli-observer/src/cascade/cli/observer
mkdir -p packages/cascade-cli-observer/tests
touch packages/cascade-cli-observer/src/cascade/cli/observer/__init__.py
~~~~~

#### Acts 2: 为 `cs-observer` 创建配置文件和入口点

现在写入 `pyproject.toml` 来定义包元数据、依赖和脚本入口点，并创建一个简单的 Typer 应用作为程序骨架。

~~~~~act
write_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-cli-observer"
version = "0.1.0"
description = "A real-time telemetry observer for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces",
  "typer[all]",
  "aiomqtt",
  "rich"
]

[project.scripts]
cs-observer = "cascade.cli.observer.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import typer

app = typer.Typer()


@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    typer.echo(f"Starting to watch project: {project}...")
    # TODO: Implement MQTT connection and event printing logic.
    typer.echo("Observer not yet implemented.")


def main():
    app()


if __name__ == "__main__":
    main()
~~~~~

#### Acts 3: 创建 `cs-controller` 包结构

同样地，我们为 `cs-controller` 工具创建目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-cli-controller/src/cascade/cli/controller
mkdir -p packages/cascade-cli-controller/tests
touch packages/cascade-cli-controller/src/cascade/cli/controller/__init__.py
~~~~~

#### Acts 4: 为 `cs-controller` 创建配置文件和入口点

最后，为 `cs-controller` 写入 `pyproject.toml` 和 `app.py` 骨架。

~~~~~act
write_file
packages/cascade-cli-controller/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-cli-controller"
version = "0.1.0"
description = "A command-line tool to control running Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces",
  "typer[all]",
  "aiomqtt"
]

[project.scripts]
cs-controller = "cascade.cli.controller.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true
~~~~~

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import typer

app = typer.Typer()


@app.command()
def pause(scope: str = typer.Argument(..., help="The scope to pause (e.g., 'global', 'task:api_call').")):
    """
    Publish a 'pause' constraint to the MQTT broker.
    """
    typer.echo(f"Publishing pause command for scope: {scope}...")
    # TODO: Implement MQTT connection and publishing logic.
    typer.echo("Controller not yet implemented.")


def main():
    app()


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议

我们已经成功地为 `cs-observer` 和 `cs-controller` 创建了基础包结构。

根据“共生演进”原则，下一步我建议我们开始实现 `cs-observer watch` 命令的基础功能。这将涉及到连接到 MQTT Broker 并以人类可读的格式打印出遥测事件。这将立即为我们提供一个验证 Phase 2（遥测系统）功能的强大工具。

如果你同意，我将为你生成实现此功能的计划。
