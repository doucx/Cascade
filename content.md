好的，收到。现在是偿还文档技术债的最佳时机。

你的要求非常明确：**构思，且仅构思**一个良好的、可扩展的、易于维护的文档结构。这意味着我现在不会产出具体的文档内容，而是为你设计和建立整个文档系统的“脚手架”。

我将基于业界公认的 **Diátaxis 文档框架** 和现代化的工具链来构思这个结构。该框架将文档分为四个明确的类别，以满足不同用户的不同需求，确保了极佳的可扩展性和可维护性。

## [WIP] feat(docs): 建立基础文档结构

### 用户需求
为 `cascade` 项目创建一个良好的、可扩展的、易于维护的文档结构，以偿还现有的文档债务，为后续的内容填充工作打下坚实的基础。

### 评论
这是一个至关重要的任务。一个优秀的文档结构不仅能提升用户体验，更能降低未来维护文档的成本。

我将采用以下策略：
1.  **采用 MkDocs**: 选择 `MkDocs` 作为文档生成工具。它基于 Markdown，配置简单，拥有丰富的插件生态（特别是 `mkdocs-material` 主题和 `mkdocstrings` 插件），非常符合 `Cascade` 追求优秀开发者体验（DX）的理念。
2.  **遵循 Diátaxis 框架**: 将文档内容明确划分为四个象限，创建对应的目录结构：
    *   **教程 (Tutorials)**: 面向初学者，提供手把手的引导。
    *   **操作指南 (How-to Guides)**: 面向目标导向的用户，提供解决特定问题的步骤。
    *   **概念阐述 (Explanation/Concepts)**: 面向寻求深入理解的用户，解释背后的原理和设计哲学。
    *   **技术参考 (Reference)**: 面向需要精确技术细节的专家，提供 API、CLI 等的详尽参考。
3.  **创建脚手架**: 我将创建所有必要的目录和空的 Markdown 文件，并配置好 `mkdocs.yml` 文件。这将为下一步的内容填充工作提供一个清晰的、即时可用的框架。

### 目标
1.  在项目根目录创建 `docs/` 文件夹。
2.  创建 `mkdocs.yml` 配置文件，定义网站结构、主题和插件。
3.  在 `docs/` 目录下，根据 Diátaxis 框架创建 `tutorial`, `how-to-guides`, `concepts`, `reference` 等子目录。
4.  在这些目录中创建对应的占位符 Markdown 文件，其文件名反映了 `Cascade 使用手册 v2.0.md` 中已有的内容构想。

### 基本原理
通过预先建立一个结构化的、由工具驱动的文档系统，我们可以确保未来的所有文档贡献都能被放置在正确的位置，从而避免混乱。`mkdocs.yml` 文件将成为文档导航的“唯一事实来源 (Single Source of Truth)”，使得添加或重排页面变得轻而易举。使用 `mkdocstrings` 插件则为未来从代码 docstring 自动生成 API 参考文档铺平了道路，极大地提高了可维护性。

### 标签
#intent/architect #intent/tooling #flow/ready #priority/high #comp/docs #scope/dx #ai/brainstorm #task/domain/docs #task/object/structure #task/action/establishment #task/state/begin

---

### Script

#### Acts 1: 创建文档目录结构

我们将创建顶层 `docs` 目录以及基于 Diátaxis 框架的子目录结构。我们还会添加一个 `assets` 目录，用于存放未来的图片等资源。

~~~~~act
run_command
~~~~~
~~~~~sh
mkdir -p docs/tutorial docs/how-to-guides docs/concepts docs/reference docs/assets
~~~~~

#### Acts 2: 创建 MkDocs 配置文件

创建 `mkdocs.yml` 文件。这将是整个文档站点的核心配置文件，定义了站点名称、主题和导航结构。我将选择流行的 `material` 主题，并预配置 `mkdocstrings` 插件，为未来的 API 文档自动化做好准备。

