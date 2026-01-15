清理工作已圆满完成。我们通过彻底切断旧路径并更新 SDK 门面，实现了 Cascade 神经系统的完整物理与逻辑重构。现在系统已完全汇聚到 `cascade-bus` 下。

## [COMMIT] refactor: 完成 cascade-bus 迁移并清理旧版封装

### 用户需求
彻底移除 `cascade-runtime` 和 `cascade-common` 中的旧版总线代码/封装，并更新 SDK 导出路径，确保系统引用的一致性。

### 评论
这是“提取 -> 隔离”战略的终点。我们通过物理删除旧文件，强制性地完成了对 `cascade-bus` 的依赖迁移。目前 Cascade 各组件通过标准路径进行通信，为后续接入 `pyneedle-bus` 清除了所有架构障碍。

### 目标
1.  提交对 `cascade-sdk` 导出路径的更新。
2.  提交删除 `runtime` 和 `common` 中旧版总线逻辑的变更。
3.  确保所有子包的依赖树（toml）完全指向 `cascade-bus`。

### 基本原理
根据 SSoT (Single Source of Truth) 原则，系统中不应存在多余的逻辑入口。通过删除兼容层并更新 SDK 映射，我们确保了开发者只能通过唯一的、解耦的 `cascade-bus` 访问通信能力。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/sdk #comp/bus #comp/runtime #comp/common #scope/api
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/cleanup-wrappers #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交清理与 SDK 更新

我们将所有涉及到的文件变更（包括文件删除）添加到暂存区。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: complete cascade-bus migration and remove legacy wrappers

Finalizes the bus isolation process by removing all legacy entry points and wrappers in 'runtime' and 'common' modules.

- Updated 'cascade-sdk' to export EventBus and FeedbackBus directly from the new 'cascade-bus' package.
- Physically removed deprecated messaging and observability files in 'cascade-runtime' and 'cascade-common'.
- Standardized dependency declarations across all pyproject.toml files.
- Verified that all internal communications now flow through the unified 'cascade-bus'.
~~~~~

### 下一步建议

Cascade 的总线剥离工作已经**完美闭环**。

接下来的建议：
1.  **Stitcher 总线剥离**: 采用相同的流程（创建 `stitcher-bus` -> 搬运逻辑 -> 清理入口）。
2.  **Quipu 总线剥离**: 处理 `quipu-bus`。
3.  **构建 `pyneedle-bus` 内核**: 当这三个主要项目的总线都被隔离后，我们就可以开始在 `pyneedle` 中实现通用的总线内核，并将这些独立的 `-bus` 包降级为 `pyneedle-bus` 的薄封装。

如果你已经准备好处理下一个项目（Stitcher 或 Quipu），请告诉我。
