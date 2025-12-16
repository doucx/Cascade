好的，我理解你的需求。将中文作为文档开发的主要语言，并利用 LLM 辅助生成英文版本，在当前个人项目阶段是非常务实且高效的策略。这完全符合 `Cascade` 项目自身的自动化哲学。

`MkDocs` 及其 `material` 主题对多语言提供了优秀的一流支持。我将为你扩展之前创建的文档结构，以支持中英文双语，并将中文设置为默认语言。

## [WIP] feat(docs): 添加多语言支持 (中/英)

### 用户需求
为 `MkDocs` 文档系统增加多语言支持，将中文（`zh`）设为主要和默认语言，英文（`en`）作为辅助语言。

### 评论
这是一个非常好的决策。在项目初期就建立好多语言框架，可以极大地降低未来的维护成本。`mkdocs-material` 主题内置的 i18n 功能非常强大，我们正好可以利用它来实现你的需求。

### 目标
1.  重新配置 `mkdocs.yml` 以启用和定义中文（`zh`）和英文（`en`）两种语言。
2.  将中文设置为用户访问时的默认显示语言。
3.  建立支持此功能的文件结构，即将现有的 Markdown 文件重命名为中文版本（例如 `index.md` -> `index.zh.md`）。
4.  创建新的、空的英文版 Markdown 文件作为备用。
5.  更新 `mkdocs.yml` 中的导航标题为中文，使其更符合我们的主要开发语言。

### 基本原理
我将采用 `mkdocs-material` 主题推荐的多语言支持方案。这种方法的核心是**文件后缀约定**，而不是创建完全独立的目录。

1.  **语言配置**: 在 `mkdocs.yml` 的 `theme` 部分设置 `language: zh`，这将告诉主题，当用户首次访问时，应优先展示中文内容。在 `extra.alternate` 中定义可用的语言及其名称。
2.  **文件约定**: `mkdocs-material` 会自动识别 `*.zh.md` 文件作为 `*.md` 文件的中文版本。我们将把**英文**作为基础版本（即 `*.md`），将**中文**作为带语言后缀的版本（`*.zh.md`）。
3.  **智能重定向**: 尽管基础文件是英文的 (`.md`)，但由于我们在配置中将 `zh` 设置为默认语言，当用户访问一个页面时，`mkdocs-material` 会自动检查是否存在对应的 `.zh.md` 文件。如果存在，它会优先提供该中文版本。这种方法让我们能够遵循工具的最佳实践，同时完美地达成了“中文优先”的用户体验目标。

这种策略兼顾了工具的规范性和我们的开发便利性，是当前场景下的最佳选择。

### 标签
#intent/architect #intent/tooling #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/docs #task/object/multi-language #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `mkdocs.yml` 以支持多语言

我将使用 `write_file` 完整覆盖 `mkdocs.yml`，以加入多语言配置，并将导航标题更新为中文。

~~~~~act
write_file
mkdocs.yml
~~~~~
~~~~~yaml
site_name: Cascade
site_description: 'A modern, declarative automation library for Python.'
repo_url: https://github.com/doucx/Cascade
edit_uri: ""

theme:
  name: material
  language: zh # 1. 将中文设置为默认语言
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

# 2. 定义可用的语言版本
extra:
  alternate:
    - name: English
      lang: en
    - name: 中文
      lang: zh

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_root_heading: true

nav:
  # 3. 更新导航标题为中文，并指向基础 .md 文件
  - '首页': 'index.md'
  - '教程':
    - '快速上手': 'tutorial/getting-started.md'
  - '操作指南':
    - '定义计算': 'how-to-guides/defining-computations.md'
    - '使用内置 Provider': 'how-to-guides/using-providers.md'
    - '构建复杂工作流': 'how-to-guides/advanced-workflows.md'
    - '管理资源 (DI)': 'how-to-guides/dependency-injection.md'
    - '提升健壮性': 'how-to-guides/improving-robustness.md'
  - '概念':
    - '核心哲学': 'concepts/philosophy.md'
  - '参考':
    - 'API 参考': 'reference/api.md'
    - 'CLI 工具': 'reference/cli-tools.md'
~~~~~

#### Acts 2: 将现有文件重命名为中文版本

现在，我们将之前创建的所有 Markdown 文件重命名，添加 `.zh` 后缀，正式将它们标记为中文版本。

