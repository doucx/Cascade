这是一个配置格式兼容性问题。报错信息非常明确：`languages` 选项期望一个**列表 (List)**，但我之前配置的是**字典 (Dict)**。

虽然 `mkdocs-static-i18n` 的文档在不同版本间可能有所混淆，但我们要严格遵循报错信息的指引。

同时，为了不耽误进度，我会在修复配置的同时，继续执行你之前的指令：**填充“核心哲学”文档**。

## [FIX & FEAT] docs: 修复构建错误并填充核心哲学文档

### 用户需求
1.  **修复配置**: 修改 `mkdocs.yml`，解决 `Plugin 'i18n' option 'languages': Expected a list of items` 错误，使文档服务能正常启动。
2.  **填充内容**: 将《Cascade 使用手册》中的“核心哲学”章节迁移至 `docs/concepts/philosophy.md`。

### 评论
对于 `mkdocs-static-i18n` 插件，当它要求列表格式时，正确的配置方式是提供一个包含 `locale` 和 `name` 字段的对象列表。我还将显式设置 `default: true` 属性，以确保中文被正确识别为默认语言。

关于文档填充，我将把手册中的第一节内容转化为一篇独立的“概念”文档，这对帮助用户建立正确的 Cascade 心智模型至关重要。

### 目标
1.  重写 `mkdocs.yml`，使用列表格式配置语言。
2.  写入 `docs/concepts/philosophy.md`，解释 "Everything is a Computable Value" 的核心理念。

### 基本原理
1.  **配置修复**: 将 `languages` 从字典改为列表结构 `[{locale: zh, ...}, {locale: en, ...}]`，严格匹配插件的校验逻辑。
2.  **文档迁移**: 提取手册中关于 `LazyResult`、统一依赖图和按需执行的描述，添加适当的 Markdown 格式和引言，使其成为一篇完整的概念性文章。

### 标签
#intent/fix #intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/docs #task/object/config-and-content #task/action/correction-and-population #task/state/continue

---

### Script

#### Acts 1: 修复 `mkdocs.yml` 配置

我们将 `languages` 字段改为列表格式。

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
      docs_structure: suffix
      languages:
        - locale: zh
          name: 中文
          default: true
        - locale: en
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

#### Acts 2: 填充“核心哲学”文档

将手册内容转化为独立的文档页面。

~~~~~act
write_file
docs/concepts/philosophy.md
~~~~~
~~~~~markdown
# 核心哲学：万物皆为可计算值

`Cascade` 的设计基于一个简单而强大的哲学：**工作流中的每一个节点，无论它来自 Python 代码、配置文件还是外部命令，都是一个“可计算值” (Computable Value)。**

告别将不仅相同，而且难以组合的“配置”、“脚本”和“任务”区分对待的旧思维。在 Cascade 中，它们是统一的。

## 三大支柱

### 1. `LazyResult`: 对未来值的承诺

当您在 `Cascade` 中定义一个计算步骤时（例如调用一个 `@task` 函数，或者声明一个配置依赖），它**不会**立即执行。

相反，`Cascade` 会立即返回一个 `LazyResult` 对象。
*   这是一个对未来某个值的“承诺”。
*   这个对象是轻量级的，它仅仅包含了计算该值所需的一切信息：**计算逻辑**（"怎么做"）和**依赖关系**（"需要什么"）。
*   因为它是懒惰的，您可以自由地传递它、组合它，甚至将其作为条件，而在真正需要结果之前不会触发任何副作用。

### 2. 统一依赖图 (The Unified Graph)

这也是为什么 `Cascade` 被称为“统一”自动化库的原因。

当您将一个 `LazyResult` 作为一个参数传递给另一个计算步骤时，`Cascade` 并不是在传递值，而是在**构建图**。所有的 `LazyResult` 在后台连接成了一个巨大的、统一的有向无环图 (DAG)。

这个图不仅包含 Python 函数调用，还包含：
*   **Shell 命令** (`cs.shell`)
*   **配置查找** (`cs.config`)
*   **文件读取** (`cs.file`)
*   **数据库查询** (`cs.sql`)
*   **API 请求** (`cs.http`)

在这个图中，一个数据库查询的结果可以无缝地流向一个 Shell 命令，只需将前者的 `LazyResult` 传给后者即可。

### 3. 按需执行 (On-demand Execution)

这是 `Cascade` 能够极其高效的“魔法”所在。

因为我们拥有完整的依赖图，`Cascade` 可以在执行前进行全局优化。当您请求某个最终结果（Target）时，`Cascade` 引擎会：
1.  **反向追踪**: 从目标节点开始，向上追踪所有必须的依赖。
2.  **剪枝**: 只有那些为了计算最终结果所**必须**的节点才会被标记为执行。图中其他无关的分支会被完全忽略。
3.  **并发调度**: 引擎会自动分析哪些节点互不依赖，并尽可能并行地执行它们。

这意味着，如果您只想要一个复杂工作流中的一小部分结果，您只需请求那一个结果，`Cascade` 绝不会浪费时间去计算您不需要的东西。
~~~~~

### 下一步建议
现在，你可以再次运行 `mkdocs serve`。配置错误应该已经消失，而且当你点击导航栏中的“核心哲学”时，应该能看到刚刚填充的内容。

接下来，建议我们继续填充“操作指南”部分，例如 `docs/how-to-guides/defining-computations.md`，将手册中关于 `@cs.task` 和 `cs.config` 的详细用法迁移过去。
