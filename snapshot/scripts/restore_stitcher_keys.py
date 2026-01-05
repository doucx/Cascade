import sys
from pathlib import Path
import griffe
from ruamel.yaml import YAML

def get_module_fqn(path: Path) -> str:
    """
    根据文件路径推断模块的 FQN。
    假设结构符合 src-layout: packages/<pkg>/src/<module_path>
    """
    parts = path.parts
    try:
        # 找到 src 目录的位置
        src_index = parts.index("src")
        # 取 src 之后的部分
        rel_parts = parts[src_index + 1:]
    except ValueError:
        # 如果找不到 src，尝试简单的推断或跳过
        return None
    
    if rel_parts[-1] == "__init__.py":
        rel_parts = rel_parts[:-1]
    else:
        rel_parts = list(rel_parts)
        rel_parts[-1] = path.stem
    
    return ".".join(rel_parts)

def restore_keys():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # 防止过早换行
    
    root = Path(".")
    # 查找所有 packages 目录下的 stitcher.yaml
    files = list(root.glob("packages/**/*.stitcher.yaml"))
    print(f"Found {len(files)} stitcher files.")

    for yaml_path in files:
        # 推断对应的 .py 文件路径
        # 策略 1: 同名 .py (foo.stitcher.yaml -> foo.py)
        py_path = yaml_path.with_name(yaml_path.name.replace(".stitcher.yaml", ".py"))
        
        # 策略 2: 如果策略 1 不存在，可能是包目录下的 __init__ (dir/foo/__init__.stitcher.yaml -> dir/foo/__init__.py)
        # 上面的替换逻辑其实已经涵盖了 foo/__init__.stitcher.yaml -> foo/__init__.py
        
        if not py_path.exists():
            # 特殊情况处理
            continue

        module_fqn = get_module_fqn(py_path)
        if not module_fqn:
            print(f"Skipping {yaml_path}: Could not infer module FQN")
            continue
            
        # 使用 Griffe 解析源码获取成员
        try:
            # 只加载单文件，不需要解析整个包依赖，这样速度快且容错高
            module = griffe.load(py_path, submodules=False)
        except Exception as e:
            print(f"WARN: Griffe failed to parse {py_path}: {e}")
            continue
            
        # 读取 YAML
        with open(yaml_path, 'r') as f:
            data = yaml.load(f)
            
        if not data:
            continue
            
        new_data = {}
        modified = False
        
        for key, value in data.items():
            # 检查 Key 是否以当前模块的 FQN 开头
            if key.startswith(module_fqn + "."):
                # 计算简短名称
                short_name = key[len(module_fqn)+1:]
                
                # 验证简短名称的“根”部分是否在模块中定义
                # 例如 short_name="MyClass.method"，根是 "MyClass"
                root_obj = short_name.split(".")[0]
                
                # module.members 包含了该文件中定义或导入的所有符号
                if root_obj in module.members:
                    # 进一步确认：如果是导入的符号，通常我们不希望在该文件中记录文档
                    # 除非它是被显式导出用于公共 API 的。
                    # 为了安全起见，只要它在 members 里，我们认为简化是安全的引用。
                    new_data[short_name] = value
                    modified = True
                else:
                    # 符号未在模块中找到，保持 FQN 以防破坏引用
                    # print(f"  [KEEP] {key} (Symbol '{root_obj}' not found in {py_path.name})")
                    new_data[key] = value
            else:
                new_data[key] = value
        
        if modified:
            print(f"Updating {yaml_path}")
            with open(yaml_path, "w") as f:
                yaml.dump(new_data, f)

if __name__ == "__main__":
    restore_keys()