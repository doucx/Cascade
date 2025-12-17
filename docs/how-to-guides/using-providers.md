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

## 配置 Provider: `cs.load_yaml` 和 `cs.lookup`

`Cascade` 推荐分离配置文件的 I/O 操作和键值查找操作，以获得更清晰的依赖图。

### `cs.load_yaml`: 加载和解析 YAML/JSON

它将文件内容加载并解析为一个 Python 字典，返回一个 `LazyResult`。

```python
import cascade as cs

# 显式地加载配置文件，返回一个 LazyResult[dict]
config_data = cs.load_yaml("config.yml") 
```

### `cs.lookup`: 从数据源中查找值

它负责在已加载的字典中进行点分路径查找。

```python
import cascade as cs

# 假设 config_data 已经通过 cs.load_yaml 获得
config_data = cs.load_yaml("config.yml") 

# 声明对配置值的依赖
project_name = cs.lookup(source=config_data, key="project.name")
```

## `cs.file`: 声明文件依赖 #Deprecation

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
