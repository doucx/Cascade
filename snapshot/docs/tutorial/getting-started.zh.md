# 快速上手

本教程将引导你完成第一个 `Cascade` 应用的创建，整个过程大约需要一分钟。

## 安装

`Cascade` 支持 Python 3.8+。通过 pip 安装：

```bash
pip install "cascade-py"
```

> 注意：根据你的 shell 配置，你可能需要使用 `pip3`。

## 您的第一个 Cascade 应用

让我们创建一个混合了配置和代码的脚本。这个脚本的目标是：读取一个配置文件中的版本号，并用它来构建一个 Docker 镜像标签。

首先，在你项目的根目录创建一个名为 `build.py` 的文件：

```python
# build.py
import cascade as cs

# 1. 使用 cs.config 声明一个对配置值的依赖
# 它会懒加载项目中的 YAML 文件来查找 'project.version'
# 注意: cs.config() 依赖 PyYAML, 请确保已安装 (`pip install PyYAML`)
project_version = cs.config("project.version")

# 2. 使用 @cs.task 定义一个 Python 任务
# 它依赖于从配置中获取的版本号
@cs.task
def generate_docker_tag(version: str, suffix: str) -> str:
    return f"my-app:{version}-{suffix}"

# 3. 连接声明式与命令式
# 注意：这里没有立即执行！
# project_version 是一个 LazyResult
image_tag = generate_docker_tag(version=project_version, suffix="latest")

# 4. 运行工作流，请求最终目标
if __name__ == "__main__":
    # 为了让这个例子能运行，我们需要一个配置文件。
    # cs.run() 会自动查找并加载名为 "cascade.yml" 或 "cascade.yaml" 的文件，
    # 并将其作为名为 "config_data" 的资源注入。
    # 
    # 你也可以手动指定配置字典，但使用资源是最佳实践。
    
    # 手动创建一个模拟的配置
    mock_config = {
        "project": {
            "version": "1.2.3"
        }
    }
    
    # 只有在调用 run() 时，所有依赖才会被解析和计算
    # 我们通过 `override_resource` 注入我们的 mock_config
    # 这样就不需要真的在项目里创建一个 cascade.yml 文件了
    
    from cascade.runtime.engine import Engine
    from cascade.testing import override_resource
    
    @cs.resource
    def config_data():
        yield mock_config

    engine = Engine()
    with override_resource(engine, "config_data", config_data):
        result = engine.run(image_tag)

    print(f"Docker 镜像标签: {result}")
```

现在，运行它：

```bash
$ python build.py
Docker 镜像标签: my-app:1.2.3-latest
```

恭喜！你刚刚构建并运行了你的第一个 `Cascade` 工作流。你已经体验到了其核心魅力：
- **声明式依赖**: 你声明了 `image_tag` 依赖于 `project_version`。
- **懒加载**: 直到调用 `run()` 之前，什么都没有发生。
- **无缝集成**: 来自配置的值 (`cs.config`) 和来自 Python 代码的值 (`@cs.task`) 被无缝地结合在了一起。

在接下来的指南中，我们将深入探索 `Cascade` 的更多强大功能。