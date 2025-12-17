# 操作指南：依赖注入

Cascade 的依赖注入 (DI) 系统允许你的任务在运行时自动获取共享资源，如数据库连接、API 客户端或配置文件。这使得任务本身保持纯粹的业务逻辑，而将资源管理的复杂性解耦出去。

## 核心概念

-   **资源 (`@cs.resource`)**: 一个使用 `yield` 的生成器函数，负责资源的创建（`yield` 之前）和清理（`yield` 之后）。
-   **注入 (`cs.inject`)**: 一个标记，用于在任务中声明对某个资源的依赖。

## 标准模式：在函数签名中注入 (推荐)

这是为工作流开发者设计的标准、最常用的模式。它通过在任务函数的参数中使用默认值来声明依赖。

**优点**:
-   **声明式**: 任务的依赖关系在其签名中一目了然。
-   **清晰**: 代码可读性强，易于理解和维护。

### ✅ 推荐做法 (Do This)

```python
import cascade as cs

# 1. 定义资源
@cs.resource
def database_connection():
    conn = connect_to_db()
    yield conn
    conn.close()

# 2. 在任务签名中声明依赖
@cs.task
def get_user(user_id: int, db=cs.inject("database_connection")):
    return db.query(f"SELECT * FROM users WHERE id={user_id}")

# 3. 正常调用任务
user_data = get_user(123)

# 4. 在运行引擎中注册资源
engine = cs.Engine(...)
engine.register(database_connection)
engine.run(user_data)
```

## 高级模式：在调用时注入

此模式主要为**库和 Provider 的作者**设计，用于构建需要动态指定资源名称的更高级抽象。

**优点**:
-   **动态性**: 允许将要注入的资源名称作为参数传递，实现更高的灵活性。

### ❌ 不推荐的日常用法 (Don't Do This for Regular Tasks)

```python
# 反模式：对于普通任务，这会使依赖关系变得不明确
@cs.task
def get_user(user_id: int, db): # 签名中看不出依赖
    ...

# 在调用时传入 inject，这很隐晦
user_data = get_user(123, db=cs.inject("database_connection"))
```

### ✅ 合理用例 (Provider 实现)

`cs.sql` Provider 是此模式的最佳示例。用户希望这样调用它：

`users = cs.sql("SELECT ...", db="analytics_db")`

为了实现这一点，`cs.sql` 内部的实现就需要使用“调用时注入”：

```python
# cascade/providers/sql.py (简化版)

def _sql_factory(query: str, db: str):
    """这是用户调用的 cs.sql()"""
    # 这里，'db' 的值 (如 "analytics_db") 是动态的。
    # 我们必须在调用时创建一个 Inject 对象。
    return _sql_task(query=query, conn=cs.inject(db))

@cs.task
def _sql_task(query: str, conn: Any):
    """这是实际执行的内部任务"""
    return conn.execute(query)
```

### 总结

-   **作为工作流开发者**，请**始终**使用**函数签名注入**模式。
-   **作为 Provider 或库开发者**，当你需要构建一个能处理动态资源目标的抽象时，**调用时注入**是一个强大而必要的工具。