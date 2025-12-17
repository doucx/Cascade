简要回答
好的，我们已经顺利完成了路线图 **Layer 1** 的所有任务。通过重塑 `.map` 操作、统一 Provider API 以及完善可视化与文档，我们已经为 Cascade 的开发者体验奠定了坚实的基础。

现在，我将生成最终的 `[COMMIT]` 计划，将这些变更作为一个逻辑整体提交。

## [COMMIT] feat(dx): 构建 Cascade 开发者体验地基 (Layer 1)

### 用户需求
执行路线图 Layer 1 的最终提交。这包括：
1. 使 `.map()` 支持策略链式调用并实现自动传播。
2. 统一 Provider API，引入原子化 IO 接口并支持命名空间（如 `cs.read.text`）。
3. 废弃并移除旧的 `cs.file` 接口。
4. 增强可视化测试并完善核心概念文档。

### 评论
本次提交标志着 Cascade 迈向成熟的重要一步。我们不仅消除了 API 中的不一致性（“惊奇”），还通过自动化的策略传播和级联跳过逻辑，使系统的行为更加符合用户的直觉。

### 目标
执行 Git 提交，持久化 Layer 1 的所有工作成果。

### 基本原理
按照规范，所有的文件修改已在之前的 `[WIP]` 计划中完成并经过验证。现在的任务是将其归档到版本控制系统中。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/providers #comp/docs #scope/api #scope/dx #ai/instruct #task/domain/core #task/object/dx-foundation #task/action/completion #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有修改过的源文件、测试文件以及新增的文档添加到暂存区，并执行一个详尽的提交。

~~~~~act
git_add
src/cascade/spec/lazy_types.py
src/cascade/spec/task.py
src/cascade/graph/build.py
src/cascade/runtime/engine.py
src/cascade/providers/__init__.py
src/cascade/providers/io.py
pyproject.toml
tests/runtime/test_map_policies.py
tests/runtime/test_map_reduce_integration.py
tests/providers/test_io.py
tests/providers/test_file.py
tests/tools/test_visualize.py
docs/concepts/control_vs_data_flow.md
docs/how-to-guides/dependency-injection.md
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(dx): implement Layer 1 of Developer Experience roadmap

This major update refines the core APIs and runtime behaviors to ensure 
consistency, predictability, and better developer experience.

Key Improvements:
1.  **Enhanced `.map()` Policies**: 
    - `MappedLazyResult` now supports `.with_retry()`, `.with_cache()`, and `.with_constraints()`.
    - Engine automatically propagates these policies from the map node to all dynamically generated sub-tasks.
2.  **Unified Provider API**:
    - Upgraded `ProviderRegistry` to support nested namespaces (e.g., `cs.read.text`).
    - Introduced atomic IO providers: `read.text`, `read.bytes`, `write.text`, `write.bytes`, and `fs.exists`.
    - Removed the legacy and inconsistent `cs.file()` API.
3.  **Refined Control Flow**:
    - Verified and documented 'Cascading Skip' logic where skipped upstreams lead to downstream skipping with clear reasons.
    - Improved `TaskSkipped` event with semantic reason IDs.
4.  **Observability & Documentation**:
    - Enhanced `cs.visualize()` to distinctively style data, condition, and constraint edges.
    - Added comprehensive documentation on Control vs Data Flow and Dependency Injection patterns.

This completes the Layer 1 foundation, setting the stage for more advanced 
workflow features.
~~~~~

### 下一步建议
我们已经成功交付了 Layer 1。基于当前的状态，我建议下一步：
- **执行全面的测试套件**: 运行 `pytest` 确保在整合后所有功能依然稳健。
- **规划 Layer 2**: 我们可以开始讨论 Layer 2 的重点，可能涉及更复杂的调度策略或持久化缓存的深度集成。
- **债务检查**: 查看 `债务监测.md`，看看是否有在此过程中引入的新问题（例如，由于移除 `cs.file` 带来的潜在兼容性说明需求）。
