from pathlib import Path

from stitcher.refactor.migration import MigrationSpec, MoveDir


def upgrade(spec: MigrationSpec):
    # 基础路径定义
    base = Path("packages/cascade-compiler/src/cascade/compiler").absolute()

    # ==========================================
    # 1. Merge Standalone Module into Package
    # ==========================================
    # 将 backend 下零散的 wiring.py 移入 wiring 包中
    # spec.add(Move(base / "backend/wiring.py", base / "wiring/harness.py"))

    # ==========================================
    # 2. Package Relocation
    # ==========================================
    # 将整个 wiring 目录移入 backend 下
    spec.add(MoveDir(base / "wiring", base / "backend/wiring"))

    # ==========================================
    # 3. Note on Namespace
    # ==========================================
    # 逻辑路径变化:
    # cascade.compiler.wiring -> cascade.compiler.backend.wiring
    # cascade.compiler.backend.wiring -> cascade.compiler.backend.wiring.harness
