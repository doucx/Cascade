# 快速上手

本教程将引导你完成第一个 `Cascade` 应用的创建。只需一分钟，你就能体验到声明式配置与命令式代码无缝结合的强大之处。

## 1. 安装

`Cascade` 支持 Python 3.8+。我们推荐安装 `config` 附加依赖，以便使用 `cs.config`。

```bash
pip install "cascade-py[config]"
```

> 注意：根据你的 shell 配置，你可能需要使用 `pip3`。

## 2. 您的第一个 Cascade 应用

我们的目标是：从一个 YAML 配置文件中读取项目版本号，然后用它来构建一个 Docker 镜像标签。

### 步骤 1：创建配置文件

在你的项目根目录，创建一个名为 `cascade.yml` 的文件。`Cascade` 会自动发现并加载它。

```yaml
# cascade.yml
project:
  version: "1.2.3"
```

这为我们的工作流提供了声明式的输入数据。

### 步骤 2：创建 Python 脚本

现在，在同一目录下，创建一个名为 `build.py` 的文件：

```python
# build.py
import cascade as cs

# 1. 声明对配置值的依赖
#    这行代码并不会立即读取文件，而是创建了一个对未来值的“承诺”。
#    Cascade 会在需要时，自动从 cascade.yml 中加载 'project.version' 的值。
project_version = cs.config("project.version")

# 2. 定义一个执行业务逻辑的 Python 任务
@cs.task
def generate_docker_tag(version: str, suffix: str = "latest") -> str:
    """根据版本号和后缀生成 Docker 标签。"""
    print(f"--> 正在使用版本 '{version}' 生成标签...")
    return f"my-app:{version}-{suffix}"

# 3. 将声明式的值连接到命令式的任务中
#    我们将 project_version 这个“承诺”作为参数传给任务。
#    Cascade 会自动构建它们之间的依赖关系。
image_tag = generate_docker_tag(version=project_version)

# 4. 运行工作流并请求最终结果
if __name__ == "__main__":
    print("开始运行 Cascade 工作流...")
    # 只有在调用 run() 时，Cascade 才会真正开始计算。
    # 它会分析出 image_tag 依赖 generate_docker_tag，
    # 而 generate_docker_tag 依赖 project_version，
    # 最终 project_version 依赖 cascade.yml 文件。
    # 然后按照正确的顺序执行所有操作。
    final_tag = cs.run(image_tag)
    
    print("工作流完成！")
    print(f"最终 Docker 镜像标签: {final_tag}")

```

### 步骤 3：运行它！

打开你的终端，运行脚本：

```bash
$ python build.py
```

你应该会看到如下输出：

```
开始运行 Cascade 工作流...
--> 正在使用版本 '1.2.3' 生成标签...
工作流完成！
最终 Docker 镜像标签: my-app:1.2.3-latest
```

恭喜！你刚刚构建并运行了你的第一个 `Cascade` 工作流。你已经体验到了其核心魅力：

- **声明式依赖**: 你用 `cs.config` 声明了对配置文件的依赖。
- **懒加载**: 直到调用 `cs.run()` 之前，文件读取和函数执行都没有发生。
- **自动依赖解析**: `Cascade` 自动发现并执行了从配置文件到最终结果所需的所有步骤。

在接下来的指南中，我们将深入探索 `Cascade` 的更多强大功能。