好的，我们已经成功地奠定了 `Cascade` 生态系统的基石，并将两个核心功能迁移到了新的插件架构中。现在是时候将这些重大的架构改进作为一个原子单元提交了。

我将生成一个 `[COMMIT]` 计划来固化所有变更。

## [COMMIT] feat(core): 引入 Provider 插件架构并迁移 shell/template

### 用户需求
将已完成并经过测试的 Provider 插件架构、`ShellProvider` 和 `TemplateProvider` 的实现，以及所有相关的代码重构和测试，作为一个完整的逻辑单元提交到版本控制中。

### 评论
这是一个对 `Cascade` 长期健康发展至关重要的里程碑式提交。通过引入基于 `entry_points` 的 Provider 插件系统，我们成功地将核心库与具体功能实现解耦，遵循了开放/封闭原则。`cs.shell` 的迁移验证了该架构的可行性，而 `cs.template` 的实现则解决了之前讨论中的核心架构缺陷，确保了计算图的显式性和依赖关系的清晰性。这个提交为 `Cascade` 未来的可扩展性、社区贡献和生态系统建设奠定了坚实的基础。

### 目标
创建一个 Git 提交，包含 Provider 插件系统的完整实现，以及 `shell` 和 `template` 两个官方 Provider 的代码、配置和测试用例。

### 基本原理
所有开发和重构工作已经完成，相关功能形成了一个逻辑上完整且经过充分测试的工作单元。将其作为一个原子提交，可以清晰地记录项目从一个单体库向一个可扩展平台演进的关键时刻，并为后续开发提供一个稳定的基线。

### 标签
#intent/build #intent/architect #flow/ready #priority/high #comp/core #comp/build #concept/plugin #concept/template-engine #scope/api #scope/dx #ai/instruct #task/domain/ecosystem #task/object/provider-system #task/action/redesign #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有相关变更

我们将所有新建、修改和删除的文件添加到 Git 暂存区，以准备提交。

~~~~~act
git_add
pyproject.toml
src/cascade/__init__.py
src/cascade/stdlib.py
src/cascade/providers/
tests/test_template.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，执行 `git commit`，并附上详细的提交信息，解释这次架构升级的重要性。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Introduce Provider plugin architecture and migrate shell/template

This landmark commit refactors Cascade from a monolithic library into an extensible platform by introducing a formal Provider plugin architecture. It establishes the foundation for a rich ecosystem and community contributions.

Key Architectural Changes:

1.  **Provider System**:
    - A new `cascade.providers` module defines the `Provider` and `LazyFactory` protocols, establishing a clear contract for all plugins.
    - `ProviderRegistry` implements plugin discovery via the standard `importlib.metadata` and `entry_points` mechanism ('cascade.providers' group).
    - `cascade/__init__.py` now uses `__getattr__` for lazy-loading of providers, making the system dynamic and performant.

2.  **`ShellProvider` Migration**:
    - The `cs.shell` task has been migrated from the old `stdlib.py` into the first official provider, `cascade.providers.shell.ShellProvider`.
    - This validates the new architecture and serves as a reference implementation for future providers.

3.  **`TemplateProvider` Implementation**:
    - A new `cs.template` provider is introduced to handle explicit, graph-aware string templating, backed by Jinja2.
    - This critically resolves a core architectural flaw of implicit dependencies, ensuring all data flows remain explicit within the computation graph. It decouples rendering logic from other providers (like a future `http` provider).

4.  **Dependency Management**:
    - `jinja2` is added as an optional dependency under the `[template]` extra, keeping the core library lightweight.

This refactoring significantly improves modularity, testability, and extensibility, paving the way for the development of a robust standard library of providers (e.g., http, sql, file) and contributions from the community.
~~~~~

### 下一步建议
我们已经成功地完成了 Provider 架构的奠基工作。下一步，我们应该利用这个强大的新架构来丰富 `Cascade` 的核心功能。根据我们的路线图，以下任务是最高优先级的：

1.  **更新文档**: 立即修改 `Cascade 使用手册 v2.0.md`，移除所有关于隐式模板的错误示例，并用 `cs.template` 的正确用法替换它们。
2.  **实现 `cs.http` Provider**: 既然模板问题已经解决，我们可以毫无顾虑地开始实现 `cs.http` Provider。
3.  **实现 `cs.sql` Provider**: 这将是另一个展示 Provider 系统与 `@cs.resource` 依赖注入系统如何协同工作的绝佳机会。
