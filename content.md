好的，我们现在为 `cs.config` Provider 的实现创建一个原子提交。

## [COMMIT] feat(providers): Implement `cs.config` for resource-based lookup

### 用户需求
实现 `cs.config` 声明式原语，使其能够通过点路径 (`key.path`) 从一个预注册的配置资源中查找值，从而将配置值作为计算图的一等公民。

### 评论
`cs.config` Provider 实现了配置的声明式访问，遵循依赖注入模式，通过 `cs.inject("config_data")` 依赖于用户注册的配置字典资源。这确保了 Provider 职责的单一性，并使配置加载与图中的查找逻辑彻底解耦。本次修改引入了 `PyYAML` 作为可选依赖，并在 `pyproject.toml` 中正确注册了新的 Provider。

### 目标
将 `pyproject.toml`、新的 `config.py` Provider 文件和相应的测试文件提交到一个原子化的 Git Commit 中。

### 基本原理
`cs.config` 及其资源解耦模式是实现“万物皆为可计算值”哲学的关键组件。它现在作为一个完整的功能单元，可以被提交入历史。

### 标签
#intent/build #flow/ready #priority/high #comp/providers #concept/config #concept/di #scope/api #task/domain/providers #task/object/config-provider #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有与 `config` Provider 相关的修改和新增文件

~~~~~act
git_add
pyproject.toml
src/cascade/providers/config.py
tests/providers/test_config.py
~~~~~

#### Acts 2: 提交变更

创建一个详细的 Git Commit。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(providers): Implement `cs.config` for resource-based lookup

Introduces the `config` Provider for accessing complex configuration data within the workflow graph.

Key changes:
1. **`ConfigProvider`:** Implemented to provide `cs.config()` factory. It requires PyYAML (via the new `[config]` optional dependency) for basic validation, although it does not perform the I/O itself.
2. **Resource Injection:** The underlying task (`_config_lookup_task`) uses `cs.inject("config_data")` to retrieve the loaded configuration dictionary from the Engine's resource context. This forces users to explicitly manage config loading (e.g., file I/O) as a separate resource.
3. **Lookup Logic:** Implements dot-separated key traversal, including support for dictionary keys and list indices.

This makes configuration values full members of the Cascade computation graph, supporting explicit dependencies.
~~~~~

### 下一步建议
我们已经实现了 `cs.config`。根据手册和核心需求，下一个关键功能是实现 **`cs.file`** 声明式文件操作。

`cs.file` 将允许用户声明对文件路径和内容的依赖，并提供 `read_text()`, `read_bytes()`, `exists()` 等方法，是构建自动化管道（尤其是在处理数据或工件时）的基石。

我建议下一步：
1. **完善 `src/cascade/spec/file.py`**: 确保 `File` 对象可以作为任务参数传递。
2. **设计 `FileProvider`**: 实现 `cs.file().read_text()` 等调用链，将文件 I/O 抽象为 `LazyResult`。 (注意：在当前的架构中，`File` 对象已经在 `spec` 层被定义并支持 I/O 方法，但在 Provider 层暴露 `cs.file` 仍然是更符合 API 一致性的做法)。

我们应该首先检查并确保 `src/cascade/spec/file.py` 中的 `File` 类具备所有必要的 I/O 方法，并在此基础上设计 Provider。实际上，`src/cascade/spec/file.py` 已经存在并且包含了 I/O 方法，这非常接近一个 Provider 的实现。

**更正计划**: `src/cascade/spec/file.py` 中的 `File` 类已经是一个功能完备的声明式文件接口。我们要做的是：
1. 在 `cascade/__init__.py` 中将其暴露（已完成）。
2. 在 `File` 类上添加类似于 `.json()` 这样的后处理方法（手册中提到），以提高 DX。
3. 确保它能被无缝集成。

鉴于 `File` 的实现看起来更像一个核心的 Spec 工具而非传统的 Provider，我们应该跳过 `FileProvider` 的创建，而是直接在 `File` 上增强其功能，并将其作为 Spec 层的核心原语暴露给用户，就像 `cs.Param` 和 `cs.Router` 一样。

下一步：**增强 `File` 接口，使其支持 `json()` 方法，并验证其集成。**
