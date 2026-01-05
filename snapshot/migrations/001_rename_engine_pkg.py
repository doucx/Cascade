from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, MoveDir

def upgrade(spec: MigrationSpec):
    """
    将 cascade.engine 包重命名为 cascade.runtime。
    Stitcher 会自动处理所有跨包引用更新。
    """
    
    # 定义源路径和目标路径 (相对于 Monorepo 根目录)
    # 注意：我们暂时还在 packages/cascade-engine 目录下操作
    src_path = Path("packages/cascade-engine/src/cascade/engine")
    dest_path = Path("packages/cascade-engine/src/cascade/runtime")

    # 执行目录移动
    # 这将触发隐式的 Rename 操作：cascade.engine.* -> cascade.runtime.*
    spec.add(MoveDir(src_path, dest_path))