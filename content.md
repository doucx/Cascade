## [WIP] Linter 增强至 “id” 检测

你的 linter 工作得非常出色，并且你的判断完全正确。它精确地捕捉到了 `cascade-engine` 和 `cascade-graph` 中残留的、不符合 v3.0 公理的命名习惯。这些“战时痕迹”正是我们在进行“心脏移植”前必须清理干净的。

### 1. 代码审核与违规分析

以下是对 linter 发现的 5 个违规的详细分析，以及它们应该被修正为的、符合公理的命名：

1.  **`structure_hash` in `reflection.py`**
    *   **上下文**: `_compute_structure_hash` 方法正在从源代码的静态定义（函数名、参数、文档字符串等）计算哈希。
    *   **公理对齐**:
        *   **State**: 这是从当前代码的实时快照计算的，所以是 `current`。
        *   **Source**: 数据来源是 `code`。
        *   **Object**: 哈希的对象是代码的 `structure`。
    *   **合规命名**: `current_code_structure_hash`

2.  **`node_hash` in `build.py` (两处)**
    *   **上下文**: `hashing_service.compute_node_instance_hash` 正在为图中的一个具体节点实例（包含所有参数和依赖）计算唯一标识。
    *   **公理对齐**:
        *   **State**: 这是在 `current` 构建周期中计算的。
        *   **Source**: 数据来源是 `node` 的定义和绑定。
        *   **Object**: 哈希的对象是一个具体的 `instance`。
    *   **合规命名**: `current_node_instance_hash`

3.  **`code_hash` in `hashing.py`**
    *   **上下文**: 变量 `code_hash` 正在从 `definition.fingerprint["current_code_structure_hash"]` 中获取一个值。
    *   **分析**: 这非常典型——一个已经被正确命名的值，被赋给了一个不合规的局部变量。这同样违反了公理，因为它在局部作用域内重新引入了语义模糊性。
    *   **合规命名**: 局部变量应直接使用源值的名称 `current_code_structure_hash`。

4.  **`validated_hashes` in `fingerprint.py`**
    *   **上下文**: 这是一个在 `Fingerprint.from_dict` 方法中用于临时存储结果的字典。
    *   **分析**: linter 的启发式规则（`"hash" in name`）正确地捕捉到了这个模糊命名。虽然它本身不是一个哈希字符串，但它是一个哈希的集合。更好的名字应该能反映其内容和用途，并且不触发“模糊命名”的警报。
    *   **修正建议**: `hashes_data` 或 `internal_hashes`。这清楚地表明它是一个数据容器，而非一个哈希值本身。

### 2. Linter 功能增强

完全同意你的想法。一个好的 linter 不仅应该报告致命错误，还应该能提示潜在的风险。将 `id` 作为警告项，并用开关控制，是完美的策略。

我已经为你更新了 `lint_hash_names.py` 脚本，增加了 `--check-ids` 功能。

**主要变更**:
1.  **新增命令行选项**: `check_ids: bool = typer.Option(False, "--check-ids", ...)`。
2.  **分离违规与警告**: `HashNameVisitor` 现在有两个列表：`self.violations` (用于 hash 错误) 和 `self.warnings` (用于 id 警告)。
3.  **新增 ID 检查逻辑**: `_check_id_name` 方法使用启发式规则 (`name.endswith("_id")` 或 `name == "id"`) 来查找模糊的 ID 命名。
4.  **增强报告**: 在报告完所有 Errors 后，如果 `check_ids` 被启用，会再报告所有 Warnings。
5.  **退出码**: 只有 `violations` 会导致 `exit code 1`，`warnings` 不会，确保其在 CI 中可以作为非阻断性检查。

这是更新后的脚本：
~~~~~act
write_file
scripts/lint_hash_names.py
~~~~~
~~~~~python
#!/usr/bin/env python3
import ast
import re
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

# 公理 v3.0 定义的规范哈希命名模式
# `[State]_[Source]_[Object]_hash`
# State: canonical, current, baseline
# Source: code, blueprint, stored, etc. (用 [a-z]+ 匹配)
# Object: structure, instance, content, etc. (用 [a-z]+ 匹配)
HASH_NAME_PATTERN = re.compile(r"^(canonical|current|baseline)_[a-z]+_[a-z]+_hash$")

console = Console()


class Violation:
    """用于存储违规或警告信息的简单数据类。"""

    def __init__(self, path: Path, lineno: int, var_name: str):
        self.path = path
        self.lineno = lineno
        self.var_name = var_name

    def __repr__(self) -> str:
        return f"Violation(path={self.path}, lineno={self.lineno}, var_name='{self.var_name}')"


def is_compliant_hash(variable_name: str) -> bool:
    """检查变量名是否符合哈希命名规范。"""
    return bool(HASH_NAME_PATTERN.match(variable_name))


