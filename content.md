好的，这是一个非常棒的迭代。我们已经验证了核心架构，现在是时候根据实测结果进行精修，让它从“能跑”变成“健壮且高效”。

我将把这三项改进合并到一个 `[WIP]` 计划中，因为它代表了一个完整的、使 CI/CD 流水线达到生产就绪状态的逻辑单元。

## [WIP] chore(ci): 优化变更检测、添加缓存并修复依赖警告

### 用户需求
根据 CI 的实际运行日志，对流水线进行三项关键改进：
1.  修正 `git diff` 逻辑，使其在 `push` 事件下也能正确检测到变更。
2.  为 `uv` 依赖添加缓存，以加快 CI 执行速度。
3.  移除 `pyproject.toml` 中关于 `typer[all]` 的依赖警告。

### 评论
这次提交是将我们的 CI/CD Dogfooding 实践从一个可行的原型（Proof-of-Concept）提升到生产级健壮性和效率的关键一步。通过引入对 CI 上下文的感知、实施依赖缓存和清理依赖定义，我们正在构建一个真正专业、高效且维护性强的自动化系统。

### 目标
1.  **修正变更检测逻辑**：修改 `cicd/workflows.py`，使其能够读取 GitHub Actions 提供的环境变量（如 `GITHUB_EVENT_NAME` 和 `GITHUB_BASE_REF`），并根据事件类型（`push` vs `pull_request`）动态生成正确的 `git diff` 命令。
2.  **实施依赖缓存**：修改 `.github/workflows/ci.yml`，在安装依赖步骤之前，使用 `actions/cache` 来缓存 `uv` 的全局缓存目录。缓存的 key 将基于操作系统、Python 版本和 `pyproject.toml` 文件的哈希值。
3.  **清理依赖警告**：在所有相关的 `pyproject.toml` 文件中，将 `typer[all]` 修正为 `typer`。

### 基本原理
-   **上下文感知**：GitHub Actions 会通过环境变量暴露事件的详细信息。我们的 Python 脚本（`workflows.py`）将直接读取这些变量来决定是与 `HEAD~1`（对于 `push`）还是 `origin/${{ GITHUB_BASE_REF }}`（对于 `pull_request`）进行比较，从而实现精确的变更检测。
-   **缓存策略**：我们将 `uv` 的缓存目录（通常是 `~/.cache/uv`）持久化。`actions/cache` 会根据一个唯一的 key 来存取缓存。当 `pyproject.toml` 文件未发生变化时，CI 将直接从缓存中恢复依赖，将安装时间从分钟级缩短到秒级。
-   **依赖规范化**：`typer[all]` 是一个旧的依赖项语法，新版本推荐直接使用 `typer` 并按需安装可选依赖。修正它能消除警告，使我们的依赖定义更加清晰和现代化。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 修正 `typer` 依赖警告

我们将首先清理两个 `cli` 包中的 `pyproject.toml` 文件。

~~~~~act
patch_file
packages/cascade-cli-controller/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "typer[all]",
  "aiomqtt"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "typer",
  "aiomqtt"
]
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-connector-local",
  "typer[all]",
  "aiomqtt",
  "rich"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-connector-local",
  "typer",
  "aiomqtt",
  "rich"
]
~~~~~

#### Acts 2: 优化变更检测逻辑

现在，我们让 `pr_check_workflow` 变得更智能，能够适应不同的 CI 事件。

~~~~~act
patch_file
cicd/workflows.py
~~~~~
~~~~~python
def pr_check_workflow() -> cs.LazyResult:
    """
    Workflow for Pull Requests and pushes to main.
    Only lints and tests the packages that have changed.
    """
    # Step 1: Declare the action to get git diff output. This returns a LazyResult[str].
    git_diff_output = cs.shell("git diff --name-only origin/main...HEAD")

    # Step 2: Declare the action to parse the output.
    # We pass the LazyResult from step 1 directly as an argument.
~~~~~
~~~~~python
import os

def pr_check_workflow() -> cs.LazyResult:
    """
    Workflow for Pull Requests and pushes to main.
    Only lints and tests the packages that have changed.
    """
    # Step 1: Determine the correct git diff command based on the CI environment.
    event_name = os.getenv("GITHUB_EVENT_NAME")
    
    if event_name == "pull_request":
        # For PRs, compare against the merge base with the target branch.
        # GHA provides the base ref in GITHUB_BASE_REF.
        base_ref = os.getenv("GITHUB_BASE_REF", "main")
        diff_command = f"git diff --name-only origin/{base_ref}...HEAD"
        print(f"Running diff for Pull Request: {diff_command}")
    else: # Handles "push", "workflow_dispatch", and local runs
        # For pushes, compare the last two commits.
        diff_command = "git diff --name-only HEAD~1 HEAD"
        print(f"Running diff for Push/Local: {diff_command}")

    # Step 2: Declare the action to get git diff output. This returns a LazyResult[str].
    git_diff_output = cs.shell(diff_command)
    
    # Step 3: Declare the action to parse the output.
    # We pass the LazyResult from step 2 directly as an argument.
~~~~~

~~~~~act
patch_file
cicd/workflows.py
~~~~~
~~~~~python
    # Step 3: Use the result of the parsing to dynamically build the rest of the graph.
    lint_results = lint_package.map(package_name=changed_packages)
    test_results = run_package_tests.map(package_name=changed_packages)
~~~~~
~~~~~python
    # Step 4: Use the result of the parsing to dynamically build the rest of the graph.
    lint_results = lint_package.map(package_name=changed_packages)
    test_results = run_package_tests.map(package_name=changed_packages)
~~~~~

#### Acts 3: 在 GitHub Actions 中添加 `uv` 缓存

最后，我们修改 `.github/workflows/ci.yml` 来启用缓存。

~~~~~act
patch_file
.github/workflows/ci.yml
~~~~~
~~~~~yaml
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Create Virtual Environment and Install Dependencies
        run: |
          uv venv
          uv pip install -e ".[dev]"
~~~~~
~~~~~yaml
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Cache uv dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-${{ matrix.python-version }}-uv-${{ hashFiles('**/pyproject.toml') }}
          restore-keys: |
            ${{ runner.os }}-${{ matrix.python-version }}-uv-

      - name: Create Virtual Environment and Install Dependencies
        run: |
          uv venv
          uv pip install -e ".[dev]"
~~~~~
