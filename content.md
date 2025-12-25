您的观察非常敏锐，这就是我们进行这次大扫除的原因。

经过对测试结果和目录结构的深入比对，我们发现了“消失的测试”和“臃肿的引擎”的真实原因：

1.  **测试“流离失所” (`cascade-sdk` 劫持了 Provider 测试)**:
    *   `cascade-library` 和 `cascade-provider-ipfs` 显示没有测试。
    *   但在 `packages/cascade-sdk/tests/providers/` 目录下，我们找到了大量本该属于它们的测试文件（如 `test_http.py`, `test_s3.py`, `test_ipfs.py`）。
    *   **原因**: 之前的重构可能将代码从 SDK 拆分到了 Library，但忘记了迁移对应的测试。

2.  **引擎“不堪重负” (`cascade-engine` 仍包含系统级测试)**:
    *   `packages/cascade-engine/tests/e2e` 包含了大量如 `test_e2e_cli_integration.py` 的文件。这些测试验证的是 CLI、Controller 和 Engine 的协同工作，属于**系统级测试**，不应放在 Engine 包内部。
    *   `packages/cascade-engine/tests/integration` 包含 `test_end_to_end.py`，这同样是跨组件的集成测试。

**结论**: 我们需要进行一次“测试归位”行动：将 Provider 测试归还给 `library` 和 `ipfs` 包，将系统级测试从 `engine` 移出到根目录的 `tests/` 下。

我将制定计划来执行这次迁移。

## [WIP] refactor(tests): Migrate stray tests to correct locations

### 错误分析
1.  **Provider 测试位置错误**: `cascade-library` 和 `cascade-provider-ipfs` 的测试目前被错误地放置在 `cascade-sdk` 包中。这导致 SDK 包的测试臃肿，而 Library 和 IPFS 包被误报为零覆盖率。
2.  **Engine 包包含系统级测试**: `cascade-engine` 包内部包含了涉及 CLI 和其他组件的 E2E 及集成测试。这违反了包的独立性原则。这些测试应该位于顶层的 `tests/` 目录中，因为它们验证的是多个包的协同工作。

### 用户需求
用户要求清理 `cascade-engine` 中残留的 E2E 文件，并修复其他包（Library, IPFS）完全没有测试的问题。

### 评论
这是架构重构的收官之战。通过这次迁移，我们将实现：
1.  **SDK**: 只包含核心 SDK 逻辑的测试。
2.  **Library/IPFS**: 拥有自己的、独立的测试套件。
3.  **Engine**: 瘦身，只包含核心运行时的单元测试。
4.  **Root Tests**: 汇集所有跨包的系统级测试。

### 目标
1.  将 `packages/cascade-sdk/tests/providers/test_ipfs.py` 移动到 `packages/cascade-provider-ipfs/tests/`。
2.  将 `packages/cascade-sdk/tests/providers/` 下的其余文件移动到 `packages/cascade-library/tests/`。
3.  将 `packages/cascade-engine/tests/e2e` 和 `packages/cascade-engine/tests/integration` 移动到根目录的 `tests/` 下，分别重组为 `tests/e2e/runtime` 和 `tests/e2e/integration`（归并入统一的 E2E/集成测试层）。

### 基本原理
**各归其位**。源代码在哪里，单元测试就应该在哪里。涉及多个组件的系统测试，就应该在顶层。这不仅是为了覆盖率报告的好看，更是为了让开发者在修改某部分代码时，能清楚地知道应该运行哪些测试。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/relocation #task/state/end

---
### Script

#### Acts 1: 准备目标目录

确保 Library 和 IPFS 包有测试目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-library/tests
mkdir -p packages/cascade-provider-ipfs/tests
mkdir -p tests/e2e/runtime
mkdir -p tests/e2e/integration
~~~~~

#### Acts 2: 归还 IPFS 测试

将 IPFS 相关的测试移出 SDK。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-sdk/tests/providers/test_ipfs.py packages/cascade-provider-ipfs/tests/
~~~~~

#### Acts 3: 归还 Library 测试

将剩余的 Provider 测试从 SDK 移至 Library。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-sdk/tests/providers/* packages/cascade-library/tests/
rmdir packages/cascade-sdk/tests/providers
~~~~~

#### Acts 4: 移出 Engine 的系统级测试

将 Engine 中的 E2E 和 Integration 测试移至根目录的 `tests/e2e` 结构中。注意我们需要连同 `harness.py` 和 `conftest.py` 一起移动。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-engine/tests/e2e/* tests/e2e/runtime/
mv packages/cascade-engine/tests/integration/* tests/e2e/integration/
rmdir packages/cascade-engine/tests/e2e
rmdir packages/cascade-engine/tests/integration
~~~~~

### 下一步建议

现在结构应该非常清晰了。请再次运行您的测试循环 `for i in (ls packages/); pytest packages/$i ; end`。您应该会看到：
1.  `cascade-library` 和 `cascade-provider-ipfs` 现在有测试在该跑了。
2.  `cascade-engine` 的测试数量会减少，只剩下真正的单元测试（coverage 依然会显示，但那是针对核心逻辑的）。
3.  要运行移出的系统级测试，您现在需要运行 `pytest tests/e2e`。
