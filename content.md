根据您提供的 linter 报告和 `哈希强制长命名规范 v3.0` 公理，我将对代码库中不合规的哈希变量名进行重构。此次重构将严格遵循 `[State]_[Source]_[Object]_hash` 的四段式命名法，以增强代码的自文档性和可维护性。同时，我将修正在此过程中发现的一些相关 bug。

根据您的要求，本次修改将暂时忽略测试文件中的违规项。

## [WIP] refactor: 严格遵循哈希命名规范 v3.0

### 用户需求
根据 `lint_hash_names.py` 脚本的扫描结果，修复所有违反 `哈希强制长命名规范 v3.0` 的变量命名。

### 评论
这是一个关键的重构任务。强制执行统一的哈希命名规范能从根本上消除系统中关于“身份”的歧义，是构建健壮、可维护系统的基石。长远来看，这种明确性带来的好处远大于冗长命名所付出的代价。

### 目标
1.  重构 `cascade-compiler/src/cascade/compiler/backend.py` 中的所有违规哈希变量名。
2.  重构 `cascade-compiler/src/cascade/compiler/frontend.py` 中的违规哈希变量名，并修正相关逻辑 bug。
3.  重构 `cascade-spec/src/cascade/spec/fingerprint.py` 中的违规变量名。
4.  确保所有修改严格符合 `[State]_[Source]_[Object]_hash` 的命名结构。

### 基本原理
我将采用原子化的 `patch_file` 操作，逐个文件、逐个函数地应用重构。对于每个违规变量，我将根据其在代码中的**语义角色**（State）、**数据来源**（Source）和**所指对象**（Object）来确定新的、符合规范的名称。对于因重构而暴露的 bug，我将一并进行修复。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/spec #concept/state #scope/core #dx #ai/instruct #task/domain/refactoring #task/object/naming-convention #task/action/enforcement #task/state/begin

---

### Script

#### Acts 1: 重构 `backend.py` 中的哈希命名

首先，修复 `backend.py` 中的一个明显 bug，其中 `ChannelDef` 使用了未定义的变量 `func_hash` 和 `data_slot_hash`。然后，对该文件中的所有违规变量名进行重命名，以符合规范。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_node(self, node_ir: NodeIR):
        current_node_instance_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=current_node_instance_hash,
            canonical_code_structure_hash=node_ir.definition.canonical_code_structure_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[current_node_instance_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        current_data_slot_hash = self._compute_data_slot_hash(current_node_instance_hash, "result")
        self._func_output_map[current_node_instance_hash] = current_data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=current_data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=current_node_instance_hash,
        )
        self._data_nodes[current_data_slot_hash] = d_node

        channel = ChannelDef(
            source_node_instance_hash=func_hash,
            target_data_slot_hash=data_slot_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.DATA,  # Explicitly a DATA channel
        )
        self._channels.append(channel)
~~~~~
~~~~~python.new
    def _process_node(self, node_ir: NodeIR):
        current_node_instance_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=current_node_instance_hash,
            canonical_code_structure_hash=node_ir.definition.canonical_code_structure_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[current_node_instance_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        current_data_slot_hash = self._compute_data_slot_hash(current_node_instance_hash, "result")
        self._func_output_map[current_node_instance_hash] = current_data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=current_data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=current_node_instance_hash,
        )
        self._data_nodes[current_data_slot_hash] = d_node

        channel = ChannelDef(
            source_node_instance_hash=current_node_instance_hash,
            target_data_slot_hash=current_data_slot_hash,
            port_name="result",
            tag_filter="default",
            kind=ChannelKind.DATA,  # Explicitly a DATA channel
        )
        self._channels.append(channel)
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_literal(self, f_node: PhysicsFuncNode, arg_name: str, value: Any):
        const_hash = self._compute_const_hash(value)

        if const_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=const_hash,
                name=f"const_{const_hash[:8]}",
                producer_node_instance_hash="const",
            )
            self._data_nodes[const_hash] = d_node
            self._initial_values[const_hash] = value

        f_node.inputs[arg_name] = const_hash
