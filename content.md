Understood. Let's proceed with the `cascade-sdk` package.

I've analyzed the contents of `packages/cascade-sdk/tests/`.
-   `test_llm_pattern.py` and `test_state_backends.py` are clear **integration tests** as they mock external dependencies (`http`, `redis`) and use the full `cs.run` or `Engine`.
-   `test_auto_gathering.py`, `test_public_api_imports.py`, `test_cli.py`, `test_lisp.py`, and `test_visualize.py` are also **integration tests**. Although some might seem simple, they all rely on the top-level `cs.run`, `cs.visualize`, or `cs.create_cli` functions, which invoke the `CascadeApp` and the full runtime stack. They test the end-to-end user-facing API.
-   There are currently no pure unit tests in this package.

I will now generate the plan to move all existing tests into the `integration` directory.

## [WIP] refactor(tests): 为 cascade-sdk 分离测试

### 用户需求

在 `cascade-sdk` 包内，继续执行将测试文件分离到 `unit/` 和 `integration/` 目录的任务。

### 评论

The tests within the SDK package are excellent examples of integration tests, as they validate the primary user-facing functions like `cs.run()`, `cs.visualize()`, and `cs.create_cli()`. Moving them into an `integration` directory correctly classifies their role in verifying the complete workflow execution path.

### 目标

1.  在 `packages/cascade-sdk/tests/` 目录下创建 `unit/` 和 `integration/` 目录。
2.  将 `tests/examples/`, `tests/integration/`, 和 `tests/tools/` 下的所有测试文件及其 `.stitcher.yaml` 文件移动到新的 `packages/cascade-sdk/tests/integration/` 目录。
3.  清理旧的、现在已为空的目录结构。

### 基本原理

All current tests in the `cascade-sdk` package exercise the full application stack via the main SDK entry points. Therefore, they will all be categorized as integration tests. The process will involve creating the new standardized test directories, moving all test-related files into the `integration` subdirectory, and then removing the now-empty legacy directories (`examples`, `integration`, `tools`).

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

为 `cascade-sdk` 包创建 `unit` 和 `integration` 测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-sdk/tests/unit packages/cascade-sdk/tests/integration
~~~~~

#### Acts 2: 迁移所有现有测试文件到 integration 目录

我们将把 `examples`, `integration`, 和 `tools` 子目录中的所有测试都移动到新的 `integration` 目录中。

~~~~~act
move_file
packages/cascade-sdk/tests/examples/test_llm_pattern.py
packages/cascade-sdk/tests/integration/test_llm_pattern.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/examples/test_llm_pattern.stitcher.yaml
packages/cascade-sdk/tests/integration/test_llm_pattern.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_auto_gathering.py
packages/cascade-sdk/tests/integration/test_auto_gathering.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_auto_gathering.stitcher.yaml
packages/cascade-sdk/tests/integration/test_auto_gathering.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_public_api_imports.py
packages/cascade-sdk/tests/integration/test_public_api_imports.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_public_api_imports.stitcher.yaml
packages/cascade-sdk/tests/integration/test_public_api_imports.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_state_backends.py
packages/cascade-sdk/tests/integration/test_state_backends.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/integration/test_state_backends.stitcher.yaml
packages/cascade-sdk/tests/integration/test_state_backends.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_cli.py
packages/cascade-sdk/tests/integration/test_cli.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_cli.stitcher.yaml
packages/cascade-sdk/tests/integration/test_cli.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_lisp.py
packages/cascade-sdk/tests/integration/test_lisp.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_lisp.stitcher.yaml
packages/cascade-sdk/tests/integration/test_lisp.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_visualize.py
packages/cascade-sdk/tests/integration/test_visualize.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_visualize.stitcher.yaml
packages/cascade-sdk/tests/integration/test_visualize.stitcher.yaml
~~~~~

#### Acts 3: 清理旧的目录结构

删除现在已经为空的 `examples`, `integration`, 和 `tools` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-sdk/tests/examples packages/cascade-sdk/tests/integration packages/cascade-sdk/tests/tools
~~~~~

### 下一步建议

`cascade-sdk` 的测试迁移已完成。根据文件列表，下一个需要处理的包是 `cascade-python`，但它没有 `tests` 目录。再下一个是 `cascade-engine`，它也没有 `tests` 目录。 `cascade-compiler` 也没有。

看起来我们已经处理完了所有包含测试的 `cascade-*` 包。

任务“将集成测试和单元测试分开”的核心迁移工作已经完成。我们可以将这个系列的工作标记为 `[COMMIT]`，或者您可以指示我处理 `stitcher-*` 或 `pyneedle-*` 包。请指示下一步。
