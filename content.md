好的，我们已经完成了 `cascade-std` 包的初始化以及核心指令集（代码、测试、文档）的迁移，并确保了 `cascade-vm` 的独立性。现在我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交。

## [COMMIT] refactor(vm): 迁移标准三连体逻辑至 cascade-std 包

### 用户需求
完成 `Act 0.5` 路线图中的任务 T1 和 T2，将原本位于 `cascade-vm` 中的标准指令集（Bleacher, Stainer, Observer）及其配套的单元测试和 Stitcher 文档迁移到新建立的 `cascade-std` 包中。

### 评论
这次提交标志着 Cascade 3.0 架构的一个重要里程碑：物理执行引擎（VM）与具体物理定律（Std）的正式分离。通过这种解耦，我们不仅净化了 `cascade-vm` 的职责，还建立了一个可扩展的标准库框架，为后续实现更复杂的采样芯片和资源经纪人奠定了基础。

### 目标
1. 提交新创建的 `cascade-std` 包及其完整结构。
2. 提交对 `cascade-vm` 的清理，包括移除迁移的代码、测试和错误的依赖声明。
3. 提交根目录 `pyproject.toml` 的配置更新，正式将 `cascade-std` 纳入 Monorepo。

### 基本原理
按照架构设计，`cascade-vm` 应当是一个不带任何业务偏见的纯粹反应堆。将 `triad` 逻辑迁出并独立为 `cascade-std` 完美契合了这一原则。通过同时迁移代码、测试和 `.stitcher.yaml` 文档，我们保证了逻辑单元的完整性和可维护性。

### 标签
#intent/refine #flow/ready #priority/high #comp/vm #comp/std #comp/build #comp/docs #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-std #task/action/migration #task/state/end

---

### Script

#### Acts 1: 提交架构迁移变更

我们将所有涉及迁移和初始化的变更添加到暂存区并执行提交。

~~~~~act
git_add
pyproject.toml
packages/cascade-vm/pyproject.toml
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-std/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): migrate standard triad logic to cascade-std

Architectural shift: Decoupled the physical reactor (VM) from specific physical laws (Std).

Key Changes:
1. **Created cascade-std**: Initialized a new package dedicated to standard physical primitives (ICs).
2. **Migrated Triad Logic**: Moved 'bleacher', 'stainer', and 'observer' from cascade-vm to cascade-std/triad.
3. **Moved Tests & Docs**: Transferred corresponding unit tests and .stitcher.yaml files to maintain consistency.
4. **Purified VM**: Removed redundant dependency on cascade-std from cascade-vm, ensuring the VM remains a generic execution engine.
5. **Configured Workspace**: Integrated cascade-std into the root pyproject.toml and LSP environments.

This refactoring fulfills Tasks T1 and T2 of the Act 0.5 roadmap.
~~~~~

#### Acts 2: 清理残留空目录

提交完成后，我们彻底清理 `cascade-vm` 中因迁移而变为空的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-vm/src/cascade/vm/instructions
rm -rf packages/cascade-vm/tests/unit/instructions
~~~~~

### 下一步建议
我们已经稳固地建立了 `cascade-std` 框架并完成了核心逻辑的迁出。

接下来的任务是 **T3: 实现采样芯片 (Probe ICs)**。这些芯片将允许计算图主动探测外部环境（如参数、环境变量）。我建议先从最基础的 `ParamProbe` 开始，它将实现 Cascade 3.0 中“参数即采样”的核心理念。
