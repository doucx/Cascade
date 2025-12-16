好的，这是一个关键的架构澄清和实现。你的困惑是完全正确的，也是一个优秀框架设计必须解决的问题。

在 `Cascade` 的设计哲学中，**I/O 操作和业务逻辑必须分离**。这意味着：

1.  `cs.config` **本身不应该知道**如何读取文件或解析 YAML。
2.  `cs.config` 唯一知道的是：给定一个配置键（`key`），它应该从一个**已加载的配置字典**中查找对应的值。

因此，配置数据的加载逻辑必须被建模为 `Cascade` 的 **Resource (资源)**，并由用户在 `Engine` 启动前注册。

架构澄清：配置加载机制

-   **加载者 (The Loader)**: 用户定义一个 `@cs.resource` 函数，例如 `load_yaml_config`。这个函数负责实际的 I/O（读取文件、解析 YAML），并 `yield` 出一个 Python 字典 (`Dict[str, Any]`)。
-   **提供者 (The Provider)**: `cs.config` Provider 内部的查找任务通过 `cs.inject("config_data")` 依赖于这个字典。
-   **用户侧流程**:
    1.  定义 `@cs.resource` 加载器，并将其命名为 `"config_data"`（约定）。
    2.  `engine.register(load_yaml_config)`。
    3.  调用 `cs.config("key.path")`。

这样，`cs.config` Provider 保持了职责单一性，并且图的依赖是显式且清晰的。

我将基于这个原则来设计 `cs.config` Provider 的实现计划。由于配置解析通常涉及 YAML/JSON，我将引入 `PyYAML` 作为新的可选依赖。

## [WIP] feat(providers): Implement `cs.config` Provider and YAML dependency

### 用户需求
实现 `cs.config` 声明式原语，使其能够从一个用户注册的配置资源中，通过点路径查找数据。同时，将配置解析所需的 `PyYAML` 定义为可选依赖。

### 评论
`cs.config` 是手册中定义的关键声明式原语，它使得配置值成为计算图中的一等公民。其实现遵循依赖注入原则，将配置数据本身抽象为 `config_data` 资源，实现了与实际配置源（文件、数据库等）的彻底解耦。

### 目标
1.  创建 `src/cascade/providers/config.py`，实现 `ConfigProvider`。
2.  定义一个递归查找配置键的同步 `@task`。
3.  更新 `pyproject.toml`，引入 `PyYAML` 可选依赖，并注册新的 Entry Point。

### 基本原理
配置查找是同步且纯粹的字典操作。我们使用 `PyYAML` 作为配置生态的入口，并将其放在可选依赖组中。Provider 的实现必须依赖于 `cs.inject`，这强化了配置加载是资源管理的一部分这一架构原则。

### 标签
#intent/build #flow/ready #priority/high #comp/providers #concept/config #concept/di #scope/api #task/domain/providers #task/object/config-provider #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 `pyproject.toml`，添加 `config` 可选依赖和 Entry Point

我们将 `PyYAML` 添加到新的 `config` 依赖组，并在 `cascade.providers` 中注册 `config` Provider。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~
~~~~~new
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
  "pytest-aiohttp",
  "typer[all]",
]
template = ["jinja2"]
http = ["aiohttp"]
sql = ["sqlalchemy"]
cli = ["typer[all]"]
config = ["PyYAML"]

