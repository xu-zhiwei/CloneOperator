> Historical implementation-level documentation. See [paper inventory](operators.md) and [C applicability](c-applicability.md) for the release interface and scope.

# SCT 双向策略与 51 项组织

Java 与 C 各 51 个策略，共 102 个独立策略文件。维持 language/level/target/category 的原目录层级，新增文件仅落在原有 replacement 目录。默认语言仍为 Java，旧编号及导入继续保留。

## 配对表

反向表示结构转换方向。每个方向独立检查候选，不能把 inverse_id 当成无条件可执行的撤销命令。

| 变换族 | 方向一 | 方向二 |
| --- | --- | --- |
| `constant_neutral_term` | WC1 `ConstantNeutralTermInsertion` | WC2 `ConstantNeutralTermRemoval` |
| `integer_addition` | WC3 `IntegerAdditionDecomposition` | WC6 `IntegerAdditionComposition` |
| `integer_subtraction` | WC5 `IntegerSubtractionRepresentation` | WC7 `IntegerSubtractionComposition` |
| `truth_constant_negation` | WC4 `BooleanNegationReplacement` | WC8 `BooleanNegationConstantReduction` |
| `expression_neutral_term` | SE2 `ExpressionRedundantWrapping` | SE3 `ExpressionRedundantUnwrapping` |
| `unit_update` | SE5 `IncrementDecrementRewriting` | SE7 `IncrementDecrementContraction` |
| `compound_assignment` | SE6 `CompoundAssignmentRewriting` | SE8 `CompoundAssignmentContraction` |
| `demorgan` | SE9 `DeMorganExpansion` | SE10 `DeMorganContraction` |
| `redundant_declaration` | SD2 `RedundantDeclarationInsertion` | SD3 `RedundantDeclarationRemoval` |
| `declaration_initialization` | SD4 `DeclarationSplitting` | SD5 `DeclarationMerging` |
| `redundant_computation` | SS2 `RedundantComputationInsertion` | SS3 `RedundantComputationRemoval` |
| `computation_extraction` | SS4 `ComputationSplitting` | SS5 `ComputationMerging` |
| `redundant_branch` | CC2 `RedundantBranchInsertion` | CC3 `RedundantBranchRemoval` |
| `dispatch_shared_body` | CC4 `IfToSwitchNesting` | CC6 `SwitchToIfNesting` |
| `dispatch_cloned_body` | CC5 `IfToSwitchCloning` | CC7 `SwitchToIfCloning` |
| `conjunction_structure` | CC8 `ConditionalNesting` | CC9 `ConditionalFlattening` |
| `conditional_assignment` | CC11 `ConditionalExpressionToIf` | CC12 `IfToConditionalExpression` |
| `disjunction_structure` | CC13 `DisjunctionBranchSplitting` | CC14 `DisjunctionBranchMerging` |
| `redundant_loop` | CL1 `RedundantLoopInsertion` | CL2 `RedundantLoopRemoval` |
| `for_while` | CL3 `ForToWhile` | CL4 `WhileToFor` |
| `for_do` | CL5 `ForToDoWhile` | CL6 `DoWhileToFor` |
| `do_while` | CL7 `DoWhileToWhile` | CL8 `WhileToDoWhile` |

## 同类可逆策略

| 编号 | 名称 | 反向机制 |
| --- | --- | --- |
| WI1 | `IdentifierRenaming` | `inverse_mapping` |
| SE1 | `OperandExchange` | `same_site` |
| SE4 | `RelationalExpressionRewriting` | `same_site` |
| SD1 | `DeclarationExchange` | `inverse_permutation` |
| SS1 | `IndependentComputationExchange` | `inverse_permutation` |
| CC1 | `IndependentCaseGroupPermutation` | `inverse_permutation` |
| CC10 | `ConditionInversionAndBranchExchange` | `normalized_involution` |

## 接口

```python
from operators import create_strategy, get_relation

op = create_strategy("SE8", language="c", seed=42)
result = op.apply("int f(int a){a=a+2;return a;}", k=1)
assert op.relation.inverse_id == "SE6"
assert get_relation("SE8").family_id == "compound_assignment"
```

应用记录保留 construction，并增加 family_id、inverse_id 和 direction。生成日志实现版本为 sct-v3，语言、编号和强度命名及禁止覆盖逻辑保持。

## 本轮新增 11 项

| 编号 | 中文含义 | 简例 |
| --- | --- | --- |
| WC6 | 整数加法合成 | 3+4 → 7 |
| WC7 | 整数减法合成 | 8-1 → 7 |
| WC8 | 逻辑取反常量还原 | !false → true，C 为 !0 → 1 |
| SE7 | 自增自减收缩 | a=a+1 → a++ |
| SE8 | 复合赋值收缩 | a=a+b → a+=b |
| SE9 | 德摩根展开 | !(P&&Q) → !P 或 !Q |
| SE10 | 德摩根收缩 | !P 或 !Q → !(P&&Q) |
| CC11 | 条件表达式转 if | x=P?a:b → if(P)x=a;else x=b |
| CC12 | if 转条件表达式 | if(P)x=a;else x=b → x=P?a:b |
| CC13 | 逻辑或分支拆分 | if(P 或 Q)B → if(P)B;else if(Q)B |
| CC14 | 逻辑或分支合并 | if(P)B;else if(Q)B → if(P 或 Q)B |

实际源码与中文逐项解释见 [案例确认稿](sct_c11.md)，必要前提与人工条件性论证见 [行为保持契约](sct_semantic_contracts.md)。

## 边界与兼容

- WC4 在两种语言统一只负责真值常量的取反表示，WC8 负责还原。C 的原 WC4 曾混合两个方向，调用签名保留，方向行为按新规范拆分。
- SE5、SE6 保留原公开类名和参数，方向明确为展开，SE7、SE8 提供收缩。Java 的同类型限制可能拒绝 long += 1，采用对应类型的 1L 可进入支持范围。
- Java 条件赋值首版只接受局部 int/long 且两个分支类型与目标完全相同。C 只接受普通 int。声明、return、数组与字段目标不在该对策略范围内。
- 德摩根变换保持顺序与短路，首版拒绝调用、拆箱、不明类型及模式作用域。两条对偶规律由同一方向策略自动识别。
- 逻辑或结构转换排除分支体中的声明和作用域敏感构造，合并要求两个体的源码完全相同，允许保守地拒绝实际等价但不同写法的体。
- CC10 在条件上下文消除已有外层取反，使重复应用不积累双重取反。辅助块仍可能增加，不承诺逐字复原。
- 反向策略不能恢复删除内容、历史名称或格式。loop/dispatch 生成的标签和辅助作用域可能超出对应反向规则的接受范围。精确撤销仍需原编辑记录，本轮未新增自动撤销 API。

## 验证

全部 51 项继续有实际改变代码的成功案例。新增 11 项均有两种语言的拒绝和重复应用检查。新增关系检查、17 对公共安全模式的直接往返适用性检查，以及 8 对新增方向的前后往返编译运行。逻辑与条件转换覆盖 25 个整数输入组合，C 额外检查短路保护 INT_MIN 取负的场景，启用 UBSan。生成及审计入口覆盖新编号、组合与禁止覆盖。最终结果单独记录在 验证摘要（历史记录，本次验证命令见 README）。这些是受限范围内的实现证据，不是形式化证明。
