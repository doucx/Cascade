好的，我将创建一个 `[COMMIT]` 计划，把前面所有的文件系统修改（`src/cascade/providers/config.py` 重构、`pyproject.toml` 更新、`docs/tutorial/getting-started.md` 重写、`tests/providers/test_config.py` 修复和增强）都提交到版本控制中。

## [COMMIT] feat(config): 重新设计配置加载，实现明确的 `cs.load_yaml` 和 `cs.lookup`

### 错误分析
上一个步骤中，我们发现 `cs.config()` 隐式依赖的 `"config_data"` 资源并未自动注册，导致快速上手示例失败。此外，原有的设计依赖隐式行为，使得工作流的依赖图不完整且不透明。

### 用户需求
1.  修复快速上手示例的运行时错误。
2.  彻底重构配置加载机制，实现一个明确、可追踪的配置依赖模式。

### 评论
本次提交是对 `Cascade` 核心架构的重大改进，将配置加载从依赖于隐式的资源注入，转变为遵循“万物皆为 LazyResult”原则的明确依赖链：`文件路径 LazyResult -> YAML加载 LazyResult -> 查找 LazyResult`。这极大地提高了工作流的透明度、可测试性，并修复了快速上手文档中的核心问题，显著增强了开发者体验 (DX)。

### 目标
1.  移除已废弃的 `cs.config` provider。
2.  引入两个新的 Provider：`cs.load_yaml` (负责文件 I/O 和解析) 和 `cs.lookup` (负责在已解析的字典中进行点分查找)。
3.  更新 `pyproject.toml` 中的 `cascade.providers` 入口点。
4.  重写 `docs/tutorial/getting-started.md`，使用新的明确 API，提供一个 100% 可在本地运行的示例。
5.  修复并增强 `tests/providers/test_config.py`，确保对 `KeyError` 和 `TypeError` 两种查找失败场景的正确验证。

### 基本原理
按照 `d3-constraint-quipu-plan-script-rules-D3-P2` 的规定，所有文件系统变更已在之前的 `[WIP]` 计划中完成。本计划将专注于 `git add` 和 `git commit`，确保本次架构重构作为一个完整的原子单元被记录。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/providers #comp/docs #comp/tests #concept/config #scope/api #scope/dx #ai/delegate #task/domain/core #task/object/config-loading #task/action/redesign #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有变更到 Git 暂存区

~~~~~act
git_add
src/cascade/providers/config.py
pyproject.toml
docs/tutorial/getting-started.md
tests/providers/test_config.py
~~~~~

#### Acts 2: 执行提交

创建一个包含详细信息的 Git 提交。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(config): Implement explicit config loading via cs.load_yaml and cs.lookup

This commit refactors the core configuration dependency system to remove implicit "magic" resource loading, significantly enhancing transparency and testability.

The old `cs.config()` relied on a globally injected `config_data` resource, which was opaque and caused issues in the Quick Start guide.

New Architecture:
1. **`cs.load_yaml(path)`**: A new provider that explicitly performs file I/O and returns a `LazyResult` containing the parsed dictionary.
2. **`cs.lookup(source, key)`**: A new provider that performs dot-separated key lookup within a given `LazyResult` source.

This change ensures the configuration dependency chain is clearly represented in the computation graph, aligning with the "everything is a LazyResult" philosophy.

Changes include:
- Removing the old `config` provider and replacing it with `load_yaml` and `lookup` entry points in `pyproject.toml`.
- Rewriting `src/cascade/providers/config.py` to implement the new two-step process.
- Updating `docs/tutorial/getting-started.md` with the new, fully functional and explicit API.
- Enhancing `tests/providers/test_config.py` to cover both `KeyError` (key missing) and `TypeError` (path traversal on non-container) edge cases.
~~~~~

### 下一步建议
配置重构和快速上手文档的修复已经完成并提交。现在，你可以继续关注其他 `how-to-guides` 或 `reference` 文档中的 `cs.config` 旧用法，将其替换为新的 `cs.load_yaml` 和 `cs.lookup` 组合。例如，`docs/how-to-guides/defining-computations.md` 文件可能仍需要更新。
