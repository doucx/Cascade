import time
from typing import Dict, Any
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler
from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        # Callback to wake up the engine loop
        self._wakeup_callback: Any = None

    def set_wakeup_callback(self, callback: Any) -> None:
        self._wakeup_callback = callback

    def request_wakeup(self, delay: float) -> None:
        if self._wakeup_callback:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.call_later(delay, self._wakeup_callback)
            except RuntimeError:
                # Fallback if no loop is running (e.g. during sync tests), though less likely in Engine run
                pass

    def register_handler(self, handler: ConstraintHandler) -> None:
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        # 1. Clean up conflicts: Remove any existing constraint with same scope & type
        conflicting_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.scope == constraint.scope
            and c.type == constraint.type
            and cid != constraint.id
        ]
        for cid in conflicting_ids:
            self._remove_constraint_by_id(cid)

        # 2. Add/Update the new constraint
        self._constraints[constraint.id] = constraint

        # Schedule wakeup if TTL is set
        if constraint.expires_at:
            now = time.time()
            if constraint.expires_at > now:
                self.request_wakeup(constraint.expires_at - now)

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)

    def _remove_constraint_by_id(self, cid: str) -> None:
        if cid not in self._constraints:
            return
        constraint = self._constraints[cid]
        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_remove(constraint, self)
        del self._constraints[cid]

    def remove_constraints_by_scope(self, scope: str) -> None:
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            self._remove_constraint_by_id(cid)

    def cleanup_expired_constraints(self) -> None:
        now = time.time()
        expired_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.expires_at is not None and c.expires_at <= now
        ]

        for cid in expired_ids:
            self._remove_constraint_by_id(cid)

        # Reschedule wakeup for the next earliest expiration if any remain
        next_expiry = None
        for c in self._constraints.values():
            if c.expires_at and c.expires_at > now:
                if next_expiry is None or c.expires_at < next_expiry:
                    next_expiry = c.expires_at

        if next_expiry:
            # We add a small buffer (0.1s) to ensure we wake up strictly after expiration
            self.request_wakeup(max(0, next_expiry - now + 0.1))

    def check_permission(self, task: Node) -> bool:
        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted

        # If no handler denied permission, permit execution.
        return True

    def get_extra_requirements(self, task: Node) -> Dict[str, Any]:
        requirements: Dict[str, Any] = {}
        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.append_requirements(task, constraint, requirements, self)
        return requirements
