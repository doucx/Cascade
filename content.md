您的分析是正确的。

当前 `tests` 目录的结构是 `packages` 目录的扁平化镜像，这是一种过时且维护性差的模式。现代 Python 项目的最佳实践是将测试代码与它所测试的源代码共同存放在同一个包内（即“代码共存”），这带来了几个关键优势：

1.  **模块化和封装**：每个 `package` 成为一个完全独立的、可分发的工作单元，包含了自身的逻辑、测试和配置。
2.  **可发现性**：测试运行器（如 `pytest`）可以更容易地自动发现和执行测试，无需复杂的 `PYTHONPATH` 配置。
3.  **可维护性**：当您修改一个包时，相关的测试就在旁边，降低了认知负荷，也使得重构更加安全。

我将创建一个计划，将顶层的测试目录分解，并将每个部分移动到其对应的包中。

## [WIP] refactor: Co-locate tests within their respective packages

### 用户需求
用户要求分析 `tests` 目录是否为 `packages` 的镜像，并在确认后，创建一个计划将其重构为代码与测试共存的结构。该计划必须使用 `run_command` 和 `mv` 来移动目录。

### 评论
这是一个非常健康且必要的架构重构。将测试与源代码放在一起，可以极大地提高项目的模块化程度和长期可维护性，使每个包都成为一个独立的、完整的单元。这与现代 Python 的打包和测试理念完全一致。

### 目标
1.  将 `tests` 目录下的每个子目录移动到 `packages` 下对应的包内，并重命名为 `tests`。
2.  将适用于多个包的集成测试（如 `tests/cli`）和共享配置（`tests/conftest.py`）移动到一个新的、明确的集成测试目录中。
3.  清理掉原有的、现已为空的顶层 `tests` 目录。

### 基本原理
我们将遵循“代码共存”的最佳实践。使用 `mv` 命令可以原子化地移动整个目录及其内容，这比逐个文件移动更高效、更不容易出错。对于那些跨越多个包的端到端（E2E）测试和共享的 `conftest.py`，将它们隔离到一个新的根级 `tests` 目录是合适的，这样既能保持共享性，又不会与单元测试混淆。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/directory-structure #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 将单元测试移动到对应的包中

以下命令会将每个与特定包对应的测试目录移动到该包内部。

~~~~~act
run_command
~~~~~
~~~~~
mv tests/application packages/cascade-application/tests
mv tests/cli-controller packages/cascade-cli-controller/tests
mv tests/cli-observer packages/cascade-cli-observer/tests
mv tests/common packages/cascade-common/tests
mv tests/connector-mqtt packages/cascade-connector-mqtt/tests
mv tests/engine packages/cascade-engine/tests
mv tests/sdk packages/cascade-sdk/tests
mv tests/spec packages/cascade-spec/tests
mv tests/cicd cicd/tests
~~~~~

#### Acts 2: 迁移集成测试和共享配置

剩余的 `tests/cli` 目录包含的是端到端测试，`tests/conftest.py` 是全局测试配置。我们将为它们创建一个新的顶层 `tests` 目录，并将旧目录删除。

~~~~~act
run_command
~~~~~
~~~~~
mkdir tests_new
mv tests/cli tests_new/e2e
mv tests/conftest.py tests_new/conftest.py
rm -rf tests
mv tests_new tests
~~~~~

### 下一步建议

这次重构是一次结构性的重大变更。在执行此计划后，下一步至关重要：

1.  **更新构建配置**：您需要检查每个包的 `pyproject.toml` 文件，确保测试工具的配置（如 `pytest` 的 `testpaths`）已更新，能够找到新位置的 `tests` 目录。
2.  **更新 CI/CD 工作流**：检查您的 CI 配置文件（例如 `cicd/workflows.py` 或 `.github/workflows/`），确保测试命令现在指向正确的位置（例如，运行 `pytest packages/cascade-engine` 而不是 `pytest tests/engine`）。
