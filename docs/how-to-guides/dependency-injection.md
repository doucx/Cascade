# 操作指南：管理资源 (DI)

在真实世界的自动化工作流中，许多任务都依赖于外部资源，例如数据库连接、HTTP 会话客户端或硬件设备句柄。这些资源通常需要一个明确的**初始化 (Setup)** 和**清理 (Teardown)** 过程。

`Cascade` 通过一个优雅的依赖注入 (Dependency Injection, DI) 系统来解决这个问题，确保资源被正确地管理和传递。

## 核心组件

1.  **`@cs.resource`**: 一个装饰器，用于将一个资源管理函数转换为 `Cascade` 可识别的资源定义。
2.  **`cs.inject()`**: 一个函数，用于在任务的签名中声明对某个资源的依赖。

## 定义一个资源

一个资源必须被定义为一个**生成器 (generator) 函数**，即函数体内必须使用 `yield` 关键字。

*   `yield` 之前的所有代码，是资源的**初始化**逻辑。
*   `yield` 产生的值，是真正要被注入到任务中的**资源实例**。
*   `yield` 之后的所有代码，是资源的**清理**逻辑。`Cascade` 引擎保证在整个工作流运行结束后，这部分代码一定会被执行。

**示例：定义一个数据库连接资源**

```python
import cascade as cs
from sqlalchemy import create_engine

# 假设 db_url 来自于配置
db_url = cs.config("db.url.analytics")

@cs.resource
def analytics_db(url: str = db_url):
    """一个管理数据库连接的资源"""
    
    print("【资源】正在连接数据库...")
    engine = create_engine(url)
    connection = engine.connect()
    
    # yield 出可用的连接对象
    yield connection
    
    # 工作流结束后，这里的代码将被执行
    print("【资源】关闭数据库连接...")
    connection.close()
    engine.dispose()
```

## 在任务中使用资源

要在任务中使用上面定义的资源，只需在该任务的函数签名中，使用 `cs.inject("资源名称")` 作为参数的默认值。

```python
import cascade as cs

@cs.task
def fetch_active_users(
    conn = cs.inject("analytics_db") # 声明依赖于名为 'analytics_db' 的资源
):
    """一个使用数据库连接的任务"""
    
    # 在任务内部，conn 就是 yield 出来的那个 connection 对象
    result = conn.execute("SELECT * FROM users WHERE status = 'active'")
    return result.fetchall()

# 当你运行这个任务时，Cascade 引擎会自动：
# 1. 发现 fetch_active_users 依赖于 analytics_db。
# 2. 找到 analytics_db 资源，并执行其初始化逻辑。
# 3. 将 yield 的值注入到 fetch_active_users 的 conn 参数中。
# 4. 执行任务。
# 5. 在整个工作流结束后，执行 analytics_db 的清理逻辑。
final_result = fetch_active_users()
```

### Provider 的隐式使用

`Cascade` 的一些内置 Provider（如 `cs.sql`）也隐式地使用了这个资源系统。

```python
# 这行代码等效于在内部执行了 cs.inject("analytics_db")
users = cs.sql("SELECT ...", db="analytics_db")
```

通过这种方式，`Cascade` 将业务逻辑（`fetch_active_users`）与资源管理的复杂性完全解耦，使你的代码更清晰、更易于测试。