import inspect
import hashlib
from typing import Any, List, Optional

from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint
from .protocols import TaskAnalyzer

# Type hint for the Cascade Task wrapper
# We use Any here to avoid circular imports, but conceptually it is cascade.spec.task.Task
TaskWrapper = Any


class ReflectionAnalyzer(TaskAnalyzer):
    def analyze(self, target: Any) -> TaskDef:
        # Determine the underlying function and metadata source
        func = target
        mode = "blocking"

        # Check if it's a cascade.spec.task.Task wrapper
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")

        if not callable(func):
            raise TypeError(
                f"Target {target} must be callable (or enclose a callable) to be analyzed."
            )

        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        docstring = inspect.getdoc(func)
        is_async = inspect.iscoroutinefunction(func)

        # Extract return annotation if available
        sig = inspect.signature(func)
        return_annotation = None
        if sig.return_annotation is not inspect.Signature.empty:
            # We store the string representation for serialization safety
            return_annotation = str(sig.return_annotation)

        # 2. Analyze Arguments
        args = self._analyze_arguments(sig)

        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )

    def _analyze_arguments(self, sig: inspect.Signature) -> List[ArgumentDef]:
        args = []
        for param in sig.parameters.values():
            kind = ArgumentKind[param.kind.name]

            annotation = None
            if param.annotation is not inspect.Parameter.empty:
                annotation = str(param.annotation)

            default_repr = None
            if param.default is not inspect.Parameter.empty:
                # We use repr() to get a stable string representation of the default value
                # This corresponds to 'default_value_repr' in IR.
                # Note: This is an approximation. Complex objects might have unstable reprs.
                try:
                    default_repr = repr(param.default)
                except Exception:
                    default_repr = "<unrepresentable>"

            args.append(
                ArgumentDef(
                    name=param.name,
                    kind=kind,
                    annotation=annotation,
                    default_value_repr=default_repr,
                )
            )
        return args

    def _compute_structure_hash(
        self,
        name: str,
        args: List[ArgumentDef],
        return_annotation: Optional[str],
        docstring: Optional[str],
        is_async: bool,
        mode: str,
    ) -> str:
        components = [f"Name:{name}"]
        components.append(f"Async:{is_async}")
        components.append(f"Mode:{mode}")
        if return_annotation:
            components.append(f"Return:{return_annotation}")

        # Include Docstring in hash?
        # Yes, for 'code_structure', doc changes imply structure changes in strict mode,
        # but arguably docs shouldn't affect execution identity.
        # For now, we include it to detect ANY definition change, as docstrings might act as prompts.
        if docstring:
            components.append(f"Doc:{docstring}")

        for arg in args:
            comp = f"Arg(Name:{arg.name},Kind:{arg.kind},Ann:{arg.annotation},Def:{arg.default_value_repr})"
            components.append(comp)

        fingerprint_str = "|".join(components)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()
