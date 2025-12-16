好的，收到指示。既然可以一次性处理多个文件，我将把逻辑上相关的“操作指南”内容作为一个批次进行填充。

我将从《Cascade 使用手册》中提取第 3、4、5 节的内容，并分别填充到我们已经创建的三个“操作指南”文件中。

## [WIP] docs: 填充核心“操作指南”文档页面

### 用户需求
继续填充文档，利用“一次可填充多个文件”的授权，将《Cascade 使用手册》中的主要内容块迁移到对应的 Markdown 文件中。

### 评论
这是一个提高效率的好机会。我将把“定义计算”、“使用 Provider”和“构建复杂工作流”这三个逻辑上连续的章节一次性填充完毕。这三篇指南构成了用户从入门到进阶的核心学习路径。

### 目标
1.  填充 `docs/how-to-guides/defining-computations.md`，内容来自手册第 3 节。
2.  填充 `docs/how-to-guides/using-providers.md`，内容来自手册第 4 节。
3.  填充 `docs/how-to-guides/advanced-workflows.md`，内容来自手册第 5 节。

### 基本原理
通过批量操作，我们可以更快地使文档网站变得充实和可用。我将仔细地将手册中的内容分解，调整标题和格式，确保每一篇新文档都自成体系、清晰易读，同时保持与项目架构决策（如显式使用 `cs.template`）的一致性。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/delegate #task/domain/docs #task/object/content-population #task/action/batch-write #task/state/continue

---

### Script

#### Acts 1: 填充“定义计算”指南

这部分内容解释了定义计算的两种基本模式：`@cs.task` 和 `cs.config`。

~~~~~act
write_file
docs/how-to-guides/defining-computations.md
~~~~~
~~~~~markdown
# 操作指南：定义计算

`Cascade` 提供了两种定义“可计算值” (`LazyResult`) 的核心方式，它们可以自由地混合使用，形成强大的工作流。

## 命令式：使用 `@cs.task` 封装业务逻辑

当你需要执行包含复杂、图灵完备的业务逻辑时，最佳方式是将其封装在一个 Python 函数中，并使用 `@cs.task` 装饰器将其转换为一个 `Cascade` 任务。

```python
import cascade as cs

@cs.task
def analyze_data(data: list) -> dict:
    """这是一个标准的 Python 函数，用于执行分析。"""
    if not data:
        return {}
    
    mean = sum(data) / len(data)
    # ... 其他复杂的分析逻辑 ...
    
    return {"mean": mean}

# 调用这个被装饰的函数并不会立即执行它
# 而是返回一个代表未来结果的 LazyResult 对象
analysis_result = analyze_data(data=[1, 2, 3, 4, 5]) 
```

`@cs.task` 是连接你现有 Python 代码与 `Cascade` 生态系统的桥梁。

## 声明式：使用 `cs.config` 从配置中获取值

当你的值是来自于一个静态配置文件（例如 `.yaml`）时，你应该使用 `cs.config()` 来声明对这个值的依赖。

```python
import cascade as cs

# 这会声明一个依赖，它将在运行时从配置源中查找 'project.name' 这个键
project_name = cs.config("project.name")

# 假设你的项目中有一个 cascade.yml 文件:
# project:
#   name: "MyApp"
```

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

#### Acts 2: 填充“使用内置 Provider”指南

这部分内容介绍了 `Cascade` 提供的一系列开箱即用的 `LazyResult` 工厂。

~~~~~act
write_file
docs/how-to-guides/using-providers.md
~~~~~
~~~~~markdown
# 操作指南：使用内置 Provider

`Cascade` 的核心是精简的，但它通过一个强大的 Provider（提供者）插件系统，提供了一系列开箱即用的、高度抽象的 `LazyResult` 工厂，以简化常见自动化场景。

这些工厂函数（如 `cs.shell`, `cs.file`）是声明式工作流的基石。

## `cs.shell`: 执行 Shell 命令

将一个 Shell 命令的执行及其 `stdout` 输出封装成一个 `LazyResult`。

```python
import cascade as cs

# 声明一个 Shell 命令的输出作为一个值
# 只有在下游任务需要 python_version 时，此命令才会被执行
python_version = cs.shell("python --version", check=True)
```

## `cs.file`: 声明文件依赖

`cs.file` 提供了一种声明对文件系统内容的依赖的方式。它本身返回一个文件工厂对象，你可以链式调用其方法。

```python
import cascade as cs

# 声明对文件内容的依赖，并自动解析为 JSON
config_data = cs.file("./config.json").json()

# 你也可以只检查文件是否存在
file_exists = cs.file("./important.lock").exists()
```

## `cs.sql`: 执行数据库查询

`cs.sql` 允许你将一个 SQL 查询的结果声明为一个 `LazyResult`。它通过 `db` 参数与资源管理系统集成。

```python
import cascade as cs

# 声明对 SQL 查询结果的依赖
# 它会自动查找并使用一个名为 'analytics_db' 的资源
active_users = cs.sql(
    "SELECT * FROM users WHERE status = 'active'",
    db="analytics_db"
)
```

## `cs.http`: 调用 Web API

`cs.http` 用于执行 HTTP 请求，并将其响应封装起来。为了处理动态 URL，它应该与 `cs.template` 配合使用。

