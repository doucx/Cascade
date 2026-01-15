好的，我将按照你的要求，为 `cascade-bus` 创建包骨架，并更新相关的 `pyproject.toml` 文件。

## [WIP] 为 `cascade-bus` 创建包骨架，并更新相关的 `pyproject.toml` 文件

这是一个重要的架构起点，它为后续从 `runtime` 和 `common` 迁移逻辑做好了物理准备。

## 标签
#intent/architect #flow/ready #priority/high
#comp/engine #comp/runtime #comp/build #concept/ui
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/initialization #task/state/begin

---

### Script

#### Acts 1: 创建 `cascade-bus` 包结构

我们将创建新包的目录结构、必要的 `__init__.py`（包含命名空间扩展脚本）以及其基础的 `pyproject.toml`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-bus/src/cascade/bus
touch packages/cascade-bus/src/cascade/bus/__init__.py
~~~~~

~~~~~act
write_file
packages/cascade-bus/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-bus/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-bus"
version = "0.1.0"
description = "The unified event and feedback bus for the Cascade ecosystem."
requires-python = ">=3.8"
dependencies = [
  "cascade-spec"
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
~~~~~

#### Acts 2: 更新 `cascade-runtime` 依赖

我们将 `cascade-bus` 添加到 `cascade-runtime` 的依赖中。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-reflection",
  "cascade-compiler",
  "cascade-vm",
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-reflection",
  "cascade-compiler",
  "cascade-vm",
  "cascade-bus",
]
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-bus = { workspace = true }
~~~~~

#### Acts 3: 更新 `cascade-common` 依赖

我们将 `cascade-bus` 添加到 `cascade-common` 的依赖中。

~~~~~act
patch_file
packages/cascade-common/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec"
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-bus"
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/cascade-common/pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]

[tool.hatch.metadata]
allow-direct-references = true

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-bus = { workspace = true }
~~~~~

#### Acts 4: 更新根目录 `pyproject.toml`

我们需要在根目录的配置中注册新包，包括 Hatch 工作区、UV 源码映射和 Pyright 检查环境。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "cascade-spec",
    "cascade-runtime",
    "cascade-sdk",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]
~~~~~
~~~~~toml.new
dependencies = [
    "cascade-spec",
    "cascade-runtime",
    "cascade-bus",
    "cascade-sdk",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
~~~~~
~~~~~toml.new
cascade-common = { workspace = true }
cascade-bus = { workspace = true }
cascade-test-utils = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
~~~~~
~~~~~toml.new
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-bus",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
  "cascade-std",
  "ruff",
]
~~~~~
~~~~~toml.new
  "cascade-std",
  "cascade-bus",
  "ruff",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-runtime/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~
~~~~~toml.new
executionEnvironments = [
  { root = "packages", extraPaths = [ "packages/cascade-application/src", "packages/cascade-cli-controller/src", "packages/cascade-cli-observer/src", "packages/cascade-common/src", "packages/cascade-bus/src", "packages/cascade-connector-local/src", "packages/cascade-connector-mqtt/src", "packages/cascade-runtime/src", "packages/cascade-library/src", "packages/cascade-provider-ipfs/src", "packages/cascade-sdk/src", "packages/cascade-spec/src", "packages/cascade-vm/src", "packages/cascade-compiler/src", "packages/cascade-std/src" ] }
]
~~~~~

### 下一步建议

骨架已经搭好，现在可以开始真正的“搬家”工作了。

我建议先从 `cascade-common` 中迁移 `FeedbackBus` 逻辑，因为它相对独立且被广泛使用。具体的迁移步骤是：
1.  在 `packages/cascade-bus/src/cascade/bus/` 中创建 `feedback.py` 和 `messages.py`。
2.  将 `cascade-common` 中 `messaging` 目录下的逻辑迁移过去。
3.  处理 `locales` 资源文件的位置。

如果你准备好了，我可以开始生成第一个逻辑迁移计划。
