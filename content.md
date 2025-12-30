很好，测试通过了。

代码审查完毕，这次的修改是正确且健壮的。我们通过 TDD 流程精确地定位并修复了问题，同时还增加了一个重要的回归测试来保护公共 API 的稳定性。

我将生成一个 `[COMMIT]` 计划来提交这些修复和新添加的测试。

## [COMMIT] fix(sdk): Stabilize public API imports and refine `__getattr__`

### 用户需求
用户要求遵循 TDD 流程解决 `cascade` 模块混乱的导入问题，确保核心组件能够作为稳定的公共 API 被正确访问，并增加测试覆盖率以防止未来出现类似问题。

### 评论
这是一个至关重要的修复。一个库的公共 API 应该是明确、稳定且可预测的。通过 TDD 流程，我们不仅修复了当前的 bug，还建立了一个回归测试屏障，确保核心 API 的稳定性，极大地提升了开发者体验 (DX)。

### 目标
1.  **已完成**: 在 `packages/cascade-sdk/tests/integration/` 目录下创建了新的测试文件 `test_public_api_imports.py`，用于验证核心组件的导入和对不存在属性的访问行为。
2.  **已完成**: 修改了 `packages/cascade-sdk/src/cascade/__init__.py`，通过显式导入暴露了核心 API 组件（如 `Engine`, `NativeSolver`, `LocalExecutor` 等），并更新了 `__all__` 列表。
3.  **已完成**: 修正了 `__getattr__` 函数的逻辑，使其在 provider 未找到时能抛出标准的、符合 Python 规范的 `AttributeError`。
4.  **已完成**: 确保了所有相关测试均已通过。
5.  **当前**: 将上述文件更改添加到 Git 暂存区，并创建一个符合规范的 Git 提交。

### 基本原理
我们遵循了 TDD 的核心原则：先编写失败的测试来捕获问题，然后进行代码修改使测试通过。修复方案的核心是：在 `cascade-sdk` 的顶层 `__init__.py` 中，将核心 API 组件由隐式、错误的 `__getattr__` 解析改为显式导入。同时，`__getattr__` 的功能被精确地限定在其预期范围内——动态加载 providers，并在查找失败时抛出标准的 `AttributeError`，使其行为与普通 Python 模块一致。

### 标签
#intent/tooling #flow/ready #priority/high #comp/sdk #comp/tests #concept/api #scope/dx #ai/instruct #task/domain/testing #task/object/api-surface #task/action/stabilization #task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交变更

现在，我们将修改过的文件和新添加的测试文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-sdk/src/cascade/__init__.py
packages/cascade-sdk/tests/integration/test_public_api_imports.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(sdk): Stabilize public API imports and refine __getattr__

The top-level `cascade` package's `__getattr__` function incorrectly intercepted all attribute lookups, attempting to resolve them through the provider registry. This caused `AttributeError` for core components like `NativeSolver`, which are not providers.

This commit resolves the issue by:
1.  Explicitly importing and exposing core components (`Engine`, `NativeSolver`, `LocalExecutor`, `MessageBus`, `DependencyMissingError`) in `cascade/__init__.py` and adding them to `__all__`. This makes the public API explicit and robust.
2.  Refining `__getattr__` to catch the `AttributeError` from the provider registry and re-raise a standard `AttributeError: module '...' has no attribute '...'`. This ensures correct behavior for truly non-existent attributes.

A new integration test, `test_public_api_imports.py`, was added following a TDD approach. It verifies both the successful import of public APIs and the correct error behavior for invalid attributes, preventing future regressions.
~~~~~

### 下一步建议
- **全面审查**: 可以在 `cascade` 生态的其他 `__init__.py` 文件中进行类似的审查，以确保导入和 API 暴露的一致性。
- **扩展测试**: 考虑将 `observatory/experiments/run_fireflies.py` 中的逻辑简化并迁移一部分到 E2E 测试套件中，以更全面地覆盖真实用户场景。
