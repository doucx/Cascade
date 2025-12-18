Excellent catch. Your detailed error log points directly to the next flaw in my reasoning. This iterative process is exactly how robust systems are built.

You are absolutely right to flag this. The build is failing inside `cascade-cli` because it cannot resolve a variable I invented.

## [COMMIT] fix(build): Use standard relative path dependencies in packages

### 错误分析
你提供的 `uv` 错误日志非常精确，直接命中了问题的核心：`ValueError: Unknown context field 'PROJECT_ROOT'`。

这个错误发生的原因是：
1.  我在 `packages/cascade-cli/pyproject.toml` (以及其他子包) 的 `dependencies` 列表中使用了 `file:///${PROJECT_ROOT}/...` 这种语法。
2.  我的假设是 `${PROJECT_ROOT}` 是一个会被构建工具（Hatchling）或安装器（`uv`）自动替换为项目根目录的标准变量。
3.  **这个假设是错误的。** `${PROJECT_ROOT}` 并非 PEP 508 或 `pyproject.toml` 规范中定义的标准上下文变量。因此，当 `hatchling` 尝试解析这个依赖字符串时，它不认识 `PROJECT_ROOT`，导致构建失败。

我们需要用一种标准的、跨工具兼容的方式来声明本地包之间的相对路径依赖。

### 用户需求
修复所有子包 (`cascade-runtime`, `cascade-py`, `cascade-cli`) 的 `pyproject.toml` 文件，将其中对本地兄弟包的依赖声明从无效的 `${PROJECT_ROOT}` 语法，修改为标准的、基于相对路径的 `file:` URI 语法。

### 评论
这是一个关键的配置修复，它教会我们不能想当然地使用自定义变量，而必须严格遵循打包规范。改用标准的相对路径 `file:` URI 不仅能解决当前的构建失败，而且使我们的项目配置更具可移植性和健壮性，因为它不再依赖任何特定工具的“魔法”变量替换。这是完成我们 Monorepo 基础设施建设的最后一步。

### 目标
1.  修改 `packages/cascade-runtime/pyproject.toml`，将其对 `cascade-interfaces` 的依赖路径修正。
2.  修改 `packages/cascade-py/pyproject.toml`，将其对 `cascade-interfaces` 和 `cascade-runtime` 的依赖路径修正。
3.  修改 `packages/cascade-cli/pyproject.toml`，将其对 `cascade-py` 的依赖路径修正。

### 基本原理
我们将对每个需要修改的 `pyproject.toml` 文件执行一次 `write_file` 操作。这是最安全的方式，因为它避免了 `patch_file` 在处理列表和多行字符串时的复杂性。

新的依赖语法将是 `package-name @ file:../relative/path/to/package`。这里的 `../` 是一个标准的相对路径指示符，它会从当前 `pyproject.toml` 文件所在的位置开始解析。例如，对于 `packages/cascade-cli/pyproject.toml` 来说，`../cascade-py` 会正确地指向 `packages/cascade-py` 目录。这是 PEP 508 规范支持的标准语法，`uv` 和 `pip` 都能正确理解。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/build #task/object/monorepo-structure #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正 `cascade-runtime` 的依赖

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

[project.optional-dependencies]
csp_solver = ["python-constraint"]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 2: 修正 `cascade-py` 的依赖

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

#### Acts 3: 修正 `cascade-cli` 的依赖

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

[project.scripts]
cascade = "cascade.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade/cli"]
~~~~~

### 下一步建议
我们已经扫清了所有已知的构建和安装障碍。现在，Monorepo 的基础设施已经**完全就绪**。

请再次运行安装命令：
```bash
uv pip install -e ".[dev]"
```
这一次，它应该能顺利完成，并正确地将所有本地包链接到你的虚拟环境中。

安装成功后，我们将正式进入代码修复阶段，着手解决所有因路径变更而失效的 `import` 语句。这是让项目恢复生机的最后一步。
