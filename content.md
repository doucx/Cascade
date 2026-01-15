好的，测试通过意味着我们已经成功完成了这次“换心手术”的第一个阶段。现在我们将这些变更作为一个完整的逻辑单元提交到 Git。

## [COMMIT] refactor(bus): 将 EventBus 和 FeedbackBus 提取到 cascade-bus 包

### 用户需求
将分散在 `cascade-runtime` 和 `cascade-common` 中的总线逻辑提取到独立的 `cascade-bus` 包中，为后续迁移到 `pyneedle-bus` 奠定架构基础。

### 评论
这是一次标准的架构解耦。通过引入 `cascade-bus`，我们确立了系统的“神经系统”是一个独立的、可复用的组件，而不是运行时的附属品。同时，通过薄封装保持了现有代码的零成本兼容。

### 目标
1.  提交新创建的 `cascade-bus` 包。
2.  提交对 `runtime` 和 `common` 包依赖及代码的重构。
3.  提交根目录工作区的配置更新。

### 基本原理
遵循“提取 -> 隔离”原则。我们不仅移动了代码，还移动了相关的资源文件（Locales），并确保了所有的 Import 路径在 `cascade-bus` 内部是自洽的。通过在原位置保留同名模块并进行 re-export，我们实现了对现有代码库的透明迁移。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/bus #comp/runtime #comp/common #scope/core
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/migration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有涉及到的包和配置文件添加到暂存区并创建提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(bus): extract EventBus and FeedbackBus into dedicated cascade-bus package

Moves event-driven telemetry and user feedback messaging out of 'runtime' and 'common' modules. This is the first stage of the Needle-Bus migration, isolating bus logic to prepare for unification under the PyNeedle kernel.

- Created 'cascade-bus' package with 'core' (EventBus) and 'feedback' (FeedbackBus) modules.
- Migrated i18n locales to 'cascade-bus'.
- Implemented thin wrappers in 'cascade-runtime' and 'cascade-common' to maintain API compatibility.
- Updated workspace dependencies and build configurations.
~~~~~

### 下一步建议

`cascade-bus` 已经稳固地建立起来了。接下来的建议：
- **Stitcher 迁移**: 按照相同的模式，处理 `stitcher` 的总线提取。
- **构建 `pyneedle-bus`**: 开始实现真正的统一内核。
- **清理封装**: 在 `pyneedle` 就绪后，我们将彻底删除这些“薄封装”，直接指向最终的统一总线。
