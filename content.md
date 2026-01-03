简要回答
好的，为了解决 `Node.structural_id` 命名与架构公理不符的问题，并建立清晰的“统一身份”语义，我将执行一次基于 `libcst` 的全局重构，将 `structural_id` 统一更名为 `current_node_instance_hash`。

## [WIP] refactor: 将 Node.structural_id 全局重构为 current_node_instance_hash

### 用户需求
1.  **全局更名**: 将 `cascade-graph` 及相关包中 `Node` 类的 `structural_id` 字段及其所有引用，统一更名为 `current_node_instance_hash`。
2.  **工具要求**: 必须使用 `libcst` 编写脚本以保留代码格式和注释信息。
3.  **目标**: 消除 v2.0 逻辑层节点的身份命名歧义，使其符合 "架构公理：哈希强制长命名规范 v3.0"。

### 评论
这是一个涉及核心数据结构的“心脏手术”。`structural_id` 这个名字带有 v2.0 的遗留色彩，而 `current_node_instance_hash` 精确地描述了该字段的来源（即时计算）、对象（节点实例）和类型（哈希）。这次重构将彻底对齐代码与新的架构白皮书。使用 `libcst` 是明智的，因为它能避免 `sed` 可能带来的误伤（如误替换同名变量）并保留代码风格。

### 目标
1.  创建一个 `scripts/refactor_ids.py` 脚本，实现基于 AST 的智能重命名。
2.  执行该脚本，覆盖所有 `packages/` 目录。
3.  手动修正（或通过 sed）序列化层中的字符串字面量引用。
4.  验证测试通过。

### 基本原理
通过编写专门的 Codemod 脚本，我们可以精确地定位到：
1.  `Node` 及其子类的字段定义 (`AnnAssign`)。
2.  构造函数调用中的关键字参数 (`Arg`)。
3.  对象属性访问 (`Attribute`)。
4.  函数参数定义 (`Param`)。

这将确保重构是语法感知的，不会破坏其他恰好名为 `structural_id` 的局部变量（虽然不太可能有）。

### 标签
#intent/refine #flow/ready #priority/high #comp/graph #comp/engine #concept/identity #scope/core #ai/instruct #task/domain/core #task/object/node-identity #task/action/rename #task/state/begin

---

### Script

#### Acts 1: 创建 LibCST 重构脚本

编写一个专门的 Python 脚本，利用 `libcst` 的 `VisitorBasedCodemodCommand` 来遍历和修改 AST。

~~~~~act
write_file
scripts/refactor_ids.py
~~~~~
~~~~~python
import os
import libcst as cst
from libcst.codemod import VisitorBasedCodemodCommand, CodemodContext, transform_module

class RenameStructuralIdCommand(VisitorBasedCodemodCommand):
    DESCRIPTION = "Rename structural_id to current_node_instance_hash"

    def leave_Attribute(self, original_node, updated_node):
        if original_node.attr.value == "structural_id":
            return updated_node.with_changes(
                attr=updated_node.attr.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_AnnAssign(self, original_node, updated_node):
        if isinstance(original_node.target, cst.Name) and original_node.target.value == "structural_id":
             return updated_node.with_changes(
                target=updated_node.target.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_Arg(self, original_node, updated_node):
        if original_node.keyword and original_node.keyword.value == "structural_id":
            return updated_node.with_changes(
                keyword=updated_node.keyword.with_changes(value="current_node_instance_hash")
            )
        return updated_node

    def leave_Param(self, original_node, updated_node):
        if original_node.name.value == "structural_id":
            return updated_node.with_changes(
                name=updated_node.name.with_changes(value="current_node_instance_hash")
            )
        return updated_node

def process_directory(root_dir):
    print(f"Starting refactoring in {root_dir}...")
    count = 0
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r") as f:
                    source = f.read()
                
                try:
                    transformer = RenameStructuralIdCommand(CodemodContext())
                    new_source = transform_module(transformer, source)
                    
                    if new_source != source:
                        print(f"Modifying {filepath}")
                        with open(filepath, "w") as f:
                            f.write(new_source)
                        count += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
    print(f"Refactoring complete. Modified {count} files.")

if __name__ == "__main__":
    process_directory("packages")
~~~~~

#### Acts 2: 执行重构脚本

运行脚本，对 `packages` 目录下的所有源码进行修改。

~~~~~
python3 scripts/refactor_ids.py
~~~~~

#### Acts 3: 修正序列化层中的字符串字面量

`libcst` 脚本主要处理标识符，但 `cascade-graph/src/cascade/graph/serialize.py` 中使用了字符串字面量 `"structural_id"` 作为 JSON 键。为了保持一致性（并避免序列化/反序列化不匹配），我们也需要更新这些键。

~~~~~act
run_command
~~~~~
~~~~~
sed -i 's/"structural_id"/"current_node_instance_hash"/g' packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~

### 下一步建议

如果测试通过，我们将提交此变更。这是一个非常大的“查找替换”操作，虽然由 AST 保证了语法正确性，但仍需仔细检查差异。之后，我们可以继续处理 lint 报告中提到的其他 `_id` 歧义问题。
