import ast
import inspect
from typing import Any, List, Dict, Optional, Set, Callable
import logging
import textwrap
from dataclasses import dataclass

from cascade.spec.task import Task

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Holds the results of a static analysis of a task's source code."""

    targets: List[Task]
    has_dynamic_recursion: bool = False


class ReferenceResolver:
    """
    Helper class to resolve AST nodes (Name, Attribute) to runtime objects
    using the function's global and closure contexts.
    """

    def __init__(self, func: Callable):
        self.func = func
        self.globals = getattr(func, "__globals__", {})
        self.closure_vars = self._get_closure_vars(func)

    def _get_closure_vars(self, func: Callable) -> Dict[str, Any]:
        """Extracts variables from the function's closure."""
        closure_vars = {}
        if (
            hasattr(func, "__closure__")
            and func.__closure__
            and func.__code__.co_freevars
        ):
            for name, cell in zip(func.__code__.co_freevars, func.__closure__):
                try:
                    closure_vars[name] = cell.cell_contents
                except ValueError:
                    # Cell might be empty
                    pass
        return closure_vars

    def resolve(self, node: ast.AST) -> Optional[Any]:
        """Attempts to resolve an AST expression to a runtime object."""
        try:
            if isinstance(node, ast.Name):
                return self._resolve_name(node.id)
            elif isinstance(node, ast.Attribute):
                parent = self.resolve(node.value)
                if parent is not None:
                    return getattr(parent, node.attr, None)
        except Exception:
            # Resolution is best-effort; suppress errors during static analysis
            pass
        return None

    def _resolve_name(self, name: str) -> Optional[Any]:
        if name in self.closure_vars:
            return self.closure_vars[name]
        if name in self.globals:
            return self.globals[name]
        return None


class TcoVisitor(ast.NodeVisitor):
    """
    Visits the AST of a function to find 'return' statements that call other Tasks.
    """

    def __init__(self, resolver: ReferenceResolver, current_task: Task):
        self.resolver = resolver
        self.current_task = current_task
        self.potential_targets: Set[Task] = set()
        self.has_dynamic_recursion: bool = False

    def visit_Return(self, node: ast.Return):
        """
        Inspects return statements.
        Supported patterns:
          return my_task(...)
          return my_task.map(...)
        """
        if node.value and isinstance(node.value, ast.Call):
            self._analyze_call(node.value)
        self.generic_visit(node)

    def _analyze_call(self, call_node: ast.Call):
        # 1. Resolve the function being called
        func_obj = self.resolver.resolve(call_node.func)
        called_task = None

        if func_obj:
            if isinstance(func_obj, Task):
                called_task = func_obj
                self.potential_targets.add(func_obj)
            elif inspect.ismethod(func_obj) and func_obj.__name__ == "map":
                bound_self = getattr(func_obj, "__self__", None)
                if isinstance(bound_self, Task):
                    called_task = bound_self
                    self.potential_targets.add(bound_self)

        # 2. If it's a recursive call, check for the anti-pattern
        if called_task and (
            called_task == self.current_task
            or called_task.name == self.current_task.name
        ):
            all_args = call_node.args + [kw.value for kw in call_node.keywords]
            for arg_node in all_args:
                if isinstance(arg_node, ast.Call):
                    nested_call_obj = self.resolver.resolve(arg_node.func)
                    if isinstance(nested_call_obj, Task) or (
                        inspect.ismethod(nested_call_obj)
                        and nested_call_obj.__name__ == "map"
                    ):
                        self.has_dynamic_recursion = True
                        break


def analyze_task_source(task: Task) -> AnalysisResult:
    """
    Analyzes a task function's source code to find potential TCO targets
    and anti-patterns.
    Results are cached on the Task object.
    """
    if hasattr(task, "_analysis_result") and task._analysis_result is not None:
        return task._analysis_result

    task_func = task.func
    if not task_func:
        return AnalysisResult(targets=[])

    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError, TypeError) as e:
        logger.debug(f"Could not parse source for {task.name}: {e}")
        task._analysis_result = AnalysisResult(targets=[])
        return task._analysis_result

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver, task)
    visitor.visit(tree)

    result = AnalysisResult(
        targets=list(visitor.potential_targets),
        has_dynamic_recursion=visitor.has_dynamic_recursion,
    )
    task._analysis_result = result
    return result


def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.
    """
    if getattr(root_task, "_tco_analysis_done", False):
        return

    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        analysis = analyze_task_source(current_task)
        targets = analysis.targets

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
                try:
                    start_index = path.index(target)
                    cycle_members = path[start_index:]
                    member_names = sorted(t.name for t in cycle_members if t.name)
                    cycle_signature = "|".join(member_names)
                    import hashlib

                    cycle_id = hashlib.md5(cycle_signature.encode()).hexdigest()
                    for member in cycle_members:
                        member._tco_cycle_id = cycle_id
                except ValueError:
                    pass

        recursion_stack.remove(current_task)
        path.pop()
        current_task._tco_analysis_done = True

    _dfs(root_task)
