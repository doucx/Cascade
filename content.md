You are right once again. My apologies, this is a subtle but critical configuration detail specific to the Hatch build backend. The error message is, thankfully, extremely explicit and tells us exactly what we need to do.

This error is a safety feature from the build tool, `hatchling`. It prevents you from accidentally publishing a package to PyPI that has local-only dependencies (`file:...`), which would be broken for anyone else. Since we are intentionally using this for our local monorepo development, we just need to tell Hatch that we know what we're doing.

This should be the final configuration hurdle to clear.

## [WIP] fix(build): Allow direct path dependencies in Hatch metadata

### 错误分析
你遇到的 `uv` 构建失败，其根本原因在于 `hatchling`（Hatch 的构建后端）的一个安全默认设置。

错误信息 `ValueError: Dependency #1 of field 'project.dependencies' cannot be a direct reference unless field 'tool.hatch.metadata.allow-direct-references' is set to 'true'` 明确指出：

1.  我们在子包的 `pyproject.toml` 中使用了 `file:../some-package` 这样的“直接引用”依赖。
2.  默认情况下，`hatchling` 禁止这种引用，因为它认为这对于要发布到 PyPI 的包来说是不安全的。
3.  要允许这种行为，我们必须在 `pyproject.toml` 文件中显式地设置一个标志：`[tool.hatch.metadata] \n allow-direct-references = true`。

这个问题会出现在每一个使用了 `file:` 语法的子包以及根包中。

### 用户需求
修改所有使用了本地 `file:` 依赖的 `pyproject.toml` 文件（包括根目录和 `packages/` 下的子包），添加 `[tool.hatch.metadata]` 配置节并设置 `allow-direct-references = true`，以 разрешить (allow) Hatch 构建包含本地路径依赖的包。

### 评论
这是一个完美的例子，说明了现代构建工具如何通过“显式优于隐式”的原则来提高打包的健壮性。通过强制我们声明允许直接引用，Hatch 确保我们是“有意为之”，而不是意外引入了本地依赖。完成这个修复后，我们的 Monorepo 配置将是完整且符合最佳实践的。

### 目标
1.  修改根 `pyproject.toml`。
2.  修改 `packages/cascade-runtime/pyproject.toml`。
3.  修改 `packages/cascade-py/pyproject.toml`。
4.  修改 `packages/cascade-cli/pyproject.toml`。
5.  在上述所有文件中，添加 `[tool.hatch.metadata]` 表并设置 `allow-direct-references = true`。

### 基本原理
我们将对四个 `pyproject.toml` 文件分别执行 `write_file` 操作。这是最直接和可靠的方法，可以确保新的配置节被正确添加。这个 `allow-direct-references = true` 标志将直接告诉 `hatchling` 构建后端：“我确认这个包包含本地文件系统引用，请继续构建。” 这将解决 `uv` 在调用构建后端时遇到的 `ValueError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正所有 `pyproject.toml` 文件以允许直接引用

我们将逐一更新所有使用 `file:` 依赖的配置文件。

首先是项目根 `pyproject.toml`。
~~~~~act
write_file
pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"
dependencies = [
    "cascade-interfaces @ file:packages/cascade-interfaces",
    "cascade-runtime @ file:packages/cascade-runtime",
    "cascade-py @ file:packages/cascade-py",
    "cascade-cli @ file:packages/cascade-cli",
]

[tool.hatch.workspaces]
packages = [
    "packages/cascade-interfaces",
    "packages/cascade-runtime",
    "packages/cascade-py",
    "packages/cascade-cli",
]

[tool.hatch.build.targets.wheel]
packages = ["packages/cascade-py/src/cascade"]

# 关键修复：允许根项目包含对本地包的直接文件引用
[tool.hatch.metadata]
allow-direct-references = true

[tool.pytest.ini_options]
addopts = "-ra"

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "moto[s3]",
  "typer",
  "mkdocs",
  "mkdocs-material",
  "mkdocstrings[python]",
]
~~~~~

然后是 `cascade-runtime`。
~~~~~act
write_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-runtime"
version = "0.1.0"
description = "The core runtime engine for Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces @ file:../cascade-interfaces"
]

# 关键修复：允许此包包含对本地包的直接文件引用
[tool.hatch.metadata]
allow-direct-references = true

[project.optional-dependencies]
csp_solver = ["python-constraint"]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

接着是 `cascade-py`。
~~~~~act
write_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-py"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces @ file:../cascade-interfaces",
  "cascade-runtime @ file:../cascade-runtime"
]

# 关键修复：允许此包包含对本地包的直接文件引用
[tool.hatch.metadata]
allow-direct-references = true

[project.optional-dependencies]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer"]
config = ["PyYAML"]
s3 = ["aiobotocore"]
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer",
  "PyYAML",
  "aiobotocore",
]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
"http.post" = "cascade.providers.http:HttpPostProvider"
"http.put" = "cascade.providers.http:HttpPutProvider"
"http.delete" = "cascade.providers.http:HttpDeleteProvider"
"http.request" = "cascade.providers.http:HttpRequestProvider"
subflow = "cascade.providers.subflow:SubflowProvider"
sql = "cascade.providers.sql:SqlProvider"
load_yaml = "cascade.providers.config:YamlLoaderProvider"
lookup = "cascade.providers.config:LookupProvider"
"read.text" = "cascade.providers.io:ReadTextProvider"
"read.bytes" = "cascade.providers.io:ReadBytesProvider"
"write.text" = "cascade.providers.io:WriteTextProvider"
"write.bytes" = "cascade.providers.io:WriteBytesProvider"
"fs.exists" = "cascade.providers.io:FsExistsProvider"
"io.local.read_text" = "cascade.providers.io:IoLocalReadTextProvider"
"io.local.read_bytes" = "cascade.providers.io:IoLocalReadBytesProvider"
"io.local.write_text" = "cascade.providers.io:IoLocalWriteTextProvider"
"io.local.write_bytes" = "cascade.providers.io:IoLocalWriteBytesProvider"
"io.local.exists" = "cascade.providers.io:IoLocalExistsProvider"
"io.s3.read_text" = "cascade.providers.s3:S3ReadTextProvider"
"io.s3.read_bytes" = "cascade.providers.s3:S3ReadBytesProvider"
"io.s3.write_text" = "cascade.providers.s3:S3WriteTextProvider"
"io.s3.write_bytes" = "cascade.providers.s3:S3WriteBytesProvider"
"io.stdout.write" = "cascade.providers.stdio:StdOutWriteProvider"
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

最后是 `cascade-cli`。
~~~~~act
write_file
packages/cascade-cli/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-cli"
version = "0.1.0"
description = "Command-line tools for the Cascade workflow engine."
requires-python = ">=3.8"
dependencies = [
  "cascade-py @ file:../cascade-py",
  "typer"
]

# 关键修复：允许此包包含对本地包的直接文件引用
[tool.hatch.metadata]
allow-direct-references = true

[project.scripts]
cascade = "cascade.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade/cli"]
~~~~~

### 下一步建议
我们已经解决了所有已知的、由 `pyproject.toml` 配置不当导致的构建问题。Monorepo 的基础设施现在是健壮且完整的。

**请再次运行安装命令：**
```bash
uv pip install -e ".[dev]"
```
这一次，我们有充分的理由相信它会成功。

安装成功后，唯一的遗留问题就是代码中的 `import` 路径错误。我已准备好为你生成一个修复所有导入路径的计划，这将是使项目恢复可运行状态的最后一步。
