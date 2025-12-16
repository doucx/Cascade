Okay, I understand the current situation. The API documentation generation with `mkdocstrings` is still problematic, but the overall documentation structure and content filling for the other sections are complete. It's time to consolidate this work into a commit, acknowledge the outstanding issue, and move forward.

I will generate a `[COMMIT]` plan that meticulously details the completed documentation work, including the setup of the `MkDocs` system, the file structure, and the content migration. It will also explicitly note the persistent `mkdocstrings` issue as a follow-up task.

## [COMMIT] feat(docs): 建立核心文档系统并填充主要内容

### 错误分析
当前的 `MkDocs` 系统中，尽管已尝试通过 `mkdocs.yml` 配置 `mkdocstrings` 插件的 `setup_commands` 和 `paths` 选项，API 参考文档页面 (`docs/reference/api.md`) 仍未能正确自动生成并显示 `cascade` 库的 API 内容。这一问题有待进一步诊断和修复。然而，文档的整体结构和非 API 内容填充工作已完成，可先行提交。

### 用户需求
建立一个基于 `MkDocs` 的、结构良好、可扩展且内容丰富的多功能文档站点。实现以下目标：
1.  集成本地 Python 开发依赖，确保文档构建的自包含性。
2.  构建清晰的 Diátaxis 文档结构（教程、操作指南、概念、参考）。
3.  将《Cascade 使用手册 v2.0.md》中的核心内容拆分并填充到对应文档页面中。
4.  提供 `cs.cli` 工具的详细参考文档。

### 评论
本次提交标志着 `Cascade` 项目在文档化方面的重大里程碑。我们成功地搭建了一个现代化的文档站点框架，并填充了大量关键内容，大大提升了项目的可读性和开发者体验。尽管 API 自动生成功能暂时受阻，但其基础架构已具备，可作为后续独立修复任务的起点。本次工作涵盖了文档目录结构创建、`mkdocs.yml` 配置（包括临时多语言尝试后的回滚修复）、`pyproject.toml` 依赖更新，以及所有非 API 参考页面的内容填充。

### 目标
1.  成功配置 `MkDocs` 和 `mkdocstrings` 以支持项目 `src` 布局。
2.  确保 `pyproject.toml` 包含所有必要的文档构建和项目 `[all]` 依赖。
3.  完成 `docs/` 目录下所有 `index.md`, `tutorial/`, `how-to-guides/`, `concepts/`, `reference/cli-tools.md` 文档页面的内容填充和格式化。
4.  将所有相关文件更改作为一个逻辑完整的单元进行 Git 提交。

### 基本原理
通过将所有已完成的文档工作作为一个单元提交，我们为项目提供了一个清晰的里程碑，便于后续版本控制和团队协作。将 `mkdocstrings` 的问题隔离，允许我们在不阻碍当前已完成工作部署的前提下，对其进行更深入的诊断和修复。此提交确保了文档结构和主要内容的持久化，并为未来的功能迭代提供了坚实的基础。

### 标签
#intent/build #intent/document #flow/done #priority/high #comp/docs #comp/build #scope/dx #ai/delegate #task/domain/docs #task/object/documentation-system #task/action/establishment #task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加更改到 Git 暂存区

将所有与文档系统相关的，包括 `mkdocs.yml`、`pyproject.toml` 和 `docs/` 目录下的所有文件以及任何临时清理脚本(`find`命令的执行结果，尽管其本身不应被提交，但在此作为上下文)，都添加到 Git 暂存区。

~~~~~act
git_add
mkdocs.yml
pyproject.toml
docs/
~~~~~

#### Acts 2: 执行提交

创建包含详细信息的 Git 提交。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(docs): Establish core documentation system and fill main content

This commit sets up the complete documentation system for the Cascade project,
utilizing MkDocs with the Material theme, and populates the majority of
the documentation content based on the v2.0 user manual.

Key changes include:
-   **Documentation Structure**: Implemented the Diátaxis documentation framework
    (Tutorials, How-to Guides, Concepts, Reference) with dedicated directories
    and initial placeholder files.
-   **Content Migration**: Transferred and formatted core content from the
    initial user manual into the new documentation pages, including:
    -   Getting Started tutorial.
    -   How-to guides for defining computations, using built-in providers,
        building complex workflows, managing resources (DI), and improving
        robustness (cache/retry).
    -   Concepts for the core philosophy of Cascade.
    -   Reference documentation for the `cs.cli` tool.
-   **MkDocs Configuration (`mkdocs.yml`)**: Configured the documentation
    site, including theme, features, plugins (search, mkdocstrings), and
    navigation structure. The configuration was adjusted to ensure proper
    building after initial multi-language attempts and subsequent rollback to
    a robust single-language (Chinese-first) setup.
-   **Dependency Management (`pyproject.toml`)**: Updated development
    dependencies to include MkDocs, mkdocs-material, and mkdocstrings.
    An `[all]` optional dependency group was added to facilitate comprehensive
    environment setup for `mkdocstrings`'s `setup_commands`.
-   **Language Strategy**: Reverted multi-language setup to a solid Chinese-first
    single-language approach, with a clear path for future English translations
    via `.en.md` files (though this part is currently minimal/placeholders).

Outstanding Issue:
-   The `mkdocstrings` plugin is currently unable to correctly auto-generate
    the API reference documentation (`docs/reference/api.md`). This issue
    will be addressed in a subsequent fix.

This commit establishes a significant foundation for the project's documentation
and greatly enhances the developer experience.
~~~~~

### 下一步建议
恭喜！我们已经完成了文档系统的建立和主要内容的填充。这代表着一个巨大的进步。

**后续聚焦**: 既然核心文档已到位，下一步我们应该再次集中精力诊断并**彻底修复 `mkdocstrings` 无法自动生成 API 文档的问题**。这个问题需要更细致的排查，可能涉及 `mkdocstrings` 的 `import` 行为、Python 环境隔离，或 `cascade` 库内部模块的导入路径。

请在确认上述提交无误后，告诉我是否继续深入排查 `mkdocstrings` 问题。