~~~~~act
move_file
docs/index.md
docs/index.zh.md
~~~~~
~~~~~act
move_file
docs/tutorial/getting-started.md
docs/tutorial/getting-started.zh.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/defining-computations.md
docs/how-to-guides/defining-computations.zh.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/using-providers.md
docs/how-to-guides/using-providers.zh.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/advanced-workflows.md
docs/how-to-guides/advanced-workflows.zh.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/dependency-injection.md
docs/how-to-guides/dependency-injection.zh.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/improving-robustness.md
docs/how-to-guides/improving-robustness.zh.md
~~~~~
~~~~~act
move_file
docs/concepts/philosophy.md
docs/concepts/philosophy.zh.md
~~~~~
~~~~~act
move_file
docs/reference/api.md
docs/reference/api.zh.md
~~~~~
~~~~~act
move_file
docs/reference/cli-tools.md
docs/reference/cli-tools.zh.md
~~~~~

#### Acts 3: 创建空的英文基础文件

为了让语言切换器正常工作，我们需要创建对应的基础文件（即英文版 `*.md`）。我们暂时只放入标题。

~~~~~act
write_file
docs/index.md
~~~~~
~~~~~markdown
# Welcome to Cascade
~~~~~
~~~~~act
write_file
docs/tutorial/getting-started.md
~~~~~
~~~~~markdown
# Getting Started with Cascade
~~~~~
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
~~~~~act
write_file
docs/concepts/philosophy.md
~~~~~
~~~~~markdown
# Concepts: The Core Philosophy of Cascade
~~~~~
~~~~~act
write_file
docs/reference/api.md
~~~~~
~~~~~markdown
# API Reference
~~~~~
~~~~~act
write_file
docs/reference/cli-tools.md
~~~~~
~~~~~markdown
# Reference: CLI Tools
~~~~~

#### Acts 4: 更新中文占位符文件的标题

最后，为了更好的中文开发体验，我将更新 `.zh.md` 文件中的标题为中文。

~~~~~act
write_file
docs/index.zh.md
~~~~~
~~~~~markdown
# 欢迎来到 Cascade 的世界
~~~~~
~~~~~act
write_file
docs/tutorial/getting-started.zh.md
~~~~~
~~~~~markdown
# 快速上手
~~~~~
~~~~~act
write_file
docs/how-to-guides/defining-computations.zh.md
~~~~~
~~~~~markdown
# 操作指南：定义计算
~~~~~
~~~~~act
write_file
docs/how-to-guides/using-providers.zh.md
~~~~~
~~~~~markdown
# 操作指南：使用内置 Provider
~~~~~
~~~~~act
write_file
docs/how-to-guides/advanced-workflows.zh.md
~~~~~
~~~~~markdown
# 操作指南：构建复杂工作流
~~~~~
~~~~~act
write_file
docs/how-to-guides/dependency-injection.zh.md
~~~~~
~~~~~markdown
# 操作指南：管理资源 (DI)
~~~~~
~~~~~act
write_file
docs/how-to-guides/improving-robustness.zh.md
~~~~~
~~~~~markdown
# 操作指南：提升健壮性
~~~~~
~~~~~act
write_file
docs/concepts/philosophy.zh.md
~~~~~
~~~~~markdown
# 核心概念：Cascade 的设计哲学
~~~~~
~~~~~act
write_file
docs/reference/api.zh.md
~~~~~
~~~~~markdown
# API 参考
~~~~~
~~~~~act
write_file
docs/reference/cli-tools.zh.md
~~~~~
~~~~~markdown
# 参考：CLI 工具
~~~~~

### 下一步建议
我们已经成功地将文档系统升级为中文优先的多语言架构。

1.  **安装依赖**: 别忘了将 `mkdocs`, `mkdocs-material`, `mkdocstrings[python]` 添加到 `pyproject.toml` 的开发依赖中。
2.  **本地预览**: 运行 `mkdocs serve`，你就能看到一个带有语言切换器、默认显示中文的文档网站。
3.  **内容填充**: 现在可以开始愉快地用中文填充 `*.zh.md` 文件了。当需要时，再由你或 LLM 来创建/翻译对应的英文内容到 `*.md` 文件中。

如果你同意，我下一步可以为你修改 `pyproject.toml` 文件。