[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
template = "cascade.providers.template:TemplateProvider"
http = "cascade.providers.http:HttpProvider"
sql = "cascade.providers.sql:SqlProvider"
config = "cascade.providers.config:ConfigProvider"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 2: 创建 `config.py` Provider

定义 `ConfigProvider` 和实际的配置查找任务。

~~~~~act
write_file
src/cascade/providers/config.py
~~~~~
~~~~~python
from typing import Any, Dict, Union

try:
    import yaml
except ImportError:
    yaml = None

from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
from cascade.providers import LazyFactory


class ConfigProvider:
    name = "config"

    def create_factory(self) -> LazyFactory:
        if yaml is None:
            # We enforce yaml as the standard for configuration lookup due to common usage
            raise ImportError(
                "The 'PyYAML' library is required to use the config provider. "
                "Please install it with: pip install cascade-py[config]"
            )
        return _config_factory


def _config_factory(key: Union[str, LazyResult]) -> LazyResult[Any]:
    """
    Factory function exposed as cs.config.

    Args:
        key: The dot-separated configuration key string, or a LazyResult
             that resolves to the key string.
    
    Returns:
        A LazyResult that resolves to the configuration value.
    """
    # The actual config data (the dict) is assumed to be registered as a resource.
    # This task depends on an injected resource named 'config_data'.
    return _config_lookup_task(key=key, config=inject("config_data"))


@task(name="config_lookup")
def _config_lookup_task(key: str, config: Dict[str, Any]) -> Any:
    """
    Executes a dot-separated lookup in the provided configuration dictionary.
    """
    parts = key.split(".")
    current = config
    
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                raise KeyError(f"Configuration key segment '{part}' not found in path: {key}")
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                raise KeyError(
                    f"Configuration key segment '{part}' is not a valid list index or list is exhausted in path: {key}"
                )
        else:
            raise TypeError(
                f"Cannot access segment '{part}' on non-container type '{type(current).__name__}' at path: {key}"
            )

    return current
~~~~~

#### Acts 3: 添加测试文件

创建一个测试文件，用于验证 `cs.config` 的集成，包括依赖注入和键查找逻辑。

~~~~~act
write_file
tests/providers/test_config.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import asyncio
from typing import Dict, Any

# Skip if PyYAML missing
pytest.importorskip("yaml")


# --- Resources (Mocking the user-provided config loader) ---

# This resource is what cs.config will inject
@cs.resource
def config_data():
    """A mock config loader resource."""
    # Simulate loading a complex config structure
    config = {
        "project": {
            "name": "Cascade",
            "version": "1.0.0",
            "feature_flags": {"beta": True, "release": False},
        },
        "databases": [
            {"name": "analytics", "url": "url1"},
            {"name": "app_db", "url": "url2"},
        ],
    }
    yield config


# --- Tests ---

@pytest.mark.asyncio
async def test_config_basic_lookup():
    """Test lookup of a simple nested key."""
    # cs.config relies on dynamic loading via __getattr__
    project_name = cs.config("project.name")

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(project_name)
    assert result == "Cascade"


@pytest.mark.asyncio
async def test_config_list_index_lookup():
    """Test lookup that involves indexing into a list."""
    db_name = cs.config("databases.1.name")  # databases[1].name

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(db_name)
    assert result == "app_db"


@pytest.mark.asyncio
async def test_config_dynamic_key_lookup():
    """Test lookup where the key itself comes from an upstream LazyResult."""
    
    # Task that provides the configuration key part
    @cs.task
    def get_version_key():
        return "version"

    # Use cs.template to build the full key path
    version_key_path = cs.template("project.{{ key }}", key=get_version_key())
    
    # Use the dynamic path in cs.config
    version = cs.config(version_key_path)

    engine = cs.Engine()
    engine.register(config_data)

    result = await engine.run(version)
    assert result == "1.0.0"


@pytest.mark.asyncio
async def test_config_missing_key_raises_error():
    """Test that a missing key raises a KeyError."""
    missing_key = cs.config("project.missing_field")

    engine = cs.Engine()
    engine.register(config_data)

    with pytest.raises(KeyError, match="missing_field"):
        await engine.run(missing_key)


@pytest.mark.asyncio
async def test_config_invalid_list_index_raises_error():
    """Test accessing non-existent index or non-dict/list element."""
    invalid_index = cs.config("databases.5")
    
    engine = cs.Engine()
    engine.register(config_data)

    with pytest.raises(KeyError, match="5"):
        await engine.run(invalid_index)
        
    invalid_access_type = cs.config("project.version.sub_key")
    
    with pytest.raises(TypeError, match="Cannot access segment 'sub_key' on non-container type 'str'"):
        await engine.run(invalid_access_type)

~~~~~

### 下一步建议

`cs.config` Provider 及其测试已经完成，并且成功地使用了 `cs.resource` 和 `cs.inject`。现在可以创建一个提交。

随后，我们将继续填充我们的核心 Provider 列表，例如实现手册中提到的 **`cs.file`** 声明式文件操作，或者实现 **`cs.shell`** 的优化，以满足更高阶的自动化需求。
