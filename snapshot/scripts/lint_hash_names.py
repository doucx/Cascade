#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

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
        self.violations: list[Violation] = []
        self.warnings: list[Violation] = []

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
    issues: list[Violation],
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
            console.print(f"  [red]L{issue.lineno}: Could not read file content.[/red]")
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
    exclude_dirs: list[str] | None = typer.Option(
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
    all_violations: list[Violation] = []
    all_warnings: list[Violation] = []

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
        console.print("\n[bold green]✅ Success! No naming issues found.[/bold green]")
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