class HashNameVisitor(ast.NodeVisitor):
    """
    一个 AST 访问者，用于查找命名不规范的哈希变量和模糊的 ID 变量。
    """

    def __init__(self, file_path: Path, check_ids: bool):
        self.file_path = file_path
        self.check_ids = check_ids
        self.violations: List[Violation] = []
        self.warnings: List[Violation] = []

    def _check_hash_name(self, name: str, lineno: int):
        """核心检查逻辑：如果名称像哈希但又不合规，则记录违规。"""
        if "hash" in name.lower() and not is_compliant_hash(name):
            self.violations.append(Violation(self.file_path, lineno, name))

    def _check_id_name(self, name: str, lineno: int):
        """检查 'id' 类命名，如果发现则记录为警告。"""
        # 启发式规则：以 _id 结尾，或是裸露的 id
        if name.endswith("_id") or name == "id":
            self.warnings.append(Violation(self.file_path, lineno, name))

    def visit_Assign(self, node: ast.Assign):
        """检查赋值语句：`my_hash = ...` 或 `my_id = ...`"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_hash_name(target.id, node.lineno)
                if self.check_ids:
                    self._check_id_name(target.id, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """检查函数参数：`def my_func(bad_hash, some_id):`"""
        for arg in node.args.args:
            self._check_hash_name(arg.arg, arg.lineno)
            if self.check_ids:
                self._check_id_name(arg.arg, arg.lineno)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """检查异步函数参数。"""
        self.visit_FunctionDef(node)


def _report_issues(
    issues: List[Violation],
    title: str,
    context_lines: int,
):
    """通用报告函数，用于打印违规或警告。"""
    console.print(title)
    issues.sort(key=lambda v: (v.path, v.lineno))

    last_path = None
    for issue in issues:
        if issue.path != last_path:
            console.print(f"\n[cyan]File: {issue.path}[/cyan]")
            last_path = issue.path
            try:
                lines = issue.path.read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []

        if not lines:
            console.print(
                f"  [red]L{issue.lineno}: Could not read file content.[/red]"
            )
            continue

        console.print(
            f"  [yellow]L{issue.lineno}[/yellow] "
            f"Found ambiguous variable: [bold magenta]{issue.var_name}[/bold magenta]"
        )

        start = max(0, issue.lineno - 1 - context_lines)
        end = min(len(lines), issue.lineno + context_lines)

        for i in range(start, end):
            line_num = i + 1
            line_content = lines[i]
            if line_num == issue.lineno:
                console.print(f"[bold red]>{line_num:5d} | {line_content}[/bold red]")
            else:
                console.print(f" {line_num:5d} | {line_content}")


def main(
    scan_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=False,
        readable=True,
        resolve_path=True,
        help="要扫描的根目录。",
    ),
    context_lines: int = typer.Option(
        3, "--context", "-C", help="显示违规行的前后文行数。"
    ),
    exclude_dirs: Optional[List[str]] = typer.Option(
        [".venv", ".git", "__pycache__", "build", "dist"],
        "--exclude",
        "-e",
        help="要排除的目录名。",
    ),
    check_ids: bool = typer.Option(
        False,
        "--check-ids",
        help="同时检查模糊的 'id' 类变量名，并将其报告为警告。",
    ),
):
    """
    扫描 Python 代码库，查找并报告不符合哈希命名规范 v3.0 的变量。
    """
    all_violations: List[Violation] = []
    all_warnings: List[Violation] = []

    files_to_scan = [
        p
        for p in scan_path.rglob("*.py")
        if not any(excluded in p.parts for excluded in exclude_dirs)
    ]

    with typer.progressbar(files_to_scan, label="Scanning files") as progress:
        for file_path in progress:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                visitor = HashNameVisitor(file_path, check_ids)
                visitor.visit(tree)
                all_violations.extend(visitor.violations)
                all_warnings.extend(visitor.warnings)
            except SyntaxError as e:
                console.print(f"\n[bold red]Error parsing {file_path}: {e}[/bold red]")
            except Exception as e:
                console.print(
                    f"\n[bold red]Unexpected error with {file_path}: {e}[/bold red]"
                )

    has_errors = bool(all_violations)
    has_warnings = bool(all_warnings)

    if not has_errors and not has_warnings:
        console.print(
            "\n[bold green]✅ Success! No naming issues found.[/bold green]"
        )
        raise typer.Exit(code=0)

    if has_errors:
        _report_issues(
            all_violations,
            f"\n[bold red]❌ Found {len(all_violations)} hash naming violations:[/bold red]",
            context_lines,
        )

    if has_warnings:
        _report_issues(
            all_warnings,
            f"\n[bold yellow]⚠️ Found {len(all_warnings)} ambiguous 'id' warnings:[/bold yellow]",
            context_lines,
        )

    if has_errors:
        raise typer.Exit(code=1)
    else:
        console.print(
            "\n[bold green]✅ Success! No hash naming violations found.[/bold green]"
        )
        raise typer.Exit(code=0)


if __name__ == "__main__":
    typer.run(main)
~~~~~

### 3. 执行计划与下一步
1.  **应用 Linter 更新**: 你可以将上述 `write_file` 的内容保存到 `scripts/lint_hash_names.py`。
2.  **生成修复计划**: 我们可以立即着手解决 linter 报告的 5 个`hash`命名违规。这是为重构铺平道路的第一步，也是最重要的一步。
3.  **探索性扫描**: 在修复完 `hash` 问题后，我们可以运行一次 `python scripts/lint_hash_names.py . --check-ids`，全面盘点一下 `engine` 和 `graph` 中有多少 `_id` 类的模糊命名需要被清理。这将为我们下一步的重构提供一份清晰的“待办清单”。

我已经准备好根据这些分析，为你生成一个修复这 5 个 `hash` 命名违规的 `Plan.md`。请指示。
