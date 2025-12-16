好的，我们来更新 `pyproject.toml` 文件，将文档构建工具添加到开发依赖中。

## [WIP] chore(deps): 添加 MkDocs 相关文档构建依赖

### 用户需求
将 `mkdocs`, `mkdocs-material`, `mkdocstrings[python]` 添加到 `pyproject.toml` 的 `dev` 可选依赖中，以便能够本地构建和预览文档网站。

### 评论
这是一个标准操作。将工具链依赖项显式地记录在项目中，确保了开发环境的一致性，方便任何协作者（包括未来的自己）能够快速搭建文档开发环境。

### 目标
使用 `patch_file` 操作，将 `mkdocs`, `mkdocs-material`, 和 `mkdocstrings[python]` 添加到 `pyproject.toml` 文件的 `[project.optional-dependencies].dev` 列表中。

### 基本原理
使用 `patch_file` 而非 `write_file` 可以进行精确、原子化的修改，避免意外地改动 `pyproject.toml` 中的其他配置。我们只需要在 `dev` 依赖列表的末尾追加新的依赖项即可。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/build #scope/dx #ai/instruct #task/domain/docs #task/object/dependencies #task/action/add #task/state/continue

---

### Script

#### Acts 1: 更新开发依赖

我们将 `mkdocs` 相关的库添加到 `dev` 依赖组中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
]
template = ["jinja2"]
~~~~~
~~~~~toml
[project.optional-dependencies]
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
~~~~~

### 下一步建议
依赖已经添加完毕。现在你可以通过以下命令在本地启动文档服务器来预览效果了：

```bash
# 1. 安装开发依赖 (如果尚未安装)
pip install -e .[dev]

# 2. 启动文档服务器
mkdocs serve
```

接下来，我们可以开始将 `Cascade 使用手册 v2.0.md` 中的内容填充到 `docs/tutorial/getting-started.zh.md` 中，作为我们第一篇正式的文档。如果你准备好了，请告诉我。
