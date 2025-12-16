# [WIP] fix(docs): 修复 mkdocstrings API 文档生成配置

### 错误分析
目前的 API 文档生成存在两个关键问题：
1.  **缺少指令**: `docs/reference/api.md` 文件内容为空，缺少 `mkdocstrings` 必需的指令（如 `::: cascade`），导致插件没有任何对象可以渲染。
2.  **路径配置**: 虽然使用了 `setup_commands`，但在某些开发环境中，显式指定 `paths` 参数指向 `src` 目录对于 `src-layout` 项目来说通常更稳健且速度更快，因为它允许静态分析工具直接定位源码而无需完整的包安装步骤。

### 用户需求
解决 `mkdocstrings` 无法自动生成 API 文档的问题，确保 API 参考页面能正确显示 `cascade` 库的文档。

### 评论
修复策略非常直接：首先告诉插件“去哪里找代码”（配置 `paths`），然后告诉插件“要显示什么”（编写 `api.md`）。我们将采用 `src` 路径映射这种更轻量的方式来替代 `setup_commands`。

### 目标
1.  配置 `mkdocs.yml`，使其能正确解析 `src/cascade` 下的源码。
2.  填充 `docs/reference/api.md`，添加能够递归显示 `cascade` 顶层 API 的指令。
3.  通过运行构建命令验证修复结果。

### 基本原理
1.  **显式路径**: 在 `mkdocstrings` 处理器配置中添加 `paths: [src]`，直接将源码目录暴露给文档生成器。
2.  **指令声明**: 在 Markdown 中使用 `::: cascade` 指令是触发自动文档生成的唯一方式。
3.  **验证**: 执行 `mkdocs build` 是确认配置生效且无 Python 导入错误的黄金标准。

### 标签
#intent/fix #flow/draft #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/docs #task/object/api-reference #task/action/fix-generation #task/state/continue

---

### Script

#### Acts 1: 配置 mkdocstrings 路径

修改 `mkdocs.yml`，移除基于 pip 安装的 `setup_commands`，改为更直接的 `paths: [src]` 配置，这有助于解决 `src-layout` 项目的发现问题。

~~~~~act
patch_file
mkdocs.yml
~~~~~
~~~~~yaml
      handlers:
        python:
          # 以下是修复 API 参考为空的关键配置
          setup_commands:
            # 强制插件在收集文档前，安装项目本身及其所有可选依赖
            - pip install -e .[all]
          options:
            # (可选, 但推荐) 按源代码中的顺序，而不是字母顺序列出成员
            members_order: source
~~~~~
~~~~~yaml
      handlers:
        python:
          paths: [src]
          options:
            # (可选, 但推荐) 按源代码中的顺序，而不是字母顺序列出成员
            members_order: source
            docstring_style: google
            show_source: true
~~~~~

#### Acts 2: 填充 API 文档指令

在 `docs/reference/api.md` 中添加 `mkdocstrings` 指令，使其渲染 `cascade` 根包的文档。

~~~~~act
write_file
docs/reference/api.md
~~~~~
~~~~~markdown
# API 参考

此页面包含 `cascade` 包的完整 API 参考文档。

::: cascade
    options:
      show_root_heading: true
      show_submodules: true
~~~~~

### 下一步建议
如果构建成功（Act 3 没有报错），你应该会在构建日志中看到有关文档页面生成的输出。此时，你可以放心地将这些更改合并到之前的 `[COMMIT]` 计划中，或者作为一个单独的修复提交。

如果构建失败，请检查 Act 3 的输出日志，通常错误原因会是缺少依赖（需要 `pip install`）或代码中的语法错误导致的解析失败。