~~~~~act
write_file
mkdocs.yml
~~~~~
~~~~~yaml
site_name: Cascade
site_description: 'A modern, declarative automation library for Python.'
repo_url: https://github.com/your-repo/cascade-py # 请替换为你的仓库 URL
edit_uri: "" # 可选，指向编辑页面的链接

theme:
  name: material
  palette:
    # Palette toggle for light vs dark mode
    - media: "(prefers-color-scheme: light)"
      scheme: default
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - toc.integrate
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_root_heading: true

nav:
  - 'Home': 'index.md'
  - 'Tutorial':
    - 'Getting Started': 'tutorial/getting-started.md'
  - 'How-to Guides':
    - 'Defining Computations': 'how-to-guides/defining-computations.md'
    - 'Using Built-in Providers': 'how-to-guides/using-providers.md'
    - 'Building Complex Workflows': 'how-to-guides/advanced-workflows.md'
    - 'Managing Resources (DI)': 'how-to-guides/dependency-injection.md'
    - 'Improving Robustness': 'how-to-guides/improving-robustness.md'
  - 'Concepts':
    - 'Core Philosophy': 'concepts/philosophy.md'
  - 'Reference':
    - 'API Reference': 'reference/api.md'
    - 'CLI Tools': 'reference/cli-tools.md'
~~~~~

#### Acts 3: 创建占位符 Markdown 文件

现在，我们根据 `mkdocs.yml` 中定义的导航结构，创建对应的 Markdown 文件。这些文件目前只包含一个标题，作为后续内容填充的起点。

创建 `index.md` (主页)。

~~~~~act
write_file
docs/index.md
~~~~~
~~~~~markdown
# Welcome to Cascade

A modern, declarative automation library for Python.
~~~~~

创建教程文件。

~~~~~act
write_file
docs/tutorial/getting-started.md
~~~~~
~~~~~markdown
# Getting Started with Cascade
~~~~~

创建操作指南文件。

~~~~~act
write_file
docs/how-to-guides/defining-computations.md
~~~~~
~~~~~markdown
# How-to: Define Computations
~~~~~
~~~~~act
write_file
docs/how-to-guides/using-providers.md
~~~~~
~~~~~markdown
# How-to: Use Built-in Providers
~~~~~
~~~~~act
write_file
docs/how-to-guides/advanced-workflows.md
~~~~~
~~~~~markdown
# How-to: Build Complex Workflows
~~~~~
~~~~~act
write_file
docs/how-to-guides/dependency-injection.md
~~~~~
~~~~~markdown
# How-to: Manage Resources with Dependency Injection
~~~~~
~~~~~act
write_file
docs/how-to-guides/improving-robustness.md
~~~~~
~~~~~markdown
# How-to: Improve Workflow Robustness (Cache & Retry)
~~~~~

创建概念阐述文件。

~~~~~act
write_file
docs/concepts/philosophy.md
~~~~~
~~~~~markdown
# Concepts: The Core Philosophy of Cascade
~~~~~

创建技术参考文件。

~~~~~act
write_file
docs/reference/api.md
~~~~~
~~~~~markdown
# API Reference

This section is auto-generated from the source code.

::: cascade
~~~~~
~~~~~act
write_file
docs/reference/cli-tools.md
~~~~~
~~~~~markdown
# Reference: CLI Tools
~~~~~

### 下一步建议
我们已经成功地搭建了文档系统的骨架。现在，你可以随时开始填充内容了。

我建议的下一步是：
1.  **安装 `MkDocs` 依赖**: 运行 `pip install mkdocs mkdocs-material mkdocstrings-python`，并将其添加到 `pyproject.toml` 的 `dev` 依赖中。
2.  **启动本地文档服务器**: 在项目根目录运行 `mkdocs serve`，你将在本地看到一个功能齐全但内容为空的文档网站。
3.  **填充内容**: 从 **`docs/tutorial/getting-started.md`** 开始，将 `Cascade 使用手册 v2.0.md` 中的内容迁移并润色到这些新的 Markdown 文件中。

如果你同意，我们可以立刻开始 `pyproject.toml` 的修改和第一篇文档内容的填充工作。
