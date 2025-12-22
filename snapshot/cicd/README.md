# Cascade CI/CD Workflow

欢迎来到 Cascade 项目的 CI/CD 系统。与传统的、基于 YAML 的流水线不同，我们的 CI/CD 流程本身就是一个使用 Cascade SDK 构建的、可测试、可维护的 Python 应用程序。我们“吃自己的狗粮”（Dogfooding），以此来展示 Cascade 的核心价值和能力。

## 核心理念：CI/CD 即代码

我们将 CI/CD 流水线视为一个声明式的 Python 应用，而不是一个静态的配置文件。这种方法带来了诸多优势：

-   **表现力强**：复杂的逻辑、条件和依赖关系可以用 Python 清晰地表达。
-   **可测试**：我们可以为流水线的每一个步骤编写单元测试（参见 `tests/cicd/`），确保其逻辑的健壮性。
-   **可重用**：CI 任务（如 `lint_package`）是标准的 Cascade 任务，可以在不同的工作流中轻松复用和组合。
-   **动态与高效**：流水线能够动态地根据代码变更调整其执行图，这对于我们的 Monorepo 架构至关重要。

## 架构

我们的 CI/CD 系统由两部分组成：

1.  **触发器 (`.github/workflows/ci.yml`)**: 一个极其简洁的 GitHub Actions 配置文件。它的唯一职责是：
    -   检出代码。
    -   设置 Python 环境。
    -   安装依赖。
    -   调用我们的 Python CI/CD 入口点 (`cicd/main.py`)，并将 GitHub 事件的上下文作为参数传入。

2.  **核心逻辑 (`cicd/` 目录)**:
    -   `main.py`: CI/CD 的命令行入口，负责解析来自 GitHub Actions 的事件类型，并触发相应的工作流。
    -   `tasks.py`: 定义构成流水线的原子任务（例如 `detect_changed_packages`, `lint_package`, `run_package_tests`）。
    -   `workflows.py`: 将原子任务组合成高级工作流（例如 `pr_check_workflow`, `release_workflow`）。

## 工作流详解

### 1. `pr_check_workflow` (Pull Request 检查)

-   **触发时机**: 当有新的 Pull Request 或代码被推送到 `main` 分支时触发。
-   **核心行为**:
    1.  **检测变更**: `detect_changed_packages` 任务会运行 `git diff` 来找出哪些 `packages/*` 目录下的文件被修改了。
    2.  **动态构建**: `cs.map` 会将 `lint_package` 和 `run_package_tests` 任务应用到所有已变更的包列表上。
    3.  **并行执行**: Cascade 引擎会为每个受影响的包并行地执行 linting 和 testing 任务。
-   **优势**: 如果一个 PR 只修改了 `cascade-sdk`，那么只有 `cascade-sdk` 会被测试，从而极大地节省了 CI 的时间和资源。

### 2. `release_workflow` (发布流程)

-   **触发时机**: （未来规划）当一个符合 `vX.Y.Z` 格式的 Git 标签被推送到仓库时触发。
-   **核心行为**:
    1.  **全量检查**: 与 `pr_check_workflow` 不同，发布流程会忽略变更检测，对**所有**包执行 linting 和 testing，以确保整个项目的健康度。
    2.  **构建**: 在所有检查通过后，并行地为所有包构建发布产物（wheel 和 sdist）。
    3.  **发布**: 将所有构建好的包发布到 PyPI。

## 如何使用

### 对于贡献者

您的开发流程非常简单：

1.  进行代码修改。
2.  在本地运行检查（推荐）：
    ```bash
    # 对你修改的包运行 lint 和 test
    uv run -- ruff check packages/<your-package-name>
    uv run -- pytest packages/<your-package-name>
    ```
3.  提交 Pull Request。

CI 系统会自动运行，并只测试您修改过的部分。

### 对于维护者

**执行发布流程**:

当前，发布流程需要手动触发或通过未来的 Git 标签自动化来实现。当准备好发布时，请确保 `PYPI_TOKEN` 已在 GitHub Secrets 中配置。

## 如何扩展

要为 CI 流程添加一个新的步骤（例如，一个新的代码格式化检查工具 `blue`），您只需要：

1.  **添加任务**: 在 `cicd/tasks.py` 中创建一个新的 Cascade 任务。
    ```python
    @cs.task
    def format_package(package_name: str) -> cs.LazyResult:
        # 直接返回 cs.shell 创建的 LazyResult，引擎会自动执行它 (TCO)
        return cs.shell(f"uv run -- blue packages/{package_name}")
    ```
2.  **整合到工作流**: 在 `cicd/workflows.py` 中，将新任务添加到 `pr_check_workflow` 的依赖图中。
    ```python
    def pr_check_workflow() -> cs.LazyResult:
        changed = detect_changed_packages()
        format_results = format_package.map(package_name=changed)
        lint_results = lint_package.map(package_name=changed).after(format_results)
        test_results = run_package_tests.map(package_name=changed).after(lint_results)
        return _ci_success_marker(test_results)
    ```
3.  **编写测试**: 在 `tests/cicd/test_tasks.py` 中为 `format_package` 任务添加单元测试。

这就是全部！无需接触复杂的 YAML 语法，您就可以用纯 Python 来扩展和维护我们的 CI/CD 流水线。