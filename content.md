好的，既然类型解析已经恢复正常，开发者体验（DX）得到了实质性的提升，我们现在就将这些构建层面的基础改进正式提交。

## [COMMIT] fix(build): Standardize namespace packages and enable PEP 561 compliance

### 用户需求
修复 IDE 中跨包类型（如 `LazyResult`）解析为 `Unknown` 的问题，确保自动补全和类型检查功能在 Monorepo 结构下能跨包正常工作。

### 评论
这是 Cascade 架构演进中的一个关键“阵痛”修复。通过统一命名空间包模式并遵循 PEP 561 规范，我们不仅解决了当前的 LSP 解析冲突，还显著增强了库在各种 IDE 环境（VS Code, PyCharm）下的稳健性。这是一个高杠杆的改进，直接降低了后续开发的认知负担。

### 目标
1.  在所有核心子包中启用 PEP 561 类型标记。
2.  统一所有子包的命名空间声明模式，消除 LSP 的解析歧义。

### 基本原理
1.  **PEP 561 Compliance**: 引入 `py.typed` 文件是 Python 生态中声明“本包提供类型信息”的标准方式。没有它，即便存在 `.pyi` 文件，类型检查器也会保守地将其视为 `Unknown`。
2.  **Namespace Standardization**: 混合使用 PEP 420（隐式）和 `pkgutil`（显式）命名空间模式在静态分析工具中容易引发解析权竞争。通过将所有包统一为显式模式，我们确保了 LSP 能一致地合并分布在不同路径下的 `cascade.*` 子模块。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/tooling #task/object/ide-stubs #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交构建配置与类型标记变更

将所有新创建的 `py.typed` 文件和各子包的 `__init__.py` 添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/py.typed
packages/cascade-sdk/src/cascade/py.typed
packages/cascade-engine/src/cascade/py.typed
packages/cascade-common/src/cascade/py.typed
packages/cascade-graph/src/cascade/py.typed
packages/cascade-library/src/cascade/py.typed
packages/cascade-spec/src/cascade/__init__.py
packages/cascade-engine/src/cascade/__init__.py
packages/cascade-graph/src/cascade/__init__.py
packages/cascade-library/src/cascade/__init__.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(build): Standardize namespace packages and enable PEP 561 compliance

This commit resolves critical IDE type inference issues (where core types like `LazyResult` were shown as `Unknown`) by standardizing the package structure across the monorepo.

Key improvements:
1.  **PEP 561 Compliance**: Added `py.typed` markers to all core packages (`spec`, `sdk`, `engine`, `common`, `graph`, `library`). This explicitly signals to type checkers (Pyright, mypy) that these packages provide valid type information.
2.  **Explicit Namespace Packages**: Unified all sub-packages to use the `pkgutil.extend_path` pattern in their `cascade/__init__.py`. This prevents the `cascade-sdk` and `cascade-common` (which were already explicit) from shadowing implicit namespace packages like `cascade-spec` in static analysis environments.

These changes ensure robust cross-package type resolution, autocompletion, and hover information in IDEs like VS Code and PyCharm.
~~~~~

### 下一步建议
我们已经完成了一个重要的阶段性目标：**打造了一个干净、类型安全且对 IDE 友好的开发基线**。

根据之前的梳理，接下来的高优先级“阵痛”是解决 **工作流卡死 Bug**（在使用 `set-limit` 时）。我建议我们现在转向 [工作流卡死与跨engine约束.md](../../02_暂存/用户反馈/P0/工作流卡死与跨engine约束.md) 进行排查和修复。这对于维持 Cascade 的可靠性承诺至关重要。
