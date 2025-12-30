好的，我来解决这个问题。

这是一个典型的 `pytest` 配置问题。错误信息 `pytest.PytestRemovedIn9Warning: '...' requested an async fixture '...', with no plugin or hook that handled it` 明确指出 `pytest` 无法处理异步 (`async`) 测试和 fixture，因为它缺少相应的插件。

标准的解决方案是添加 `pytest-asyncio` 插件到项目的开发依赖中。

我将修改根目录下的 `pyproject.toml` 文件来添加这个依赖。

## [WIP] fix: 添加 pytest-asyncio 依赖以支持异步测试

### 错误分析
`pytest` 的核心测试运行器是同步的。当它遇到使用 `async def` 定义的测试函数或 fixture 时（如此处的 `mock_ipfs_server`），它不知道如何管理 `asyncio` 事件循环来正确地运行它们。

`pytest-asyncio` 插件通过集成 `asyncio` 事件循环到 `pytest` 的生命周期中来解决这个问题。它会自动发现并运行标记为 `@pytest.mark.asyncio` 的测试，并能正确处理 `async` fixture。

当前项目的开发环境中缺少了这个关键的依赖，导致了测试失败。

### 用户需求
用户希望修复在 `packages/cascade-provider-ipfs/tests/test_ipfs.py` 中由于缺少异步支持而导致的 `pytest` 错误。

### 评论
这是一个常见的配置疏漏，特别是在一个大型多包项目中。将 `pytest-asyncio` 添加到根 `pyproject.toml` 的 `[project.optional-dependencies].dev` 部分是正确且一劳永逸的解决方案，可以确保整个工作区的所有测试都能正确处理异步代码。

### 目标
1.  修改项目根目录的 `pyproject.toml` 文件。
2.  在 `dev` 可选依赖列表中添加 `pytest-asyncio`。
3.  确保测试能够成功运行。

### 基本原理
我们将通过一个 `patch_file` 操作，在 `pyproject.toml` 的 `dev` 依赖列表中，紧随 `pytest-mock` 之后添加 `pytest-asyncio`。这可以确保在安装开发环境时 (`uv pip install -e .[dev]`)，`pytest` 会具备运行异步测试所需的能力。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/async-support #task/action/configuration #task/state/begin

---
### Script

#### Acts 1: 更新项目开发依赖

我们将修改根 `pyproject.toml` 文件，以包含 `pytest-asyncio` 库。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
dev = [
  "pytest",
  "pytest-cov",
  "pytest-aiohttp",
  "pytest-mock",
  "moto[s3]",
  "typer",
~~~~~
~~~~~toml.new
dev = [
  "pytest",
  "pytest-cov",
  "pytest-aiohttp",
  "pytest-mock",
  "pytest-asyncio",
  "moto[s3]",
  "typer",
~~~~~

### 下一步建议

在应用此补丁后，请确保更新你的开发环境依赖。如果你正在使用 `uv`，可以运行以下命令：

```bash
uv pip install -e .[dev]
```

然后重新运行测试，问题应该就解决了。
