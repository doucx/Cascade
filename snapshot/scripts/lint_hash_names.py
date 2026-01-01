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
    """用于存储违规信息的简单数据类。"""
    def __init__(self, path: Path, lineno: int, var_name: str):
        self.path = path
        self.lineno = lineno
        self.var_name = var_name

    def __repr__(self) -> str:
        return f"Violation(path={self.path}, lineno={self.lineno}, var_name='{self.var_name}')"


def is_compliant(variable_name: str) -> bool:
    """检查变量名是否符合哈希命名规范。"""
    return bool(HASH_NAME_PATTERN.match(variable_name))


class HashNameVisitor(ast.NodeVisitor):
    """
    一个 AST 访问者，用于查找命名不规范的哈希变量。
    """
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations: List[Violation] = []

    def _check_name(self, name: str, lineno: int):
        """核心检查逻辑：如果名称像哈希但又不合规，则记录违规。"""
        # 启发式规则：名称包含 "hash" 就应该被检查
        if "hash" in name.lower() and not is_compliant(name):
            self.violations.append(Violation(self.file_path, lineno, name))

    def visit_Assign(self, node: ast.Assign):
        """检查赋值语句：`my_hash = ...`"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_name(target.id, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """检查函数参数：`def my_func(bad_hash):`"""
        for arg in node.args.args:
            self._check_name(arg.arg, arg.lineno)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """检查异步函数参数。"""
        self.visit_FunctionDef(node)


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
):
    """
    扫描 Python 代码库，查找并报告不符合哈希命名规范 v3.0 的变量。
    """
    all_violations: List[Violation] = []
    
    files_to_scan = [
        p for p in scan_path.rglob("*.py")
        if not any(excluded in p.parts for excluded in exclude_dirs)
    ]

    with typer.progressbar(files_to_scan, label="Scanning files") as progress:
        for file_path in progress:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                visitor = HashNameVisitor(file_path)
                visitor.visit(tree)
                all_violations.extend(visitor.violations)
            except SyntaxError as e:
                console.print(f"\n[bold red]Error parsing {file_path}: {e}[/bold red]")
            except Exception as e:
                console.print(f"\n[bold red]Unexpected error with {file_path}: {e}[/bold red]")

    if not all_violations:
        console.print("\n[bold green]✅ Success! No hash naming violations found.[/bold green]")
        raise typer.Exit(code=0)

    console.print(
        f"\n[bold red]❌ Found {len(all_violations)} hash naming violations:[/bold red]"
    )

    # 按文件路径对违规进行分组
    all_violations.sort(key=lambda v: (v.path, v.lineno))
    
    last_path = None
    for violation in all_violations:
        if violation.path != last_path:
            console.print(f"\n[cyan]File: {violation.path}[/cyan]")
            last_path = violation.path
            try:
                lines = violation.path.read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []

        if not lines:
            console.print(f"  [red]L{violation.lineno}: Could not read file content.[/red]")
            continue

        console.print(
            f"  [yellow]L{violation.lineno}[/yellow] "
            f"Found non-compliant hash variable: [bold magenta]{violation.var_name}[/bold magenta]"
        )

        start = max(0, violation.lineno - 1 - context_lines)
        end = min(len(lines), violation.lineno + context_lines)

        for i in range(start, end):
            line_num = i + 1
            line_content = lines[i]
            if line_num == violation.lineno:
                console.print(f"[bold red]>{line_num:5d} | {line_content}[/bold red]")
            else:
                console.print(f" {line_num:5d} | {line_content}")

    raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)