import ast
import inspect
from typing import Any, List, Dict, Optional, Set, Callable
import logging
import textwrap

from cascade.spec.task import Task

logger = logging.getLogger(__name__)


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

    def __init__(self, resolver: ReferenceResolver):
        self.resolver = resolver
        self.potential_targets: Set[Any] = set()

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

        if func_obj:
            # Check if it is a Task
            if isinstance(func_obj, Task):
                self.potential_targets.add(func_obj)

            # Check for .map calls: Task.map(...)
            if inspect.ismethod(func_obj) and func_obj.__name__ == "map":
                # Check if the bound self is a Task
                bound_self = getattr(func_obj, "__self__", None)
                if isinstance(bound_self, Task):
                    self.potential_targets.add(bound_self)


def analyze_task_source(task: Task) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    Results are cached on the Task object to avoid redundant AST parsing.
    """
    # 1. Return cached results if available
    if (
        hasattr(task, "_potential_tco_targets")
        and task._potential_tco_targets is not None
    ):
        return task._potential_tco_targets

    task_func = task.func
    if not task_func:
        return []

    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError, TypeError) as e:
        # Some callables (like built-ins) might not have source code
        logger.debug(f"Could not parse source for {task.name}: {e}")
        task._potential_tco_targets = []
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    # 2. Cache the result
    task._potential_tco_targets = list(visitor.potential_targets)
    return task._potential_tco_targets


def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.
    """
    # 1. Skip if this branch has already been fully analyzed
    if getattr(root_task, "_tco_analysis_done", False):
        return

    # Use a simple DFS to detect cycles
    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        # Get static targets using the cached analyzer
        targets = analyze_task_source(current_task)

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
                # Cycle Detected!
                # All tasks in path from 'target' to 'current_task' form the cycle.
                try:
                    start_index = path.index(target)
                    cycle_members = path[start_index:]

                    # Generate a deterministic ID for this cycle
                    # Sort names to ensure stability regardless of entry point
                    member_names = sorted(t.name for t in cycle_members if t.name)
                    cycle_signature = "|".join(member_names)
                    # Use a simple hash of the signature
                    import hashlib

                    cycle_id = hashlib.md5(cycle_signature.encode()).hexdigest()

                    for member in cycle_members:
                        # Only overwrite if not set or allow merging?
                        # For simplicity, last write wins or check consistency.
                        member._tco_cycle_id = cycle_id

                except ValueError:
                    pass

        recursion_stack.remove(current_task)
        path.pop()
        # Mark individual task as processed to avoid re-entering its branch in future DFS runs
        current_task._tco_analysis_done = True

    _dfs(root_task)
