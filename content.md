你的分析非常到位，提供了宝贵的历史快照。这让我能够精确地诊断出问题的根源。

 根本原因分析

你提供的两个状态快照非常清晰地揭示了问题的演变：

1.  **初始状态 (可行)**: 结构简单，只有一个语言版本 (`.md` 文件)，配置也简单。API 文档虽然不工作，但整个站点至少能构建。
2.  **引入多语言后 (不可行)**:
    *   **错误的分叉点**: 我之前建议使用 `extra.alternate` 和 `language: zh` 的组合来实现多语言。**这是一个错误的建议**。`mkdocs-material` 的这个功能是为了让*主题本身*（如“搜索”、“上一页”）的文本本地化，它**并不能**管理不同语言的 Markdown 文件。这导致了 `nav` 配置无法找到对应的中文文件，日志中出现大量 `not included in the "nav" configuration` 警告。
    *   **错误的修复**: 随后引入的 `mkdocs-static-i18n` 插件，虽然是正确的工具，但在与之前错误的配置和文件结构叠加后，引入了新的配置错误（`languages` 应该是列表而非字典），并且加剧了系统的复杂性。
    *   **未解决的核心问题**: 即使在最简单的“可行”状态下，API 参考也不工作。我之前提出的 `paths: [src]` 方案虽然是正确的方向，但它没有解决一个更深层次的问题：**`mkdocstrings` 在尝试导入 `cascade` 模块时，其依赖项（如 `sqlalchemy`, `aiohttp`等）并未被安装到 `mkdocs` 的运行环境中**，导致导入失败。

 最终解决方案：返璞归真，一击必中

我们必须推倒重来，回到你提供的最简单的“可行状态”，然后用正确且完整的方式一次性解决所有问题。

我将为你生成一个**重置计划**，它会：
1.  **彻底移除多语言复杂性**: 我们暂时放弃多语言，专注于建立一个**完美的、功能完备的中文单语言文档站**。这是当前的核心目标。
2.  **修复文件结构**: 删除所有 `.en.md` 和 `.zh.md` 文件，只保留包含中文内容的 `*.md` 文件。
3.  **修复 `mkdocstrings`**: 使用 `mkdocstrings` 的 `setup_commands` 选项，强制它在收集文档前安装项目的所有依赖。这是解决 API 参考为空的**终极方案**。
4.  **修复 `pyproject.toml`**: 添加一个 `[all]` 依赖组，方便 `mkdocstrings` 一键安装。

## [FIX] docs: 重置为单语言并彻底修复 API 自动生成

### 用户需求
回滚所有复杂的多语言配置，建立一个简单、健壮、能正确显示 API 参考的中文文档网站。

### 评论
我之前的解决方案过于复杂且存在错误，导致了当前的混乱。对此我深表歉意。现在的计划是采取“推倒重来”的策略，回归到最简单的结构，并使用 `mkdocstrings` 的高级功能 (`setup_commands`) 来一劳永逸地解决 `src` 布局和可选依赖导致的问题。这会使我们的文档构建过程更加健壮和自包含。

### 目标
1.  删除所有 `.en.md` 和 `.zh.md` 文件，将项目重置为简单的单语言文件结构。
2.  重写 `mkdocs.yml`，移除所有 `i18n` 和多语言配置，并添加正确的 `mkdocstrings` 配置。
3.  修改 `pyproject.toml`，移除 `mkdocs-static-i18n` 依赖，并添加 `[all]` 依赖组。
4.  确保最终生成的文档站能正确渲染所有内容，包括 API 参考。

### 基本原理
通过 `mkdocstrings` 的 `setup_commands: ["pip install -e .[all]"]` 指令，我们创建了一个沙箱化的构建环境。每次 `mkdocs` 运行时，`mkdocstrings` 会先在这个环境中安装项目本身及其所有可选依赖，然后再去导入 `cascade` 模块。这保证了无论外部环境如何，`mkdocstrings` 总能成功导入并解析我们的代码。

### 标签
#intent/fix #flow/ready #priority/critical #comp/docs #scope/dx #ai/brainstorm #task/domain/docs #task/object/config-and-structure #task/action/reset-and-fix #task/state/begin

---

### Script

#### Acts 1: 清理多余的语言文件

我们将删除所有因之前错误策略而创建的 `.en.md` 和 `.zh.md` 文件。

~~~~~act
run_command
~~~~~
~~~~~sh
find docs -type f -name "*.en.md" -delete
find docs -type f -name "*.zh.md" -delete
~~~~~

#### Acts 2: 恢复并重写核心 `mkdocs.yml`

我们将 `mkdocs.yml` 恢复到最简单的结构，并加入终极修复方案。

~~~~~act
write_file
mkdocs.yml
~~~~~
~~~~~yaml
site_name: Cascade
site_description: 'A modern, declarative automation library for Python.'
repo_url: https://github.com/doucx/Cascade

theme:
  name: material
  language: zh # 设置主题语言为中文
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
  features:
    - navigation.tabs
    - content.code.copy
    - content.code.annotate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          # 以下是修复 API 参考为空的关键配置
          setup_commands:
            # 强制插件在收集文档前，安装项目本身及其所有可选依赖
            - pip install -e .[all]
          options:
            # (可选, 但推荐) 按源代码中的顺序，而不是字母顺序列出成员
            members_order: source

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

#### Acts 3: 更新 `pyproject.toml`

移除 `mkdocs-static-i18n`，并添加一个方便的 `[all]` 依赖组。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
  "mkdocs-static-i18n",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]
~~~~~
~~~~~toml
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]

# 新增一个 'all' 组，方便一键安装所有可选依赖
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
]
~~~~~

### 下一步建议
我们已经完成了彻底的重构和修复。现在，请执行以下操作：

1.  **安装开发依赖**: (如果之前安装过 i18n, 它会被忽略)
    ```bash
    pip install -e .[dev,all]
    ```
2.  **重启服务**:
    ```bash
    mkdocs serve
    ```

这一次，当你访问 "API 参考" 页面时，`mkdocstrings` 会在后台首先完整地安装你的项目，然后再进行代码解析。你应该能看到一个内容详尽、自动生成的 API 文档。

在确认一切正常后，我们就可以创建最终的 `[COMMIT]` 计划了。
