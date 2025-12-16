# 快速上手

本教程将引导你完成第一个 `Cascade` 应用的创建。只需一分钟，你就能体验到声明式配置与命令式代码无缝结合的强大之处。

## 1. 安装

`Cascade` 支持 Python 3.8+。我们需要 `config` 附加依赖来处理 YAML 文件。

```bash
pip install "cascade-py[config]"
```

> 注意：根据你的 shell 配置，你可能需要使用 `pip3`。

## 2. 您的第一个 Cascade 应用

我们的目标是：从一个 YAML 配置文件中读取项目版本号，然后用它来构建一个 Docker 镜像标签。

### 步骤 1：创建配置文件

在你的项目根目录，创建一个名为 `cascade.yml` 的文件。

```yaml
# cascade.yml
project:
  name: "MyAwesomeApp"
  version: "1.2.3"
```

这为我们的工作流提供了声明式的输入数据。

### 步骤 2：创建 Python 脚本

现在，在同一目录下，创建一个名为 `build.py` 的文件：

```python
# build.py
import cascade as cs

# 1. 明确地加载配置文件
#    这会创建一个 LazyResult，它代表了未来将被解析的 YAML 文件内容。
#    依赖关系图中现在有了一个清晰的、代表文件 I/O 的节点。
config_data = cs.load_yaml("cascade.yml")

# 2. 从已加载的数据中明确地查找值
#    我们将 config_data 这个“承诺”作为 source 传递。
#    这清晰地表明 project_version 依赖于 config_data。
project_version = cs.lookup(source=config_data, key="project.version")

# 3. 定义一个执行业务逻辑的 Python 任务
@cs.task
def generate_docker_tag(version: str, suffix: str = "latest") -> str:
    """根据版本号和后缀生成 Docker 标签。"""
    print(f"--> 正在使用版本 '{version}' 生成标签...")
    return f"my-app:{version}-{suffix}"

# 4. 将查找到的值连接到任务中
image_tag = generate_docker_tag(version=project_version)

# 5. 运行工作流并请求最终结果
if __name__ == "__main__":
    print("开始运行 Cascade 工作流...")
    # 调用 run() 时，Cascade 会解析出完整的、明确的依赖链并按序执行。
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
▶️  Starting Run for targets: [generate_docker_tag]
  ⏳ Running task `load_yaml`...
  ✅ Finished task `load_yaml` in ...s
  ⏳ Running task `lookup`...
  ✅ Finished task `lookup` in ...s
  ⏳ Running task `generate_docker_tag`...
--> 正在使用版本 '1.2.3' 生成标签...
  ✅ Finished task `generate_docker_tag` in ...s
🏁 Run finished successfully in ...s.
工作流完成！
最终 Docker 镜像标签: my-app:1.2.3-latest
```

恭喜！你刚刚构建了一个清晰、健壮且无“魔法”的 `Cascade` 工作流。

在接下来的指南中，我们将深入探索 `Cascade` 的更多强大功能。