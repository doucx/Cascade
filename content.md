好的，我们开始实施。将 CI/CD 流水线本身作为项目代码的一部分来构建（Dogfooding），是展示 Cascade 强大能力的绝佳方式。我们将创建一个由 Python 和 Cascade 驱动的、可测试、可维护的动态工作流，以取代脆弱的传统 YAML 配置。

我将生成一个计划，创建所需的文件和目录结构。

## [WIP] feat: 实现使用 Cascade 的 CI/CD Dogfooding 流水线

### 用户需求
用户希望为 Cascade Monorepo 项目创建一个 CI/CD 流水线，并利用 Cascade 自身的技术栈来实现这一目标（Dogfooding）。

### 评论
这是一个绝佳的实践。通过 Dogfooding，我们不仅能构建一个功能强大、高度灵活且与项目架构（Monorepo）完美契合的 CI/CD 流水线，还能为社区提供一个展示 Cascade 核心价值的最佳范例。将 CI/CD 逻辑从不透明的 YAML 迁移到可测试、可重用的 Python 代码中，本身就是一次巨大的工程体验提升。

### 目标
1.  **创建目录结构**：建立一个新的 `cicd/` 目录来存放所有 CI/CD 相关的 Python 代码。
2.  **定义 GitHub Actions 入口**: 创建一个极其简洁的 `.github/workflows/ci.yml` 文件，其唯一职责是设置环境并调用我们的 Python CI/CD 脚本。
3.  **实现原子任务**: 在 `cicd/tasks.py` 中，使用 `@cs.task` 定义构成流水线的原子操作，如 `detect_changed_packages`, `lint_package`, `test_package`, `build_package` 等。
4.  **组合为工作流**: 在 `cicd/workflows.py` 中，将原子任务组合成高级工作流，如 `pr_check_workflow` 和 `release_workflow`，并利用 `cs.map` 实现对 Monorepo 中已变更包的动态、并行处理。
5.  **创建 CLI 入口**: 在 `cicd/main.py` 中，创建一个简单的 CLI，用于解析来自 GitHub Actions 的事件上下文，并触发相应的工作流。

### 基本原理
我们将 CI/CD 流程本身视为一个声明式的 Cascade 应用程序。GitHub Actions 的角色被简化为一个触发器和环境设置器。所有的核心逻辑——包括依赖分析、条件执行、并行处理和错误处理——都由 Cascade 的运行时引擎在 Python 代码中动态管理。

这种方法的核心优势在于：
*   **代码即流水线**: 将复杂的 CI/CD 逻辑用表现力强、易于维护和测试的 Python 代码来定义。
*   **Monorepo 感知**: 通过 `git diff` 动态检测变更的包，并利用 `cs.map` 构建一个仅针对受影响组件的、最小化的执行图，极大地提升了 CI 效率。
*   **可重用性与可测试性**: 每个 CI 步骤都是一个标准的 Cascade 任务，可以被独立测试、复用和组合。

### 标签
#intent/build #intent/tooling #flow/ready #priority/high #comp/build #comp/tests #scope/dx #ai/brainstorm #task/domain/ci-cd #task/object/pipeline #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 CI/CD 目录和 GHA 配置目录

首先，我们创建 `cicd` 目录用于存放流水线代码，以及 GitHub Actions 的工作流目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p cicd .github/workflows
~~~~~

#### Acts 2: 创建 GitHub Actions 工作流文件

这个 YAML 文件非常精简。它负责环境设置，并将所有逻辑委托给我们即将创建的 Python 脚本。

~~~~~act
write_file
.github/workflows/ci.yml
~~~~~
~~~~~yaml
name: Cascade CI/CD

on:
  push:
    branches:
      - main
  pull_request:
  workflow_dispatch:

jobs:
  ci:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          # Fetch all history for all branches and tags for git diff to work correctly
          fetch-depth: 0

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: uv pip install -e ".[dev]"

      - name: Run Cascade CI Workflow
        run: python cicd/main.py --event ${{ github.event_name }}
        env:
          PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
~~~~~

#### Acts 3: 创建 `cicd` 包的初始化文件

~~~~~act
write_file
cicd/__init__.py
~~~~~
~~~~~python
# This file marks 'cicd' as a Python package.
~~~~~

#### Acts 4: 定义原子 CI 任务

`tasks.py` 文件包含了所有可重用的、构成我们流水线的基本构建块。

~~~~~act
write_file
cicd/tasks.py
~~~~~
~~~~~python
import cascade as cs
import re
from typing import List

@cs.task
async def detect_changed_packages() -> List[str]:
    """
    Detects which packages have changed compared to the main branch.
    For pull requests, it compares against the base branch.
    """
    # Note: This command is a simplification. A robust implementation would need
    # to handle different base refs for PRs vs. pushes. For this PoC,
    # comparing against 'origin/main' is a good starting point.
    git_diff_output = await cs.shell("git diff --name-only origin/main...HEAD")
    
    changed_packages = set()
    package_pattern = re.compile(r"^packages/([^/]+)/.*")

    for line in git_diff_output.splitlines():
        match = package_pattern.match(line)
        if match:
            changed_packages.add(match.group(1))
    
    if not changed_packages:
        print("No package changes detected.")
        return []

    print(f"Detected changed packages: {list(changed_packages)}")
    return sorted(list(changed_packages))

@cs.task
async def lint_package(package_name: str) -> str:
    """Runs ruff linter on a specific package."""
    print(f"Linting {package_name}...")
    await cs.shell(f"uv run -- ruff check packages/{package_name}")
    return f"LINT_OK_{package_name}"

