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