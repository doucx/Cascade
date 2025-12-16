好的，成果需要固化。我们已经成功地将一个重要的架构原则（显式模板渲染）转化为具体、可测试的代码。现在，是时候将这个工作单元提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划来完成这项工作。

## [COMMIT] feat(provider): 实现 cs.template 用于显式字符串渲染

### 用户需求
将已完成并经过测试的 `cs.template` Provider 功能提交到版本控制中，以固化开发成果。

### 评论
这是一个里程碑式的提交，它不仅仅是增加了一个新功能，更是对 `Cascade` 核心架构理念的一次重要实践和验证。通过 `cs.template`，我们确立了“显式优于隐式”的原则，保证了计算图的诚实性和清晰性，并为后续 `cs.http` 等 Provider 的干净实现铺平了道路。

### 目标
创建一个 Git 提交，包含 `TemplateProvider` 的完整实现、`jinja2` 可选依赖的配置、插件入口点的注册以及相关的测试用例。

### 基本原理
该功能已经开发完毕并通过了测试，形成了一个逻辑上完整且独立的原子工作单元。将其提交可以为项目历史留下清晰的记录，并为下一步的工作（如修改文档、开发 `cs.http`）提供一个稳定的基础。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/build #comp/tests #concept/plugin #concept/template-engine #scope/api #scope/dx #ai/instruct #task/domain/ecosystem #task/object/template-provider #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 提交 `cs.template` Provider

我们将所有与 `cs.template` 相关的新增和修改文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
src/cascade/providers/template.py
pyproject.toml
tests/test_template.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(provider): Implement cs.template for explicit string rendering

Introduces the `cs.template` provider, establishing an explicit, first-class mechanism for string templating within the computation graph.

This commit resolves a core architectural issue where templating was implicitly coupled with providers like `http` or `config`. By making templating an independent task, we achieve:
1.  **Explicit Dependency Graph**: The dependency of a task on a rendered string (and its variables) is now clearly represented in the graph.
2.  **Single Responsibility Principle**: Providers are no longer responsible for rendering. `cs.template` handles templating; `cs.http` handles HTTP, etc.
3.  **Composability**: Any `LazyResult` can be used as a context variable for a template, making it a powerful and universal primitive.

Key changes:
- Adds `src/cascade/providers/template.py` with `TemplateProvider`.
- Uses `jinja2` as the rendering engine, managed as an optional dependency group `[template]`.
- Registers the new provider via the `cascade.providers` entry point in `pyproject.toml`.
- Includes a comprehensive test suite in `tests/test_template.py`.
~~~~~

### 下一步建议
我们已经成功地将 `cs.template` 功能合并。现在，最重要的事情是确保我们的文档与代码实现保持一致，以避免误导用户。

**下一步，我建议我们立即着手更新 `开发/Cascade 使用手册 v2.0.md`，将其中所有使用隐式模板的错误示例，全部修正为使用我们新引入的、架构正确的 `cs.template` Provider。**
