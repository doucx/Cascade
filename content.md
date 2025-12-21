好的，我们已经成功地将项目的开发流程规范化，并为新用户提供了现代化的入门体验。现在我们将这些重要的文档更新作为一个完整的单元进行提交。

## [COMMIT] docs: Create contribution guide and modernize tutorial

### 用户需求
1.  **环境规范化**: 记录并推广 `uv pip install -e .[dev]` 作为唯一的开发环境入口。
2.  **教程现代化**: 更新入门教程，展示阶段二引入的“直觉化”特性（如 `cs.format`）。
3.  **建立贡献指南**: 创建 `CONTRIBUTING.md` 以固化开发流程。

### 评论
这是一次关键的文档大修，显著提升了项目的开发者体验 (DX) 和新用户引导 (Onboarding)。通过创建 `CONTRIBUTING.md`，我们为社区协作建立了清晰的契约。通过现代化 `getting-started.md`，我们确保用户的第一印象是 Cascade 简洁、直观的一面。

### 目标
1.  提交新建的 `CONTRIBUTING.md` 文件。
2.  提交重写后的 `docs/tutorial/getting-started.md` 文件。
3.  提交对 `README.md` 的更新，添加开发者入口。

### 基本原理
将所有与文档和开发者指南相关的变更作为一个原子提交进行管理。这标志着我们“技术债务偿还与 DX 优化路线图”中定义的阶段三正式完成。

### 标签
#intent/document #flow/ready #priority/medium 
#comp/docs #scope/dx #ai/instruct
#task/domain/docs #task/object/onboarding-docs #task/action/completion
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交文档变更

我们将新创建和修改过的文档文件添加到 Git 暂存区，并创建一个内容明确的提交。

~~~~~act
git_add
CONTRIBUTING.md
docs/tutorial/getting-started.md
README.md
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
docs: Create contribution guide and modernize tutorial

This commit overhauls the project's documentation to improve both the contributor and new user experience, marking the completion of the DX enhancement roadmap.

Key changes:
1.  **Added `CONTRIBUTING.md`**: A new, comprehensive guide for developers is introduced. It standardizes the development environment setup using a single `uv pip install -e .[dev]` command and outlines testing procedures and commit message conventions.
2.  **Modernized `getting-started.md`**: The tutorial has been completely rewritten to be more intuitive and showcase modern Cascade features. The previous complex example involving YAML and lookups has been replaced with a simpler, more direct example using `cs.shell` and the new `cs.format` provider.
3.  **Updated `README.md`**: Added a "For Developers" section that links directly to the new contribution guide, making it easy for potential contributors to get started.
~~~~~

### 下一步建议
我们已经成功完成了 **“技术债务偿还与 DX 优化路线图”** 的全部三个阶段！

*   **阶段一**: 我们统一了开发环境。
*   **阶段二**: 我们让核心架构变得更符合直觉。
*   **阶段三**: 我们将这些改进固化为了文档和契约。

现在，Cascade 项目拥有了一个更加健壮、易于维护和贡献的基础。我们可以满怀信心地重新审视我们的宏大愿景：[Cascade 战略学说第三纪元：创世协议](../../01_current/总成/Cascade%20战略学说第三纪元：创世协议%20——%20从机械编排到生态涌现-251220.md)。

我建议下一步是，基于这个稳固的基础，开始实施“创世协议”中定义的第一批战术任务。
