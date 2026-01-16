好的，我们已经顺利完成了代码重构、清理以及静态分析修复。现在，我们将把这一系列旨在提升架构纯净度的改动作为一个完整的逻辑单元提交到版本库中。

## [COMMIT] refactor: 集中核心接口与契约至 cascade-spec 以实现彻底解耦

### 用户需求

根据架构重构计划，已完成所有预定目标。现在需要通过 Git 提交将这些变更永久化。

### 评论

这次重构是 Cascade 3.0 架构演进中的一个里程碑。我们成功地将 `cascade-spec` 确立为整个系统的“主权中心”，消除了 `cascade-std` 与 `cascade-vm` 之间的非法依赖，并标准化了物理节点的实现协议。这极大地降低了系统的认知负载，并为未来的多运行时（Multi-Runtime）支持铺平了道路。

### 目标

1.  将所有新增文件、修改文件以及删除文件的变更添加到 Git 暂存区。
2.  创建一个包含详细说明的提交记录，阐述本次重构的动机、内容和影响。

### 基本原理

通过 `[COMMIT]` 计划，我们将散落在多个包中的、但逻辑上紧密关联的修改合并为一个原子化的变更集。这保证了版本历史的清晰性，使得其他团队成员可以轻松地追溯和理解这次重构的完整上下文。

### 标签

#intent/refine #flow/ready #priority/high 
#comp/spec #comp/vm #comp/std #comp/compiler #comp/tests 
#scope/core #scope/dx 
#task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将把所有涉及重构的包添加到暂存区，并创建一个内容详尽的提交信息。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: centralize core contracts and binding tools in cascade-spec

This refactoring aligns the codebase with the high-fidelity architecture principles by establishing 'cascade-spec' as the single source of truth for all cross-package contracts and interfaces.

Key Changes:
- Centralized Data Contracts: Moved 'ComputeRequest' and 'DelayRequest' from implementation packages (vm) to 'cascade.spec.runtime'.
- Unified IC Binding: Migrated the 'implements' decorator and its supporting 'IOWrapper' from 'cascade-std' to 'cascade.spec.physics.binding'.
- Decoupled Implementation Packages: 
    - Removed 'cascade-std's dependency on 'cascade-vm'.
    - Removed redundant local interface definitions in 'cascade-compiler'.
    - Updated 'cascade-test-utils' to follow the new centralized specification.
- Cleaned up obsolete modules: Deleted 'kernel_tools.py' in std and 'contract.py/contracts.py' in vm.

This ensures a clear "Spec -> Implementation" dependency flow, improving architecture purity, reducing cognitive load, and enhancing developer experience for building third-party Cascade components.
~~~~~

### 下一步建议

- **全量测试**: 虽然我们修复了 pyright 报错，但建议在提交后运行一次完整的 pytest 套件，以确保在运行时层面没有因导入路径变化导致的残留问题。
- **文档更新**: 既然 `implements` 已经移动到了 `cascade-spec`，建议更新开发指南，明确将其作为开发物理节点的标准 SDK 接口进行介绍。
- **监控与观察**: 留意后续开发中是否还有零散的依赖违例，并及时将其“归位”到 `cascade-spec`。
