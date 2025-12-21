#### Acts 2: Fix the Broken Engine API Call

This patch makes the test suite pass again by updating the `_execute_map_node` implementation.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        coros = [
            self._execute_graph(
                target, params, active_resources, run_id, parent_state_backend
            )
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)
~~~~~
~~~~~python
        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        async def run_sub_target(target):
            # For mapped tasks, we perform the full build/solve cycle for each item.
            # TCO optimization does not apply here.
            graph = build_graph(target)
            plan = self.solver.resolve(graph)
            return await self._execute_graph(
                target, params, active_resources, run_id, parent_state_backend,
                graph=graph, plan=plan
            )

        coros = [run_sub_target(target) for target in sub_targets]
        return await asyncio.gather(*coros)
~~~~~