```python
import cascade as cs

# 定义一个参数作为模板变量
username = cs.Param("username", default="cascade-py")

# 1. 使用 cs.template 显式地构建 URL
api_url = cs.template("https://api.github.com/users/{{ user }}", user=username)

# 2. 将构建好的 URL (一个 LazyResult) 传递给 cs.http
# .json() 会创建一个下游任务，自动解析响应体
user_profile = cs.http(api_url).json()
```
~~~~~

#### Acts 3: 填充“构建复杂工作流”指南

这部分内容展示了如何将各种计算单元组合成复杂的逻辑。

~~~~~act
write_file
docs/how-to-guides/advanced-workflows.md
~~~~~
~~~~~markdown
# 操作指南：构建复杂工作流

一旦你掌握了定义单个计算值的基础，就可以开始将它们组合起来，构建真正强大的、端到端的工作流。`Cascade` 的核心价值在于其无缝的可组合性。

## 无缝依赖混合

这是 `Cascade` `1+1 > 2` 的关键。因为所有东西都是 `LazyResult`，它们可以自由地相互依赖，无论其来源如何。

```python
import cascade as cs

# 场景：使用 Shell 命令的结果作为 Python 任务的输入
# 1. 从 Shell 获取当前的 git commit hash
commit_hash = cs.shell("git rev-parse --short HEAD")

# 2. 定义一个 Python 任务
@cs.task
def create_build_artifact(version: str) -> str:
    # 模拟创建构建产物
    artifact_name = f"artifact-{version}.zip"
    print(f"Creating {artifact_name}...")
    return artifact_name

# 3. 将 Shell 的 LazyResult 连接到 Python 任务
# 依赖关系被自动建立：create_build_artifact 依赖于 commit_hash
artifact = create_build_artifact(version=commit_hash)
```

## 参数化你的工作流 (`cs.param`)

使用 `cs.Param` 来定义在运行时（通过 `cs.run` 的 `params` 参数或 `cs.cli` 的命令行参数）注入的值。这使得你的工作流可以复用和配置。

```python
import cascade as cs

# 定义一个名为 'env' 的参数，默认值为 'staging'
env = cs.Param("env", default="staging", description="目标环境 (staging/production)")

@cs.task
def get_db_url(environment: str) -> str:
    if environment == "production":
        return "prod_db_url"
    return "stage_db_url"

db_url = get_db_url(environment=env)

# 运行时可以覆盖默认值
# from cascade.runtime.engine import Engine
# engine = Engine()
# prod_url = engine.run(db_url, params={"env": "production"}) 
# assert prod_url == "prod_db_url"
```

## 条件执行 (`.run_if()`)

使用 `.run_if()` 方法，可以让一个任务只在某个条件（一个返回布尔值的 `LazyResult`）为 `True` 时执行。

```python
import cascade as cs

# 定义一个布尔类型的参数来控制是否部署
should_deploy = cs.Param("deploy", default=False, type=bool)

# .run_if() 会将 should_deploy 作为其条件依赖
deployment_status = cs.shell(
    "kubectl apply -f deployment.yaml", 
    check=True
).run_if(should_deploy)
```
当以 `params={"deploy": False}` 运行时，`shell` 命令将永远不会被执行。

## 处理集合：映射 (`.map()`)

使用 `.map()`，您可以将一个任务工厂（如 `@task` 函数或 `cs.shell`）应用到一个集合的每个元素上，这会自动创建一组并行执行的任务。

```python
import cascade as cs

# files_to_process 可以是一个列表，也可以是上游任务的 LazyResult
files_to_process = ["data1.csv", "data2.csv", "data3.csv"]

@cs.task
def process_file(filepath: str) -> str:
    # ... 复杂的处理逻辑 ...
    return f"processed_{filepath}"

# 将 process_file 任务映射到文件列表上
# .map() 返回一个 MappedLazyResult，它在运行时会解析为一个结果列表
processed_files = process_file.map(filepath=files_to_process)

@cs.task
def summarize(processed: list[str]):
    print(f"完成了 {len(processed)} 个文件的处理。")
    return f"Processed {len(processed)} files."

# `summarize` 任务会等待所有 `process_file` 子任务完成后再执行
final_summary = summarize(processed=processed_files)
```

## 动态路由 (`cs.router`)

`cs.Router` 可以根据一个 `selector` 的值，动态地从多个上游 `LazyResult` 中选择一个作为下游任务的输入。

```python
import cascade as cs

# selector 可以是 Param，也可以是其他任务的结果
data_source_type = cs.Param("data_source", default="db")

@cs.task
def from_db(): return "Data from DB"

@cs.task
def from_api(): return "Data from API"

# Router 会根据 data_source_type 的值，选择一个上游
data_input = cs.Router(
    selector=data_source_type,
    routes={
        "db": from_db(),
        "api": from_api()
    }
)

@cs.task
def process_data(data: str):
    return f"Final data: {data}"

result = process_data(data=data_input)

#
# from cascade.runtime.engine import Engine
# engine = Engine()
# res_api = engine.run(result, params={"data_source": "api"}) 
# assert "API" in res_api
```
~~~~~

### 下一步建议
我们已经完成了核心“操作指南”的填充。剩下的指南还有：
*   `docs/how-to-guides/dependency-injection.md`
*   `docs/how-to-guides/improving-robustness.md`

我们可以继续完成这两篇，以使“操作指南”部分完整。如果你同意，我将开始填充关于依赖注入 (`@cs.resource`) 的内容。
