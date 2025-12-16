好的，根据上一步的架构重构，我们现在需要全面审查并更新所有遗留使用旧的 `cs.config()` API 的文档，将其替换为新的、明确的 `cs.load_yaml` 和 `cs.lookup` 组合。

我将从 `docs/how-to-guides/defining-computations.md` 文件开始，因为它是介绍 `cs.config` 概念的主要文档之一。

## [WIP] docs(config): 更新文档，将 cs.config 替换为 cs.load_yaml/cs.lookup

### 用户需求
更新所有文档中对已废弃 `cs.config` 的引用，使用新引入的 `cs.load_yaml` 和 `cs.lookup` 模式。

### 评论
虽然上一步修复了最关键的快速上手文档，但若不及时更新其他核心文档，会导致概念混乱。本次修改将确保整个文档体系中使用统一、清晰的配置加载模式。

### 目标
1.  修改 `docs/how-to-guides/defining-computations.md` 中的所有代码示例和解释文本。
2.  将 `cs.config("key.path")` 转换为 `cs.lookup(source, key="key.path")` 的模式，并确保 `source` 变量通过 `cs.load_yaml` 获得。

### 基本原理
文档的清晰度和一致性至关重要。使用 `patch_file` 可以精确地更新代码块，避免不必要的全文覆盖。我将修改文件中的两个主要示例：基本查找和动态键查找。

### 标签
#intent/refine #flow/ready #priority/medium #comp/docs #concept/config #scope/dx #ai/instruct #task/domain/docs #task/object/config-api-update #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修改 `docs/how-to-guides/defining-computations.md` 中的基本配置查找示例

我们将引入 `cs.load_yaml` 作为配置数据源，并使用 `cs.lookup` 进行查找。由于 `config_data` 在这个文档中没有定义，我们假定用户会明确加载它。

~~~~~act
patch_file
docs/how-to-guides/defining-computations.md
~~~~~
~~~~~python
# 声明式：使用 `cs.config` 从配置中获取值

当你的值是来自于一个静态配置文件（例如 `.yaml`）时，你应该使用 `cs.config()` 来声明对这个值的依赖。

```python
import cascade as cs

# 这会声明一个依赖，它将在运行时从配置源中查找 'project.name' 这个键
project_name = cs.config("project.name")

# 假设你的项目中有一个 cascade.yml 文件:
# project:
#   name: "MyApp"
```
~~~~~
~~~~~markdown
# 声明式：使用配置 Provider 获取值

当你的值是来自于一个配置文件（例如 `.yaml`）时，你应该使用配置 Provider 来声明对这个值的依赖。我们推荐分离**文件加载**和**键值查找**两个步骤。

```python
import cascade as cs

# 1. 明确地加载配置源（假设文件名为 cascade.yml）
config_source = cs.load_yaml("cascade.yml")

# 2. 从已加载的配置中查找 'project.name' 这个键
# project_name 依赖于 config_source
project_name = cs.lookup(source=config_source, key="project.name")

# 假设你的项目中有一个 cascade.yml 文件:
# project:
#   name: "MyApp"
```
~~~~~

#### Acts 2: 修改 `docs/how-to-guides/defining-computations.md` 中的动态配置键示例

在这个示例中，我们需要将 `cs.config(db_url_key)` 替换为 `cs.lookup(source=config_source, key=db_url_key)`。

**注意**: 文档中缺少 `config_source` 的定义。我将在 Act 1 的修改中通过自然语言说明 `config_source` 的来源，但在 Act 2 的代码示例中，我需要显式定义 `config_source` 以使代码可读。

~~~~~act
patch_file
docs/how-to-guides/defining-computations.md
~~~~~
~~~~~python
### 处理动态配置键

一个常见的场景是，配置的键本身是动态生成的（例如，根据环境切换）。为了保持依赖图的明确性，**严禁**使用 f-string 等方式在 `cs.config` 内部拼接字符串。

正确的做法是使用 `cs.template` 来显式地构建配置键：

```python
import cascade as cs

# 1. 定义一个运行时参数
env = cs.Param("env", default="staging")

# 2. 使用 cs.template 显式地构建配置键
# db_url_key 本身是一个 LazyResult
db_url_key = cs.template("db.url.{{ environment }}", environment=env)

# 3. 使用这个 LazyResult 作为 cs.config 的输入
# 这清晰地表明 db_url 依赖于 db_url_key，而 db_url_key 依赖于 env
db_url = cs.config(db_url_key)
```
~~~~~
~~~~~python
### 处理动态配置键

一个常见的场景是，配置的键本身是动态生成的（例如，根据环境切换）。为了保持依赖图的明确性，**严禁**使用 f-string 等方式直接拼接字符串。

正确的做法是使用 `cs.template` 来显式地构建配置键，并将完整的配置源传递给查找操作：

```python
import cascade as cs

# 假设我们已经加载了配置源
config_source = cs.load_yaml("config.yml")

# 1. 定义一个运行时参数
env = cs.Param("env", default="staging")

# 2. 使用 cs.template 显式地构建配置键
# db_url_key 本身是一个 LazyResult
db_url_key = cs.template("db.url.{{ environment }}", environment=env)

# 3. 使用这个 LazyResult 作为 cs.lookup 的键，并传入配置源
# 这清晰地表明 db_url 依赖于 db_url_key，而 db_url_key 依赖于 env 和 config_source
db_url = cs.lookup(source=config_source, key=db_url_key)
```
~~~~~

### 下一步建议
我们已经完成了 `docs/how-to-guides/defining-computations.md` 的更新。

接下来，我们需要检查：
1. `docs/how-to-guides/dependency-injection.md` (使用了 `cs.config` 来获取 db_url)
2. `docs/how-to-guides/using-providers.md` (提到了 `cs.config`)

请指示是否继续更新这些文件，并准备提交。
