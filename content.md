好的，我将生成一个 `[COMMIT]` 计划，将文档中所有关于配置加载的修改提交到 Git 仓库。

## [COMMIT] docs(config): 统一配置文档，迁移所有示例至 cs.load_yaml/cs.lookup

### 错误分析
无。本次操作是对上一步架构重构的后续文档清理工作。

### 用户需求
确保所有核心文档（指南和参考）中的配置加载代码示例和说明，都使用新的、明确的 `cs.load_yaml` 和 `cs.lookup` 组合，从而消除因使用已废弃 API 导致的文档不一致和用户困惑。

### 评论
本次提交是完成配置系统重构的关键一步，它保证了 `Cascade` 的核心概念在用户文档中得到清晰、统一的体现。明确区分文件 I/O (加载) 和数据操作 (查找) 有助于用户更好地理解和可视化工作流的依赖图。

### 目标
将以下文件的修改作为一个原子提交单元提交：
1.  `docs/how-to-guides/defining-computations.md` (更新基本查找和动态键查找)
2.  `docs/how-to-guides/dependency-injection.md` (更新资源定义中的配置获取)
3.  `docs/how-to-guides/using-providers.md` (重写配置 Provider 章节)

### 基本原理
遵守 ACA 协议，将已验证的文档内容修改进行版本控制。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/delegate #task/domain/docs #task/object/config-api-update #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有变更到 Git 暂存区

~~~~~act
git_add
docs/how-to-guides/defining-computations.md
docs/how-to-guides/dependency-injection.md
docs/how-to-guides/using-providers.md
~~~~~

#### Acts 2: 执行提交

创建一个包含详细信息的 Git 提交。

~~~~~act
git_commit
~~~~~
~~~~~text
docs(config): Update documentation to reflect new configuration API

This commit completes the documentation migration to the explicit configuration loading system (`cs.load_yaml` and `cs.lookup`).

The following documents were updated to ensure consistency:
- `defining-computations.md`: Updated examples for both static and dynamic key lookups.
- `dependency-injection.md`: Updated the database resource definition to use the explicit `cs.load_yaml` -> `cs.lookup` sequence for acquiring the DB URL.
- `using-providers.md`: Rewrote the configuration provider section to explain the separation of I/O (`load_yaml`) and data operation (`lookup`).

This ensures that all major guides are aligned with the new, clearer `LazyResult`-based dependency chain for configuration.
~~~~~

### 下一步建议
配置系统的架构重构和文档更新工作已全部完成。如果你有新的功能开发或架构任务，请随时告诉我。