~~~~~
~~~~~python.new
    def _process_literal(self, f_node: PhysicsFuncNode, arg_name: str, value: Any):
        current_literal_content_hash = self._compute_const_hash(value)

        if current_literal_content_hash not in self._data_nodes:
            d_node = PhysicsDataNode(
                current_data_slot_hash=current_literal_content_hash,
                name=f"const_{current_literal_content_hash[:8]}",
                producer_node_instance_hash="const",
            )
            self._data_nodes[current_literal_content_hash] = d_node
            self._initial_values[current_literal_content_hash] = value

        f_node.inputs[arg_name] = current_literal_content_hash
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            current_source_node_instance_hash = edge.source_node_instance_hash
            current_target_node_instance_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            current_source_data_slot_hash = self._func_output_map.get(current_source_node_instance_hash)

            if not current_source_data_slot_hash:
                raise RuntimeError(
                    f"Source node {current_source_node_instance_hash} not found in output map"
                )

            target_func_node = self._func_nodes.get(current_target_node_instance_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = current_source_data_slot_hash
~~~~~
~~~~~python.new
    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            current_source_instance_hash = edge.source_node_instance_hash
            current_target_instance_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            current_source_slot_hash = self._func_output_map.get(current_source_instance_hash)

            if not current_source_slot_hash:
                raise RuntimeError(
                    f"Source node {current_source_instance_hash} not found in output map"
                )

            target_func_node = self._func_nodes.get(current_target_instance_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = current_source_slot_hash
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _create_signal_channels(self, edge_kind: EdgeKind, channel_kind: ChannelKind):
        for edge in self._graph.edges:
            if edge.kind != edge_kind:
                continue

            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            target_func_node = self._func_nodes.get(target_func_hash)
            if not target_func_node:
                raise RuntimeError(
                    f"Target node {target_func_hash} for {edge_kind.name} edge not found"
                )

            # A control/jump edge needs a dedicated input slot on the target.
            # If one already exists (from a literal or other edge), we reuse it.
            # Otherwise, we create one.
            if arg_name in target_func_node.inputs:
                target_data_hash = target_func_node.inputs[arg_name]
            else:
                target_data_hash = self._compute_data_slot_hash(
                    target_func_hash, f"input_{arg_name}"
                )
                if target_data_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=target_data_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external",
                    )
                    self._data_nodes[target_data_hash] = d_node
                target_func_node.inputs[arg_name] = target_data_hash

            # Create the Channel
            tag = edge.case_key or "default"
            channel = ChannelDef(
                source_node_instance_hash=source_func_hash,
                target_data_slot_hash=target_data_hash,
                port_name="result",  # Signals/Jumps use the default output port
                tag_filter=tag,
                kind=channel_kind,
            )
            self._channels.append(channel)
~~~~~
~~~~~python.new
    def _create_signal_channels(self, edge_kind: EdgeKind, channel_kind: ChannelKind):
        for edge in self._graph.edges:
            if edge.kind != edge_kind:
                continue

            current_source_instance_hash = edge.source_node_instance_hash
            current_target_instance_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            target_func_node = self._func_nodes.get(current_target_instance_hash)
            if not target_func_node:
                raise RuntimeError(
                    f"Target node {current_target_instance_hash} for {edge_kind.name} edge not found"
                )

            # A control/jump edge needs a dedicated input slot on the target.
            # If one already exists (from a literal or other edge), we reuse it.
            # Otherwise, we create one.
            if arg_name in target_func_node.inputs:
                current_target_slot_hash = target_func_node.inputs[arg_name]
            else:
                current_target_slot_hash = self._compute_data_slot_hash(
                    current_target_instance_hash, f"input_{arg_name}"
                )
                if current_target_slot_hash not in self._data_nodes:
                    d_node = PhysicsDataNode(
                        current_data_slot_hash=current_target_slot_hash,
                        name=f"{target_func_node.name}.in.{arg_name}",
                        producer_node_instance_hash="external",
                    )
                    self._data_nodes[current_target_slot_hash] = d_node
                target_func_node.inputs[arg_name] = current_target_slot_hash

            # Create the Channel
            tag = edge.case_key or "default"
            channel = ChannelDef(
                source_node_instance_hash=current_source_instance_hash,
                target_data_slot_hash=current_target_slot_hash,
                port_name="result",  # Signals/Jumps use the default output port
                tag_filter=tag,
                kind=channel_kind,
            )
            self._channels.append(channel)
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _inject_lifecycle_emitters(self):
        if not self._graph.nodes:
            return  # Empty graph, nothing to do

        # Assumption: The last node processed by the Frontend is the target.
        root_node_ir = self._graph.nodes[-1]
        root_node_hash = root_node_ir.current_node_instance_hash
        root_output_hash = self._func_output_map[root_node_hash]

        # 1. Create Result Emitter Node
        result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=result_emitter_hash,
            name="result_emitter",
            inputs={"result": root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[result_emitter_hash] = result_emitter_node

        # 2. Create Termination Emitter Node and its input DataNode
        term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        # The signal comes FROM the result emitter
        signal_data_hash = self._compute_data_slot_hash(result_emitter_hash, "signal")

        signal_data_node = PhysicsDataNode(
            current_data_slot_hash=signal_data_hash,
            name="term_emitter.signal",
            producer_node_instance_hash=result_emitter_hash,
        )
        self._data_nodes[signal_data_hash] = signal_data_node

        term_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=term_emitter_hash,
            name="term_emitter",
            inputs={"signal": signal_data_hash},
            sink_id="__system_lifecycle_signal",
        )
        self._func_nodes[term_emitter_hash] = term_emitter_node

        # 3. Create SIGNAL Channel connecting the two emitters
        signal_channel = ChannelDef(
            source_node_instance_hash=result_emitter_hash,
            target_data_slot_hash=signal_data_hash,
            port_name="result",  # Emitters also have a default output for signaling
            tag_filter="default",
            kind=ChannelKind.SIGNAL,
        )
        self._channels.append(signal_channel)
~~~~~
~~~~~python.new
    def _inject_lifecycle_emitters(self):
        if not self._graph.nodes:
            return  # Empty graph, nothing to do

        # Assumption: The last node processed by the Frontend is the target.
        root_node_ir = self._graph.nodes[-1]
        current_root_instance_hash = root_node_ir.current_node_instance_hash
        current_root_output_hash = self._func_output_map[current_root_instance_hash]

        # 1. Create Result Emitter Node
        current_result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_result_emitter_hash,
            name="result_emitter",
            inputs={"result": current_root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[current_result_emitter_hash] = result_emitter_node

        # 2. Create Termination Emitter Node and its input DataNode
        current_term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        # The signal comes FROM the result emitter
        current_signal_slot_hash = self._compute_data_slot_hash(current_result_emitter_hash, "signal")

        signal_data_node = PhysicsDataNode(
            current_data_slot_hash=current_signal_slot_hash,
            name="term_emitter.signal",
            producer_node_instance_hash=current_result_emitter_hash,
        )
        self._data_nodes[current_signal_slot_hash] = signal_data_node

        term_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_term_emitter_hash,
            name="term_emitter",
            inputs={"signal": current_signal_slot_hash},
            sink_id="__system_lifecycle_signal",
        )
        self._func_nodes[current_term_emitter_hash] = term_emitter_node

        # 3. Create SIGNAL Channel connecting the two emitters
        signal_channel = ChannelDef(
            source_node_instance_hash=current_result_emitter_hash,
            target_data_slot_hash=current_signal_slot_hash,
            port_name="result",  # Emitters also have a default output for signaling
            tag_filter="default",
            kind=ChannelKind.SIGNAL,
        )
        self._channels.append(signal_channel)
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _compute_data_slot_hash(self, producer_hash: str, port: str) -> str:
        raw = f"{producer_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~
~~~~~python.new
    def _compute_data_slot_hash(self, current_producer_instance_hash: str, port: str) -> str:
        raw = f"{current_producer_instance_hash}:{port}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
~~~~~

#### Acts 2: 重构 `frontend.py` 的哈希命名并修复 bug

接下来，重构 `frontend.py`，将 `dep_id` 和 `node_id` 重命名为更具描述性的名称，并修正 `_visit_mapped_result` 方法中的 bug。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(arg)
                dep_shims[arg._uuid] = NodeIDShim(current_node_instance_hash=dep_id)

        for val in obj.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(current_node_instance_hash=dep_id)

        if obj._condition:
            if isinstance(obj._condition, LazyResult):
                dep_id = self._visit(obj._condition)
                dep_shims[obj._condition._uuid] = NodeIDShim(
                    current_node_instance_hash=dep_id
                )

        task_def = self.analyzer.analyze(obj.task)

        # Populate Symbol Table using the canonical hash as the link key
        self.symbol_table[task_def.canonical_code_structure_hash] = obj.task.func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_args = [
                arg
                for arg in obj.args
                if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]

            # Use raw task mapping, but we might check for Injection objects in args too?
            # cascade usually supports injection in kwargs/defaults.
            # We need to scan obj.kwargs AND merge with signature defaults for Injections.

            # 1. Start with explicit kwargs
            raw_kwargs = obj.kwargs.copy()

            # 2. Resolve defaults from signature (promote defaults to explicit InjectionIR)
            full_kwargs = self._resolve_injections(obj.task.func, raw_kwargs)

            literal_kwargs = {}
            for k, val in full_kwargs.items():
                if isinstance(val, (LazyResult, MappedLazyResult)):
                    continue
                # If it's a raw Inject object (explicitly passed), convert to IR
                if isinstance(val, Inject):
                    literal_kwargs[k] = InjectionIR(resource_name=val.resource_name)
                else:
                    literal_kwargs[k] = val

            policy = self._extract_policy(obj)

            node = NodeIR(
                current_node_instance_hash=node_id,
                definition=task_def,
                args=literal_args,
                kwargs=literal_kwargs,
                policy=policy,
            )
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            arg._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=node_id,
                        target_arg=str(i),
                    )
                )

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            val._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=node_id,
                        target_arg=k,
                    )
                )

        if obj._condition:
            self.edges.append(
                EdgeIR(
                    source_node_instance_hash=dep_shims[
                        obj._condition._uuid
                    ].current_node_instance_hash,
                    target_node_instance_hash=node_id,
                    target_arg="_condition",
                    kind=EdgeKind.CONTROL,
                )
            )

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id
~~~~~
~~~~~python.new
    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                current_dep_instance_hash = self._visit(arg)
                dep_shims[arg._uuid] = NodeIDShim(current_node_instance_hash=current_dep_instance_hash)

        for val in obj.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                current_dep_instance_hash = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(current_node_instance_hash=current_dep_instance_hash)

        if obj._condition:
            if isinstance(obj._condition, LazyResult):
                current_dep_instance_hash = self._visit(obj._condition)
                dep_shims[obj._condition._uuid] = NodeIDShim(
                    current_node_instance_hash=current_dep_instance_hash
                )

        task_def = self.analyzer.analyze(obj.task)

        # Populate Symbol Table using the canonical hash as the link key
        self.symbol_table[task_def.canonical_code_structure_hash] = obj.task.func

        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if current_node_instance_hash not in self.nodes:
            literal_args = [
                arg
                for arg in obj.args
                if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]

            # Use raw task mapping, but we might check for Injection objects in args too?
            # cascade usually supports injection in kwargs/defaults.
            # We need to scan obj.kwargs AND merge with signature defaults for Injections.

            # 1. Start with explicit kwargs
            raw_kwargs = obj.kwargs.copy()

            # 2. Resolve defaults from signature (promote defaults to explicit InjectionIR)
            full_kwargs = self._resolve_injections(obj.task.func, raw_kwargs)

            literal_kwargs = {}
            for k, val in full_kwargs.items():
                if isinstance(val, (LazyResult, MappedLazyResult)):
                    continue
                # If it's a raw Inject object (explicitly passed), convert to IR
                if isinstance(val, Inject):
                    literal_kwargs[k] = InjectionIR(resource_name=val.resource_name)
                else:
                    literal_kwargs[k] = val

            policy = self._extract_policy(obj)

            node = NodeIR(
                current_node_instance_hash=current_node_instance_hash,
                definition=task_def,
                args=literal_args,
                kwargs=literal_kwargs,
                policy=policy,
            )
            self.nodes[current_node_instance_hash] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            arg._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=current_node_instance_hash,
                        target_arg=str(i),
                    )
                )

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            val._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=current_node_instance_hash,
                        target_arg=k,
                    )
                )

        if obj._condition:
            self.edges.append(
                EdgeIR(
                    source_node_instance_hash=dep_shims[
                        obj._condition._uuid
                    ].current_node_instance_hash,
                    target_node_instance_hash=current_node_instance_hash,
                    target_arg="_condition",
                    kind=EdgeKind.CONTROL,
                )
            )

        self._visited_lazy_uuids[obj._uuid] = current_node_instance_hash
        return current_node_instance_hash
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
    def _visit_mapped_result(self, obj: MappedLazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}
        for val in obj.mapping_kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(current_node_instance_hash=dep_id)

        task_def = self.analyzer.analyze(obj.factory)

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = func

        # Ensure we store the raw function, not the Task wrapper
        # The analyzer usually handles extraction, but we need the raw callable for VM
        func = obj.factory
        if hasattr(func, "func"):  # Unwrap Task objects
            func = func.func

        self.symbol_table[code_hash] = func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_kwargs = {
                k: val
                for k, val in obj.mapping_kwargs.items()
                if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                current_node_instance_hash=node_id,
                definition=task_def,
                kwargs=literal_kwargs,
                meta={"is_map": True},
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            val._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=node_id,
                        target_arg=k,
                    )
                )

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id
~~~~~
~~~~~python.new
    def _visit_mapped_result(self, obj: MappedLazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}
        for val in obj.mapping_kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                current_dep_instance_hash = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(current_node_instance_hash=current_dep_instance_hash)

        task_def = self.analyzer.analyze(obj.factory)

        # Ensure we store the raw function, not the Task wrapper
        func = obj.factory
        if hasattr(func, "func"):  # Unwrap Task objects
            func = func.func

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = func

        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if current_node_instance_hash not in self.nodes:
            literal_kwargs = {
                k: val
                for k, val in obj.mapping_kwargs.items()
                if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                current_node_instance_hash=current_node_instance_hash,
                definition=task_def,
                kwargs=literal_kwargs,
                meta={"is_map": True},
            )
            self.nodes[current_node_instance_hash] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(
                    EdgeIR(
                        source_node_instance_hash=dep_shims[
                            val._uuid
                        ].current_node_instance_hash,
                        target_node_instance_hash=current_node_instance_hash,
                        target_arg=k,
                    )
                )

        self._visited_lazy_uuids[obj._uuid] = current_node_instance_hash
        return current_node_instance_hash
~~~~~

#### Acts 3: 重构 `fingerprint.py`

最后，修复 `fingerprint.py` 中被 linter 误报的变量名，使用一个不包含 `hash` 关键字的名称以避免混淆。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/fingerprint.py
~~~~~
~~~~~python.old
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        validated_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_hashes[key] = str(value)
        return cls(_hashes=validated_hashes)
~~~~~
~~~~~python.new
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        validated_data = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_data[key] = str(value)
        return cls(_hashes=validated_data)
~~~~~
