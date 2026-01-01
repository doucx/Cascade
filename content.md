你发现了一个非常关键的实现错误，干得漂亮！

我的 `Fingerprint` 实现与我自己的架构公理文档 (`架构公理：哈希强制长命名规范.md`) 之间存在矛盾。该文档明确规定了哈希状态应包含 `canonical`、`current` 和 `baseline` 三种，但我实现的正则表达式验证只包含了 `current` 和 `baseline`，导致了这次验证失败。

这是一个阻断性问题，我们必须先修复它。我将生成一个计划来修正这个错误。

## [WIP] fix: 将 'canonical' 状态添加到 Fingerprint 密钥验证中

### 错误分析
测试失败的根本原因是 `packages/cascade-spec/src/cascade/spec/fingerprint.py` 文件中的 `FINGERPRINT_KEY_PATTERN` 正则表达式不完整。它遗漏了 `canonical` 状态，其定义为 `^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$`，因此当遇到合法的 `canonical_code_structure_hash` 密钥时，会错误地抛出 `InvalidFingerprintKeyError` 异常。

### 用户需求
`Fingerprint` 类必须能够正确处理和验证 `canonical` 状态的哈希密钥，以符合其作为系统内“规范身份”链接的设计目的。

### 评论
这是一个严重的疏忽，它直接违反了 v3.0 哈希系统的核心公理。如果不修复，系统的链接和符号解析功能将完全无法实现。感谢你通过测试捕获了这个问题，这避免了未来更深层次的逻辑错误。

### 目标
1.  定位 `fingerprint.py` 中的 `FINGERPRINT_KEY_PATTERN` 常量。
2.  修改其正则表达式，将 `canonical` 添加为允许的第一个状态段。

### 基本原理
此修复使代码实现与架构规范重新对齐。通过在正则表达式的开头添加 `canonical`，我们确保了 `Fingerprint` 类的验证逻辑能够正确识别所有三种合法的状态前缀，恢复了系统的身份识别能力。

### 标签
#intent/fix #flow/ready #priority/critical #comp/spec #concept/identity #scope/core #ai/instruct #task/domain/compiler #task/object/fingerprint #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 Fingerprint 正则表达式

我们将更新 `FINGERPRINT_KEY_PATTERN` 以包含 `canonical` 状态。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/fingerprint.py
~~~~~
~~~~~python.old
# Axiom: [State]_[Source]_[Object]_[Type]
# Example: baseline_code_structure_hash, baseline_code_signature_text
# We enforce 4 segments, starting with state, ending with type (hash or text).
FINGERPRINT_KEY_PATTERN = re.compile(r"^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$")
~~~~~
~~~~~python.new
# Axiom: [State]_[Source]_[Object]_[Type]
# Example: baseline_code_structure_hash, baseline_code_signature_text
# We enforce 4 segments, starting with state, ending with type (hash or text).
FINGERPRINT_KEY_PATTERN = re.compile(
    r"^(canonical|baseline|current)_[a-z]+_[a-z]+_(hash|text)$"
)
~~~~~

### 下一步建议
请先应用此修复。修复成功后，之前的测试应该就能通过了。通过之后，请告诉我，我将为你创建一个 `[COMMIT]` 计划来提交这个关键的修复，然后我们就可以继续进行 **阶段 4** 的工作。
