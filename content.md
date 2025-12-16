简要回答
CLI 工具在运行工作流后未打印最终结果，导致测试无法捕获预期输出。我将修改 `src/cascade/tools/cli.py` 以显式打印执行结果。

## [WIP] fix(cli): 修复 CLI 工具不输出工作流执行结果的问题

### 错误分析
*   **现象**: `tests/tools/test_cli.py::test_cli_generator_from_context` 失败。断言 `'Hello World Hello World' in output` 未通过，输出中仅包含运行时的日志信息。
*   **原因**: `src/cascade/tools/cli.py` 中的 `main` 函数调用了 `cascade_run`，但**丢弃了返回值**。`cascade_run` 负责执行工作流并返回结果，但它本身不负责将结果打印到控制台（这是调用者的职责）。因此，`Typer` 应用执行完毕后，stdout 中没有任何关于业务结果的输出。
*   **解决方案**: 修改 `main` 函数，捕获 `cascade_run` 的返回值，如果不为 `None`，则使用 `print()` 将其输出到 stdout。

### 用户需求
修复 CLI 测试失败，确保通过 `cs.cli` 生成的命令行工具能够将工作流的最终结果输出到标准输出，以便用户查看或被其他工具管道化使用。

### 评论
这是一个简单的疏忽。CLI 工具的主要作用之一就是展示结果。

### 目标
修改 `src/cascade/tools/cli.py`，在工作流执行成功后打印结果。

### 基本原理
在 `cli.py` 的闭包 `main` 函数中添加结果打印逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #task/domain/core #task/object/cli #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修改 CLI 输出逻辑

在 `src/cascade/tools/cli.py` 中，将 `cascade_run` 的结果捕获并打印。

~~~~~act
patch_file
src/cascade/tools/cli.py
~~~~~
~~~~~python
        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params, log_level=log_level, log_format=log_format)

    # --- Metaprogramming to create the dynamic signature ---
~~~~~
~~~~~python
        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        result = cascade_run(target, params=run_params, log_level=log_level, log_format=log_format)
        if result is not None:
            print(result)

    # --- Metaprogramming to create the dynamic signature ---
~~~~~

### 下一步建议
再次运行测试。如果通过，则所有已知的 v1.3 重构问题均已解决。我们可以着手准备提交。
