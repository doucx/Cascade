非常好！经过一系列的诊断和修复，我们终于完成了一个非常复杂且关键的架构重构。测试套件的通过确认了仓库现在处于一个稳定、一致的状态。

是时候将这个里程碑式的工作单元作为一个原子提交永久记录下来了。

## [COMMIT] refactor(arch): Implement semantic package structure (spec, engine, sdk)

### 用户需求
将项目包从基于物理分层（`interfaces`, `runtime`）的结构，重构为基于领域驱动和语义支柱（`spec`, `engine`, `sdk`）的新架构。

### 评论
这次重构是 Cascade 项目架构成熟过程中的一次重大飞跃。它彻底解决了原有包结构语义模糊、职责不清的核心痛点。新的结构使得代码库的意图更加清晰，降低了新开发者的认知负荷，并为未来的跨语言（如 Rust）内核实现奠定了坚实的基础。

### 目标
创建一个单一的、内容详尽的 Git 提交，以原子方式记录整个成功的架构重构过程。

### 基本原理
一系列复杂的文件移动、重命名和内容修复已经完成，并且通过了完整的 `pytest` 测试套件验证。这意味着代码库处于一个已知的、健康的状态。此刻进行提交，可以为这个重大的重构工作创建一个安全的、可回溯的历史检查点。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有重构相关的变更
我们将根目录的 `pyproject.toml` 以及 `packages` 和 `tests` 目录下的所有变更添加到 Git 暂存区。

~~~~~act
git_add
pyproject.toml
packages/
tests/
~~~~~

#### Acts 2: 创建原子提交
现在，我们将创建一个内容详尽的提交，以清晰地记录本次重构的目的和范围。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(arch): Implement semantic package structure

This commit executes a major architectural refactoring, moving the project from a physical-layer package structure to a semantic, domain-driven one as outlined in the architecture proposal.

The previous structure (`interfaces`, `runtime`, `py`) was causing confusion, as components like the graph compiler were located in `runtime`, and core contracts were split.

This change introduces a clear, four-pillar structure:

1.  **`cascade-spec`**: The system's contract. Contains all data models (`Blueprint`, `Graph`), interfaces (`protocols.py`), and specifications. This is the most stable part of the codebase.

2.  **`cascade-engine`**: The execution core. Contains the virtual machine, resource manager, constraint manager, and graph compiler/builder. This is the "engine" that runs the workflows.

3.  **`cascade-sdk`**: The user-facing SDK. Provides the public API (`@cs.task`, `cs.run`) and the built-in provider registry.

4.  **`cascade-common`**: Shared utilities like the decoupled messaging bus and renderers.

Key changes in this commit:
-   `packages/cascade-interfaces` renamed to `packages/cascade-spec`.
-   `packages/cascade-runtime` renamed to `packages/cascade-engine`.
-   `packages/cascade-py` renamed to `packages/cascade-sdk`.
-   `blueprint.py` moved from `engine` to `spec`, solidifying its role as a core contract.
-   `tests/` directory structure standardized to mirror the new package names.
-   All `pyproject.toml` files (root and packages) have been updated to reflect the new names and inter-package dependencies.
-   All Python `import` statements across the codebase have been corrected to point to the new module locations.
~~~~~

### 下一步建议
我们已经成功完成了第一阶段的语义化重构。根据原始的架构建议书，下一步是继续深化这种职责分离。我建议我们开始实施第二阶段：

**将图逻辑从 `cascade-engine` 中剥离出来，创建一个新的 `cascade-graph` 包。**

这个包将专门负责图的构建、编译、哈希和序列化，进一步净化 `cascade-engine`，使其更专注于“物理执行”。如果你同意，我将为此创建下一个计划。