@cs.task
async def test_package(package_name: str) -> str:
    """Runs pytest on a specific package."""
    print(f"Testing {package_name}...")
    await cs.shell(f"uv run -- pytest packages/{package_name}")
    return f"TEST_OK_{package_name}"

@cs.task
async def build_package(package_name: str) -> str:
    """Builds a specific package using hatch."""
    print(f"Building {package_name}...")
    # Hatch runs from the workspace root and can build specific packages
    await cs.shell(f"uv run -- hatch build packages/{package_name}")
    return f"BUILD_OK_{package_name}"

@cs.task
async def publish_packages() -> str:
    """Publishes all built packages to PyPI."""
    pypi_token = cs.Env("PYPI_TOKEN")
    if not pypi_token:
        raise ValueError("PYPI_TOKEN environment variable is not set.")
    
    print("Publishing all packages to PyPI...")
    # Twine will automatically find all packages in the top-level dist/ directory
    await cs.shell("uv run -- twine upload 'dist/*'")
    return "PUBLISH_OK"
~~~~~

#### Acts 5: 组合高级工作流

`workflows.py` 文件将原子任务编排成有意义的、端到端的 CI/CD 流程。

~~~~~act
write_file
cicd/workflows.py
~~~~~
~~~~~python
import cascade as cs
from typing import List
from .tasks import (
    detect_changed_packages,
    lint_package,
    test_package,
    build_package,
    publish_packages,
)

# List of all packages in the monorepo for full runs.
ALL_PACKAGES = [
    "cascade-spec",
    "cascade-common",
    "cascade-graph",
    "cascade-engine",
    "cascade-sdk",
    "cascade-library",
    "cascade-connector-local",
    "cascade-connector-mqtt",
    "cascade-cli-controller",
    "cascade-cli-observer",
    "cascade-provider-ipfs",
]

@cs.task
def _ci_success_marker(results: List[str]):
    """A dummy task to act as a final success node in the graph."""
    print("CI checks completed successfully.")
    print("Results:", results)
    return "CI_SUCCESS"

def pr_check_workflow() -> cs.LazyResult:
    """
    Workflow for Pull Requests and pushes to main.
    Only lints and tests the packages that have changed.
    """
    changed = detect_changed_packages()

    # Dynamically create lint and test tasks for each changed package
    lint_results = lint_package.map(package_name=changed)
    test_results = test_package.map(package_name=changed)

    # Enforce order: tests run only after linting passes for all packages
    test_results.after(lint_results)

    # The final result of the workflow depends on the test results
    return _ci_success_marker(test_results)


def release_workflow() -> cs.LazyResult:
    """
    Workflow for releases (triggered by a tag).
    Lints, tests, and builds ALL packages, then publishes them.
    """
    # Lint all packages in parallel
    lint_all = lint_package.map(package_name=ALL_PACKAGES)

    # Test all packages after all linting is done
    test_all = test_package.map(package_name=ALL_PACKAGES).after(lint_all)

    # Build all packages after all testing is done
    build_all = build_package.map(package_name=ALL_PACKAGES).after(test_all)

    # Publish after all builds are complete
    publish_result = publish_packages().after(build_all)
    
    return publish_result
~~~~~

#### Acts 6: 创建 CI/CD 命令行入口

`main.py` 是 GitHub Actions 调用的入口点。它根据事件类型选择要执行的 Cascade 工作流。

~~~~~act
write_file
cicd/main.py
~~~~~
~~~~~python
import sys
import cascade as cs
import typer
from .workflows import pr_check_workflow, release_workflow

app = typer.Typer()

@app.command()
def main(event: str = typer.Option(..., "--event", help="The GitHub event name.")):
    """
    Cascade CI/CD Pipeline Entrypoint.
    """
    print(f"Received GitHub event: {event}")

    target = None
    if event in ["pull_request", "push", "workflow_dispatch"]:
        print("Triggering PR Check Workflow...")
        target = pr_check_workflow()
    # A push event on a tag looks like 'push' but github.ref starts with 'refs/tags/'
    # GHA doesn't have a simple 'tag' event name, so a more robust check is needed.
    # For now, we assume a separate trigger or manual dispatch for releases.
    # A simple approach for a future iteration would be to pass ${{ github.ref_type }}
    # elif event == "tag":
    #    print("Triggering Release Workflow...")
    #    target = release_workflow()
    else:
        print(f"No workflow defined for event '{event}'. Exiting.")
        sys.exit(0)

    if target:
        # The log level is configured in the GHA workflow file
        cs.run(target, log_level="DEBUG")

if __name__ == "__main__":
    app()
~~~~~

### 下一步建议
- **增强事件检测**：`cicd/main.py` 中的事件检测逻辑可以进一步增强，例如通过检查 `github.ref_type` 来区分 `branch-push` 和 `tag-push`，从而自动触发发布工作流。
- **缓存**：在 `ci.yml` 中为 `uv` 添加缓存步骤，可以显著加快依赖安装速度。
- **本地测试**：为 `cicd/` 目录下的任务和工作流编写 `pytest` 测试，这是将 CI/CD 作为应用程序来构建的核心优势之一。
- **发布逻辑**：当前的 `release_workflow` 是一个雏形。一个完整的实现需要处理版本号管理、更新 `pyproject.toml`、创建 GitHub Release 等步骤，这些都可以被建模为 Cascade 任务。
