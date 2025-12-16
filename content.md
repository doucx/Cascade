这是一个配置与文件结构不匹配导致的问题。

**问题分析**：
1.  **MkDocs 原生不支持**同一目录下的多语言文件关联（如 `index.md` 和 `index.zh.md`），除非使用专门的插件。
2.  目前的配置中，`nav` 指向的是 `index.md`。由于没有插件介入，MkDocs 仅加载了 `index.md`（这是我们之前创建的英文占位符文件），并忽略了未被引用的 `index.zh.md`（中文文件），同时也因此产生了“文件存在但未在 nav 中”的警告。
3.  虽然您提到要“增加多语言支持”，但鉴于“中文是主要开发语言”，最佳的实践是将**中文直接作为默认文件**（`*.md`），将**英文作为变体文件**（`*.en.md`）。

为了修复这个问题并真正实现多语言支持，我们需要引入 `mkdocs-static-i18n` 插件，并调整文件命名策略。

## [FIX] papers(docs): 修复多语言配置并重构文件结构

### 用户需求
修复 MkDocs 构建时的警告，并确保访问文档时默认显示中文内容。同时保留多语言架构以支持未来的英文文档。

### 评论
必须引入 `mkdocs-static-i18n` 插件。这是 MkDocs 生态中处理文件级多语言（suffix mode）的标准解决方案。
我们将调整策略为：**中文即本体，英文即副本**。
- `filename.md`: 存放中文内容（默认）。
- `filename.en.md`: 存放英文内容（可选）。

### 目标
1.  在 `pyproject.toml` 中添加 `mkdocs-static-i18n` 依赖。
2.  执行文件重命名大挪移：
    - 将当前的英文占位符 `*.md` 重命名为 `*.en.md`。
    - 将当前的中文内容 `*.zh.md` 重命名为 `*.md`。
3.  更新 `mkdocs.yml` 以配置 `i18n` 插件，并将默认语言设为 `zh`。

### 基本原理
配置 `mkdocs-static-i18n` 插件并将 `default_language` 设为 `zh` 后，插件会自动将 `docs/foo.md` 视为中文页面，将 `docs/foo.en.md` 视为对应的英文页面，并自动注入语言切换器。这完美符合“中文为主”的开发策略，同时也解决了导航引用的问题。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/docs #task/object/i18n-config #task/action/correction #task/state/end

---

### Script

#### Acts 1: 添加插件依赖

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  "mkdocs-material",
  "mkdocstrings[python]",
]
~~~~~
~~~~~toml
  "mkdocs-material",
  "mkdocstrings[python]",
  "mkdocs-static-i18n",
]
~~~~~

#### Acts 2: 文件大挪移 (English -> .en.md)

首先，把现有的英文占位符文件（`*.md`）重命名为 `*.en.md`。这将它们腾出位置，同时也标记为“翻译版本”。

~~~~~act
move_file
docs/index.md
docs/index.en.md
~~~~~
~~~~~act
move_file
docs/tutorial/getting-started.md
docs/tutorial/getting-started.en.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/defining-computations.md
docs/how-to-guides/defining-computations.en.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/using-providers.md
docs/how-to-guides/using-providers.en.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/advanced-workflows.md
docs/how-to-guides/advanced-workflows.en.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/dependency-injection.md
docs/how-to-guides/dependency-injection.en.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/improving-robustness.md
docs/how-to-guides/improving-robustness.en.md
~~~~~
~~~~~act
move_file
docs/concepts/philosophy.md
docs/concepts/philosophy.en.md
~~~~~
~~~~~act
move_file
docs/reference/api.md
docs/reference/api.en.md
~~~~~
~~~~~act
move_file
docs/reference/cli-tools.md
docs/reference/cli-tools.en.md
~~~~~

#### Acts 3: 文件大挪移 (Chinese -> .md)

现在，将中文文件（`*.zh.md`）重命名为基础文件（`*.md`）。这意味着中文正式“上位”为默认文档。

~~~~~act
move_file
docs/index.zh.md
docs/index.md
~~~~~
~~~~~act
move_file
docs/tutorial/getting-started.zh.md
docs/tutorial/getting-started.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/defining-computations.zh.md
docs/how-to-guides/defining-computations.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/using-providers.zh.md
docs/how-to-guides/using-providers.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/advanced-workflows.zh.md
docs/how-to-guides/advanced-workflows.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/dependency-injection.zh.md
docs/how-to-guides/dependency-injection.md
~~~~~
~~~~~act
move_file
docs/how-to-guides/improving-robustness.zh.md
docs/how-to-guides/improving-robustness.md
~~~~~
~~~~~act
move_file
docs/concepts/philosophy.zh.md
docs/concepts/philosophy.md
~~~~~
~~~~~act
move_file
docs/reference/api.zh.md
docs/reference/api.md
~~~~~
~~~~~act
move_file
docs/reference/cli-tools.zh.md
docs/reference/cli-tools.md
~~~~~

#### Acts 4: 配置 mkdocs.yml

最后，配置 `mkdocs.yml` 以使用 `i18n` 插件。我们需要移除之前的手动 `extra.alternate` 配置，改用插件的标准配置。

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
  language: zh
  palette:
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
  - i18n:
      default_language: zh
      languages:
        zh:
          name: 中文
          build: true
        en:
          name: English
          build: true

nav:
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

### 下一步建议

修复已完成。请执行以下步骤使更改生效：

1.  **安装新依赖**:
    ```bash
    pip install "mkdocs-static-i18n"
    ```
2.  **重启服务**:
    ```bash
    mkdocs serve
    ```

现在：
- `http://localhost:8080/` 将直接显示中文内容（因为 `index.md` 现在是中文的）。
- 不会再有“页面未引用”的警告。
- 页面右上角会出现语言切换器，允许你在中文和英文（目前仅为占位符）之间切换。

我们可以继续填充“核心哲学”文档了，这次将直接写入 `docs/concepts/philosophy.md`。
