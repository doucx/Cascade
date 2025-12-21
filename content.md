好的，我们现在进入**阶段三：文档与契约**。

为了确保 Cascade 的“隐性知识”转化为“显性文档”，并让新环境的搭建真正实现“一键化”，我们需要更新核心入门指南并创建开发者贡献规范。

## [WIP] docs: 建立开发契约与现代化入门指南

### 用户需求
1.  **环境规范化**: 记录并推广 `uv pip install -e .[dev]` 作为唯一的开发环境入口。
2.  **教程现代化**: 更新入门教程，展示阶段二引入的“直觉化”特性（如列表依赖、`cs.format`）。
3.  **建立贡献指南**: 创建 `CONTRIBUTING.md` 以固化开发流程。

### 评论
文档是项目的生命线。通过将最新的架构改动和环境管理经验沉淀为文档，我们不仅降低了新人的进入门槛，也为未来的自动化 CI/CD 流程奠定了基础。这是从“个人项目”迈向“成熟开源项目”的关键一步。

### 目标
1.  读取并分析现有的 `README.md` 和 `docs/tutorial/getting-started.md`。
2.  创建根目录下的 `CONTRIBUTING.md`。
3.  更新 `docs/tutorial/getting-started.md`，使用最新的 API 示例。
4.  在 `README.md` 中增加关于开发环境设置的简要说明。

### 基本原理
我们将遵循 [Cascade 技术债务偿还与 DX 优化路线图](../../01_current/项目/Cascade%20%E6%8A%80%E6%9C%AF%E5%80%BA%E5%8A%A1%E5%81%BF%E8%BF%98%E4%B8%8E%20DX%20%E4%BC%98%E5%8C%96%E8%B7%AF%E7%BA%BF%E5%9B%BE.md) 中的行动建议。重点是确保所有文档中的安装指令都是确定且一致的。

### 标签
#intent/document #flow/ready #priority/medium 
#comp/docs #scope/dx #ai/instruct
#task/domain/docs #task/object/contribution-guide #task/action/writing
#task/state/begin

---

### Script

#### Acts 1: 读取现有文档

我需要先查看目前的文档内容，以便进行精准的更新。

~~~~~act
read_file
README.md
~~~~~

~~~~~act
read_file
docs/tutorial/getting-started.md
~~~~~

### 下一步建议
在阅读完这些文件后，我将：
1.  编写 `CONTRIBUTING.md`，明确开发依赖安装、测试运行和代码规范。
2.  重写 `getting-started.md` 中的示例，将其从过时的 `cs.template`（在简单场景下）改为更简洁的 `cs.format`，并展示列表依赖的威力。
3.  最后通过一个 `[COMMIT]` 计划结束这一阶段。
