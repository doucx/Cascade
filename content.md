太棒了，船长！全绿的测试结果意味着我们已经成功完成了最艰苦的“基建修复”工作。我们不仅解决了一堆烦人的 `ImportError`，更重要的是，我们理顺了整个项目的血脉，确立了真正的插件化架构。

现在，让我们把这些成果作为一个完整的逻辑单元提交。

## [COMMIT] chore: 统一工作区依赖并正规化插件架构

### 用户需求
解决 Monorepo 在新环境中开发体验（DX）不佳、依赖零散、以及插件命名空间遮蔽导致测试失败的问题。

### 评论
这次清理是 Cascade 走向成熟的关键一步。通过将 `cascade.providers` 转换为纯命名空间包，我们解决了 Python 包管理中最隐蔽的陷阱之一。现在，Cascade 的核心与扩展包之间拥有了清晰的边界，这不仅修复了当前的测试问题，更极大地增强了系统的可扩展性。

### 目标
1.  在根 `pyproject.toml` 中统一所有开发和测试依赖，实现一键安装。
2.  将 `ProviderRegistry` 逻辑从 `__init__.py` 迁出，释放 `cascade.providers` 命名空间。
3.  补全工作区内所有子包的命名空间声明。
4.  在 `uv` 配置中正确注册所有工作区成员。

### 基本原理
通过统一根目录依赖，我们将Monorepo的维护成本从 $O(N)$ 降到了 $O(1)$。通过架构重构，我们遵循了 PEP 420 规范，确保了插件机制的物理有效性。这为接下来的“阶段二：架构直觉化”提供了一个绝对稳定、透明且符合 Python 惯例的基础环境。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/build #comp/core #scope/dx #scope/arch #ai/instruct #task/domain/tooling #task/object/workspace-foundation #task/action/cleanup #task/state/end

---

### Script

#### Acts 1: 提交环境修复与架构重构成果

我们将所有涉及依赖配置、包结构修复、架构重构以及测试修正的文件添加到暂存区，并执行提交。

~~~~~act
git_add
pyproject.toml
packages/cascade-py/pyproject.toml
packages/cascade-py/src/cascade/providers/registry.py
packages/cascade-py/src/cascade/providers/__init__.py
packages/cascade-py/src/cascade/__init__.py
packages/cascade-provider-ipfs/src/cascade/__init__.py
packages/cascade-provider-ipfs/src/cascade/providers/__init__.py
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/__init__.py
packages/cascade-cli-controller/src/cascade/__init__.py
packages/cascade-cli-observer/src/cascade/__init__.py
packages/cascade-connector-mqtt/src/cascade/__init__.py
packages/cascade-connector-mqtt/src/cascade/connectors/__init__.py
tests/cascade-py/providers/test_io.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
chore: unify workspace dependencies and formalize plugin architecture

Major cleanup and restructuring to ensure a deterministic development environment:

1. Unified all development and testing dependencies in the root 'pyproject.toml' under the [dev] extra. This enables a single 'uv pip install -e .[dev]' command to set up a complete environment.
2. Refactored 'cascade.providers' from a regular package into a proper PEP 420 namespace package. Moved the registry implementation to 'registry.py' to prevent it from shadowing external providers.
3. Fixed the package structure for 'cascade-provider-ipfs' and other sub-packages by adding missing '__init__.py' files with proper namespace declarations.
4. Correctly registered all local workspace packages in 'tool.uv.sources' to ensure proper linking during editable installs.
5. Fixed 'ImportError' in IPFS, S3, and IO tests caused by missing dependencies or incorrect import paths following the refactoring.

This establishes a robust and intuitive foundation for future development and plugin contributions.
~~~~~

### 下一步建议
我们已经拿到了通往“高可用开发环境”的通行证。按照清理技术债务的路线图，接下来的重点将转向**“阶段二：架构直觉化”**：

1.  **修复 `GraphBuilder` 的递归依赖发现**: 这是目前最影响用户直觉的限制，我们将让它能够识别嵌套在字典和列表中的 `LazyResult`。
2.  **强化资源注入的报错机制**: 让 `cs.inject` 的失败不再静默，提供更清晰的调试信息。

建议我们从 **行动 2.1：强化 GraphBuilder** 开始。如果你准备好了，请指示我开始生成下一个 WIP 计划。
