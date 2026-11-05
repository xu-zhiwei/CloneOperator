> Historical implementation-level documentation. IDs refer to the internal registry. See [paper inventory](operators.md) for the public paper-numbered interface and [C applicability](c-applicability.md) for the broader C profile.

# C11 SCT 算子目录

Java 与 C 各有 51 个独立策略文件，编号和表格分类共用。本文仅说明 C11 首版。Java 为默认模式，既有接口保持 Java 行为。

## 使用与范围

```python
from operators import create_strategy
java_operator = create_strategy("SE1")
c_operator = create_strategy("SE1", language="c", seed=42)
result = c_operator.apply("int f(int a){return a+1;}", k=1)
assert result.language == "c"
```

```bash
python src/operate_source.py \
  --language c --input input.c --output output_c_SE2k1_SD2k1.c \
  --strategies SE2:1,SD2:1 --seed 42
```

单源码入口不需要代码对文件。生成入口 operate_sct.py、ASTNN/DSFM 自定义及组合入口、适用率审计均支持 --language c。数据容器格式与代码语言分别设置，未验证检测器的 C 预处理能力。C 生成输出和单源码输出名称必须包含 c_ 以及策略编号和强度，输出及日志使用排他创建，禁止覆盖。

输入可以是独立函数或不含预处理指令的完整翻译单元。输入须已有正确的 C11 编译上下文，不将源码片段之外的宏假定为已知。首版不执行预处理，任何 #include、#define、条件编译或其他预处理节点都会使变换拒绝，记录 unresolved_preprocessor_context。普通带头文件的源码文件因此会返回原文，不能将该情况计为成功。

计算规则仅确认普通局部 int 和 int 参数。不支持 typedef 别名、unsigned、long、浮点、混合类型、指针及数组访问、结构体成员、调用、除法和移位。拒绝 volatile、原子访问和地址已逃逸的绑定。常量采用无后缀十进制形式，范围限制为 C11 保证的 -32767 至 32767，不假定宿主 int 必为 32 位。

声明规则排除复杂声明符、多变量声明、限定符和循环头。控制或作用域重写拒绝函数内的 goto、标签、数组声明、限定符及非局部跳转。GNU 属性与汇编等已识别扩展也拒绝。临时变量名检查整个输入的标识符，名称提供器不得引入关键字、保留名或已有名称。回调类型和局部函数原型的参数不会误算为外层函数参数。

纯表达式允许原有整数算术，但不承诺原输入没有溢出。重排、拆分和展开保留已定义输入上的运算及其树结构。删除初始化或计算时另用更严格的 total 检查，只接受可证明不会引入或掩盖未定义行为的受限表达式。

本轮补充拒绝函数内枚举、结构体、联合体、泛型选择和数组声明符，以及三字符序列、双字符替代记号、通用字符转义、反斜杠续行和源码位置宏。C SE1 分别括起每个操作数，保留原运算树。函数声明符名称不作为参数引用参与重命名。全部策略的理论前提与推导见 [语义契约](sct_semantic_contracts.md)。

k 是成功应用次数上限。每轮只应用一个候选并重新解析，可重复修改同一位置，交换可抵消。解析通过不代表编译或行为验证通过。

## 全部策略

### WI1 IdentifierRenaming

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wi1-identifierrenaming)。

重命名绑定明确的普通局部 int 或 int 参数，同时修改属于该绑定的引用。支持同名变量的不同词法作用域。

实现文件为 `operators/c/word/identifier/replacement/identifier_renaming.py`。

变换前

```c
int f(int a){int value=a;return value;}
```

变换后

```c
int f(int a){int sctName0=a;return sctName0;}
```

拒绝示例

```c
int f(int *a){return *a;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### WC1 ConstantNeutralTermInsertion

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wc1-constantneutralterminsertion)。

为可确认 int 类型的十进制整数常量增加 + 0。

实现文件为 `operators/c/word/constant/redundancy/constant_neutral_term_insertion.py`。

变换前

```c
int f(int a){return 7;}
```

变换后

```c
int f(int a){return (7 + 0);}
```

拒绝示例

```c
unsigned f(void){return 4294967295U;}
```

该输入保持原文，记录 `literal_type_or_context_unknown, no_safe_site`。此外适用上面的公共限制。

### WC2 ConstantNeutralTermRemoval

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wc2-constantneutraltermremoval)。

删除整数常量右侧的 + 0 或 - 0，要求两侧均为受支持的 int 常量。

实现文件为 `operators/c/word/constant/redundancy/constant_neutral_term_removal.py`。

变换前

```c
int f(int a){return 7+0;}
```

变换后

```c
int f(int a){return 7;}
```

拒绝示例

```c
unsigned f(void){return 7U+0U;}
```

该输入保持原文，记录 `not_redundant_int_constant, no_safe_site`。此外适用上面的公共限制。

### WC3 IntegerAdditionDecomposition

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wc3-integeradditiondecomposition)。

将受支持整数常量拆为两个 int 常量之和，生成操作数和结果均在保证范围内。

实现文件为 `operators/c/word/constant/replacement/integer_addition_decomposition.py`。

变换前

```c
int f(int a){return 32767;}
```

变换后

```c
int f(int a){return (16383 + 16384);}
```

拒绝示例

```c
long f(void){return 32768L;}
```

该输入保持原文，记录 `literal_type_or_context_unknown, no_safe_site`。此外适用上面的公共限制。

### WC4 BooleanNegationReplacement

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wc4-booleannegationreplacement)。

将 int 常量 0、1 与逻辑取反表达式互换，不引入 bool 宏或头文件。

实现文件为 `operators/c/word/constant/replacement/boolean_negation_replacement.py`。

变换前

```c
int f(int a){return 1;}
```

变换后

```c
int f(int a){return (!0);}
```

拒绝示例

```c
int f(void){return 2;}
```

该输入保持原文，记录 `not_confirmed_int_truth_value, no_safe_site`。此外适用上面的公共限制。

### WC5 IntegerSubtractionRepresentation

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#wc5-integersubtractionrepresentation)。

以非零差值构造同值 int 减法。最大正值使用减去 -1 的构造，避免生成越界正操作数。

实现文件为 `operators/c/word/constant/replacement/integer_subtraction_representation.py`。

变换前

```c
int f(int a){return 32767;}
```

变换后

```c
int f(int a){return (32766 - (-1));}
```

拒绝示例

```c
unsigned f(void){return 4294967295U;}
```

该输入保持原文，记录 `literal_type_or_context_unknown, no_safe_site`。此外适用上面的公共限制。

### SE1 OperandExchange

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se1-operandexchange)。

交换纯 int 表达式中 +、*、&、|、^、==、!= 的操作数，不交换短路运算。

实现文件为 `operators/c/statement/expression/reordering/operand_exchange.py`。

变换前

```c
int f(int a){return a+1;}
```

变换后

```c
int f(int a){return ((1) + (a));}
```

拒绝示例

```c
int f(int *a,int b){return *a+b;}
```

该输入保持原文，记录 `noncommutative_or_effectful_expression, no_safe_site`。此外适用上面的公共限制。

### SE2 ExpressionRedundantWrapping

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se2-expressionredundantwrapping)。

为确定读取 int 值的变量或纯表达式增加 + 0，排除赋值左侧和自增操作数。

实现文件为 `operators/c/statement/expression/redundancy/expression_redundant_wrapping.py`。

变换前

```c
int f(int a){return a;}
```

变换后

```c
int f(int a){return ((a) + 0);}
```

拒绝示例

```c
double f(double a){return a;}
```

该输入保持原文，记录 `not_pure_int_rvalue, no_safe_site`。此外适用上面的公共限制。

### SE3 ExpressionRedundantUnwrapping

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se3-expressionredundantunwrapping)。

删除非字面量纯 int 表达式右侧的 + 0。

实现文件为 `operators/c/statement/expression/redundancy/expression_redundant_unwrapping.py`。

变换前

```c
int f(int a){return a+0;}
```

变换后

```c
int f(int a){return (a);}
```

拒绝示例

```c
double f(double a){return a+0.0;}
```

该输入保持原文，记录 `not_wrapped_int_expression, no_safe_site`。此外适用上面的公共限制。

### SE4 RelationalExpressionRewriting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se4-relationalexpressionrewriting)。

交换局部 int 或整数常量的关系比较操作数，并翻转 <、<=、>、>=。

实现文件为 `operators/c/statement/expression/replacement/relational_expression_rewriting.py`。

变换前

```c
int f(int a){return a<3;}
```

变换后

```c
int f(int a){return (3 > a);}
```

拒绝示例

```c
int f(unsigned a,int b){return a<b;}
```

该输入保持原文，记录 `relational_type_or_effect_unknown, no_safe_site`。此外适用上面的公共限制。

### SE5 IncrementDecrementRewriting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se5-incrementdecrementrewriting)。

将独立语句中的局部 int 自增、自减改为 += 1、-= 1。

实现文件为 `operators/c/statement/expression/replacement/increment_decrement_rewriting.py`。

变换前

```c
int f(int a){a++;return a;}
```

变换后

```c
int f(int a){a += 1;return a;}
```

拒绝示例

```c
int f(volatile int a){a++;return a;}
```

该输入保持原文，记录 `update_binding_unknown, no_safe_site`。此外适用上面的公共限制。

### SE6 CompoundAssignmentRewriting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#se6-compoundassignmentrewriting)。

将局部 int 的 +=、-=、*= 展开为普通赋值，右侧要求纯 int 表达式。

实现文件为 `operators/c/statement/expression/replacement/compound_assignment_rewriting.py`。

变换前

```c
int f(int a){a+=2;return a;}
```

变换后

```c
int f(int a){a = a + (2);return a;}
```

拒绝示例

```c
int f(int *a){*a+=1;return *a;}
```

该输入保持原文，记录 `compound_assignment_not_pure_int, no_safe_site`。此外适用上面的公共限制。

### SD1 DeclarationExchange

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#sd1-declarationexchange)。

交换同一块中相邻的单变量 int 声明。初始化必须可证明无副作用和未定义行为，并排除名字遮蔽引起的绑定变化。

实现文件为 `operators/c/statement/declaration/reordering/declaration_exchange.py`。

变换前

```c
int f(int a){int x=1;int y=2;return a+x+y;}
```

变换后

```c
int f(int a){int y=2;int x=1;return a+x+y;}
```

拒绝示例

```c
int g(void);int f(void){int a=g();int b=1;return a+b;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### SD2 RedundantDeclarationInsertion

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#sd2-redundantdeclarationinsertion)。

在函数入口插入新鲜 int 变量及常量初始化。

实现文件为 `operators/c/statement/declaration/redundancy/redundant_declaration_insertion.py`。

变换前

```c
int f(int a){return a;}
```

变换后

```c
int f(int a){ int sctTemp0 = 0; return a;}
```

拒绝示例

```c
int f(int a){end:return a;}
```

该输入保持原文，记录 `not_safe_function_entry, no_safe_site`。此外适用上面的公共限制。

### SD3 RedundantDeclarationRemoval

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#sd3-redundantdeclarationremoval)。

删除无引用的局部 int 声明，初始化若存在则须证明可安全删除。

实现文件为 `operators/c/statement/declaration/redundancy/redundant_declaration_removal.py`。

变换前

```c
int f(int a){int unused=1;return a;}
```

变换后

```c
int f(int a){return a;}
```

拒绝示例

```c
int g(void);int f(void){int a=g();return 0;}
```

该输入保持原文，记录 `declaration_used_or_initializer_unsafe, no_safe_site`。此外适用上面的公共限制。

### SD4 DeclarationSplitting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#sd4-declarationsplitting)。

拆分单变量 int 声明和初始化。初始化要求纯整数表达式。

实现文件为 `operators/c/statement/declaration/replacement/declaration_splitting.py`。

变换前

```c
int f(int a){int x=a+1;return x;}
```

变换后

```c
int f(int a){int x; x = a+1;return x;}
```

拒绝示例

```c
int f(int a){const int x=a;return x;}
```

该输入保持原文，记录 `not_splittable_int_declaration, no_safe_site`。此外适用上面的公共限制。

### SD5 DeclarationMerging

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#sd5-declarationmerging)。

合并相邻的未初始化 int 声明与该绑定的普通赋值，拒绝自引用右侧。

实现文件为 `operators/c/statement/declaration/replacement/declaration_merging.py`。

变换前

```c
int f(int a){int x;x=a+1;return x;}
```

变换后

```c
int f(int a){int x = a+1;return x;}
```

拒绝示例

```c
int f(int a){int x;x=x+1;return x;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### SS1 IndependentComputationExchange

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#ss1-independentcomputationexchange)。

交换同一块中相邻、无读写依赖的纯局部 int 普通赋值。

实现文件为 `operators/c/statement/ordinary_statement/reordering/independent_computation_exchange.py`。

变换前

```c
int f(int a){int x=0;int y=0;x=a+1;y=a+2;return x+y;}
```

变换后

```c
int f(int a){int x=0;int y=0;y=a+2;x=a+1;return x+y;}
```

拒绝示例

```c
int f(int a,int b){a=b+1;b=a+1;return a+b;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### SS2 RedundantComputationInsertion

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#ss2-redundantcomputationinsertion)。

在函数入口插入隔离块，包含新鲜 int 变量及常量算术赋值，避免累积溢出。

实现文件为 `operators/c/statement/ordinary_statement/redundancy/redundant_computation_insertion.py`。

变换前

```c
int f(int a){return a;}
```

变换后

```c
int f(int a){ { int sctTemp0 = 0; sctTemp0 = 1 + 2; } return a;}
```

拒绝示例

```c
int f(int a){end:return a;}
```

该输入保持原文，记录 `not_safe_function_entry, no_safe_site`。此外适用上面的公共限制。

### SS3 RedundantComputationRemoval

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#ss3-redundantcomputationremoval)。

删除相邻的局部 int 声明与普通赋值，变量所有引用均限于该赋值，初始化及右侧均须可安全删除。

实现文件为 `operators/c/statement/ordinary_statement/redundancy/redundant_computation_removal.py`。

变换前

```c
int f(int a){int unused=0;unused=1+2;return a;}
```

变换后

```c
int f(int a){return a;}
```

拒绝示例

```c
int f(int a){int x=0;x=a+1;return x;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### SS4 ComputationSplitting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#ss4-computationsplitting)。

从直接赋值的非短路二元右侧提取左子表达式为新鲜 int 临时变量，保留原运算树。

实现文件为 `operators/c/statement/ordinary_statement/replacement/computation_splitting.py`。

变换前

```c
int f(int a){a=(a+1)*2;return a;}
```

变换后

```c
int f(int a){int sctTemp0 = (a+1); a = sctTemp0*2;return a;}
```

拒绝示例

```c
int f(int a){a=a && (a+1);return a;}
```

该输入保持原文，记录 `no_unconditionally_evaluated_subexpression, no_safe_site`。此外适用上面的公共限制。

### SS5 ComputationMerging

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#ss5-computationmerging)。

将相邻声明中仅使用一次的 int 临时值内联到纯赋值右侧，拒绝短路或条件求值位置。

实现文件为 `operators/c/statement/ordinary_statement/replacement/computation_merging.py`。

变换前

```c
int f(int a){int tmp=a+1;a=tmp*2;return a;}
```

变换后

```c
int f(int a){a=(a+1)*2;return a;}
```

拒绝示例

```c
int f(int a){int t=a+1;a=a && t;return a;}
```

该输入保持原文，记录 `no_safe_site`。此外适用上面的公共限制。

### CC1 IndependentCaseGroupPermutation

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc1-independentcasegrouppermutation)。

交换传统 switch 的完整分组，保留共享标签和组内顺序。分组必须以直接 break 或 return 结束。

实现文件为 `operators/c/control/conditional/reordering/independent_case_group_permutation.py`。

变换前

```c
int f(int a){switch(a){case 0:case 1:a=2;break;default:a=3;break;}return a;}
```

变换后

```c
int f(int a){switch(a){ default: a=3;
break; case 0: case 1: a=2;
break; }return a;}
```

拒绝示例

```c
int f(int a){switch(a){case 0:a=2;case 1:a=3;break;}return a;}
```

该输入保持原文，记录 `case_fallthrough_or_complex_control, no_safe_site`。此外适用上面的公共限制。

### CC2 RedundantBranchInsertion

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc2-redundantbranchinsertion)。

在函数入口插入 if (0) 冗余块。

实现文件为 `operators/c/control/conditional/redundancy/redundant_branch_insertion.py`。

变换前

```c
int f(int a){return a;}
```

变换后

```c
int f(int a){ if (0) { int sctTemp0 = 0; } return a;}
```

拒绝示例

```c
int f(int a){end:return a;}
```

该输入保持原文，记录 `not_safe_function_entry, no_safe_site`。此外适用上面的公共限制。

### CC3 RedundantBranchRemoval

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc3-redundantbranchremoval)。

删除条件为可证明常量零的分支，保留 else 的可执行部分及块边界。

实现文件为 `operators/c/control/conditional/redundancy/redundant_branch_removal.py`。

变换前

```c
int f(int a){if(0){a=2;}else{a=3;}return a;}
```

变换后

```c
int f(int a){{ {a=3;} }return a;}
```

拒绝示例

```c
int f(int a){if(a){a=2;}return a;}
```

该输入保持原文，记录 `condition_not_provably_false, no_safe_site`。此外适用上面的公共限制。

### CC4 IfToSwitchNesting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc4-iftoswitchnesting)。

将稳定 int 变量的等值 if 链转成 switch，同一分支的多个值共享一份分支体。

实现文件为 `operators/c/control/conditional/replacement/if_to_switch_nesting.py`。

变换前

```c
int f(int a){if(a==0 || a==1){a=2;}else{a=3;}return a;}
```

变换后

```c
int f(int a){switch (a) { case 0: case 1: {a=2;} break; default: {a=3;} }return a;}
```

拒绝示例

```c
int g(int);int f(int a){if(g(a)==1){a=2;}return a;}
```

该输入保持原文，记录 `not_stable_integer_equality_chain, no_safe_site`。此外适用上面的公共限制。

### CC5 IfToSwitchCloning

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc5-iftoswitchcloning)。

将同类 if 链转成 switch，为每个值复制分支体。

实现文件为 `operators/c/control/conditional/replacement/if_to_switch_cloning.py`。

变换前

```c
int f(int a){if(a==0 || a==1){a=2;}else{a=3;}return a;}
```

变换后

```c
int f(int a){switch (a) { case 0: {a=2;} break; case 1: {a=2;} break; default: {a=3;} }return a;}
```

拒绝示例

```c
int f(int a){while(a){if(a==1){break;}a--;}return a;}
```

该输入保持原文，记录 `not_stable_integer_equality_chain, no_safe_site`。此外适用上面的公共限制。

### CC6 SwitchToIfNesting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc6-switchtoifnesting)。

将受限 switch 转为逐组条件块，用选择值快照及激活标志保留穿透，分支体不复制。

实现文件为 `operators/c/control/conditional/replacement/switch_to_if_nesting.py`。

变换前

```c
int f(int a){switch(a){case 0:a+=1;case 1:a+=2;break;default:a=3;}return a;}
```

变换后

```c
int f(int a){{ int sctSelector0 = a; int sctActive0 = 0; if (sctSelector0 == 0) sctActive0 = 1; if (sctActive0) { a+=1;  } if (sctSelector0 == 1) sctActive0 = 1; if (sctActive0) { a+=2; sctActive0 = 0; } if ((sctSelector0 != 0 && sctSelector0 != 1)) sctActive0 = 1; if (sctActive0) { a=3;  } }return a;}
```

拒绝示例

```c
int f(int a){switch(a){case 1:if(a)break;default:a=2;}return a;}
```

该输入保持原文，记录 `switch_control_or_binding_unknown, no_safe_site`。此外适用上面的公共限制。

### CC7 SwitchToIfCloning

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc7-switchtoifcloning)。

将受限 switch 转成互斥条件分支，为每个入口复制执行至终止组的后缀。

实现文件为 `operators/c/control/conditional/replacement/switch_to_if_cloning.py`。

变换前

```c
int f(int a){switch(a){case 0:a+=1;case 1:a+=2;break;default:a=3;}return a;}
```

变换后

```c
int f(int a){{ int sctSelector0 = a; if (sctSelector0 == 0) { a+=1; a+=2; } else if (sctSelector0 == 1) { a+=2; } else if ((sctSelector0 != 0 && sctSelector0 != 1)) { a=3; } }return a;}
```

拒绝示例

```c
int f(int a){switch(a){case 1:if(a)break;default:a=2;}return a;}
```

该输入保持原文，记录 `switch_control_or_binding_unknown, no_safe_site`。此外适用上面的公共限制。

### CC8 ConditionalNesting

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc8-conditionalnesting)。

将无 else 的 if (a && b) 转成嵌套 if，保持从左到右短路顺序。

实现文件为 `operators/c/control/conditional/replacement/conditional_nesting.py`。

变换前

```c
int f(int a){if(a>0 && a<3){a=2;}return a;}
```

变换后

```c
int f(int a){if (a>0) { if (a<3) { {a=2;} } }return a;}
```

拒绝示例

```c
int f(int a){if(a>0 && a<3){a=2;}else{a=3;}return a;}
```

该输入保持原文，记录 `not_safe_conjunction_without_else, no_safe_site`。此外适用上面的公共限制。

### CC9 ConditionalFlattening

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc9-conditionalflattening)。

将无 else、外层体只有内层 if 的嵌套条件转成 &&，拒绝夹带声明或其他语句。

实现文件为 `operators/c/control/conditional/replacement/conditional_flattening.py`。

变换前

```c
int f(int a){if(a>0){if(a<3){a=2;}}return a;}
```

变换后

```c
int f(int a){if ((a>0) && (a<3)) { {a=2;} }return a;}
```

拒绝示例

```c
int f(int a){if(a>0){int x=1;if(a<3){a=x;}}return a;}
```

该输入保持原文，记录 `not_exact_nested_if, no_safe_site`。此外适用上面的公共限制。

### CC10 ConditionInversionAndBranchExchange

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cc10-conditioninversionandbranchexchange)。

对完整 if/else 取反条件并交换分支，分别包裹分支体以避免悬空 else。

实现文件为 `operators/c/control/conditional/replacement/condition_inversion_and_branch_exchange.py`。

变换前

```c
int f(int a){if(a>0){a=2;}else{a=3;}return a;}
```

变换后

```c
int f(int a){if (!((a>0))) { {a=3;} } else { {a=2;} }return a;}
```

拒绝示例

```c
int f(int a){if(a>0){a=2;}return a;}
```

该输入保持原文，记录 `missing_else_or_unknown_condition, no_safe_site`。此外适用上面的公共限制。

### CL1 RedundantLoopInsertion

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl1-redundantloopinsertion)。

插入由新鲜普通 int 变量控制的零次 while。

实现文件为 `operators/c/control/loop/redundancy/redundant_loop_insertion.py`。

变换前

```c
int f(int a){return a;}
```

变换后

```c
int f(int a){ { int sctTemp0 = 0; while (sctTemp0) { sctTemp0 = 0; } } return a;}
```

拒绝示例

```c
int f(int a){end:return a;}
```

该输入保持原文，记录 `not_safe_function_entry, no_safe_site`。此外适用上面的公共限制。

### CL2 RedundantLoopRemoval

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl2-redundantloopremoval)。

删除常量假条件且无初始化的 while/for，或紧邻无外部使用的零初始化变量控制的 while。变量声明保留。

实现文件为 `operators/c/control/loop/redundancy/redundant_loop_removal.py`。

变换前

```c
int f(int a){while(0){a++;}return a;}
```

变换后

```c
int f(int a){;return a;}
```

拒绝示例

```c
int g(void);int f(int a){for(g();0;){a++;}return a;}
```

该输入保持原文，记录 `loop_not_provably_zero_or_has_initializer, no_safe_site`。此外适用上面的公共限制。

### CL3 ForToWhile

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl3-fortowhile)。

将 for 转为外层初始化和 while，正常迭代及针对当前循环的 continue 均执行原更新。

实现文件为 `operators/c/control/loop/replacement/for_to_while.py`。

变换前

```c
int f(int a){for(int i=0;i<3;i++){if(i==1)continue;a++;}return a;}
```

变换后

```c
int f(int a){{ int i=0; while (i<3) { {if(i==1){ i++; continue; }a++;} i++; } }return a;}
```

拒绝示例

```c
int f(int a){end:for(int i=0;i<3;i++){a++;}return a;}
```

该输入保持原文，记录 `complex_loop_control_or_scope, no_safe_site`。此外适用上面的公共限制。

### CL4 WhileToFor

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl4-whiletofor)。

将 while 转为无初始化、无更新的 for。

实现文件为 `operators/c/control/loop/replacement/while_to_for.py`。

变换前

```c
int f(int a){int i=0;while(i<3){i++;if(i==2)continue;a++;}return a;}
```

变换后

```c
int f(int a){int i=0;for (; (i<3); ) {i++;if(i==2)continue;a++;}return a;}
```

拒绝示例

```c
int f(int a){end:while(a<3){a++;}return a;}
```

该输入保持原文，记录 `complex_loop_control_or_scope, no_safe_site`。此外适用上面的公共限制。

### CL5 ForToDoWhile

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl5-fortodowhile)。

使用外层条件守卫将 for 转为 do/while，保持零次执行及更新顺序。

实现文件为 `operators/c/control/loop/replacement/for_to_do_while.py`。

变换前

```c
int f(int a){for(int i=0;i<3;i++){if(i==1)continue;a++;}return a;}
```

变换后

```c
int f(int a){{ int i=0; if (i<3) { do { {if(i==1){ i++; continue; }a++;} i++; } while (i<3); } }return a;}
```

拒绝示例

```c
int f(int a){for(int i=0;i<3;i++){int i=5;if(a)continue;a+=i;}return a;}
```

该输入保持原文，记录 `for_update_name_capture, no_safe_site`。此外适用上面的公共限制。

### CL6 DoWhileToFor

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl6-dowhiletofor)。

以常量循环头和首轮标志将 do/while 转为 for，continue 经更新清除标志后，在下轮内部守卫求值条件。保留常量循环头，避免引入 C11 的非常量循环终止假定。

实现文件为 `operators/c/control/loop/replacement/do_while_to_for.py`。

变换前

```c
int f(int a){int i=0;do{i++;if(i==2)continue;a++;}while(i<3);return a;}
```

变换后

```c
int f(int a){int i=0;{ int sctFirst0 = 1; for (; 1; sctFirst0 = 0) { if (!sctFirst0 && !((i<3))) break; {i++;if(i==2)continue;a++;} } }return a;}
```

拒绝示例

```c
int f(int a){end:do{a++;}while(a<3);return a;}
```

该输入保持原文，记录 `complex_loop_control_or_scope, no_safe_site`。此外适用上面的公共限制。

### CL7 DoWhileToWhile

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl7-dowhiletowhile)。

以常量循环头和首轮标志将 do/while 转为 while，内部守卫在首轮跳过条件，其后及 continue 均求值原条件。不会把原常量循环头变成非常量循环头。

实现文件为 `operators/c/control/loop/replacement/do_while_to_while.py`。

变换前

```c
int f(int a){int i=0;do{i++;if(i==2)continue;a++;}while(i<3);return a;}
```

变换后

```c
int f(int a){int i=0;{ int sctFirst0 = 1; while (1) { if (!sctFirst0 && !((i<3))) break; sctFirst0 = 0; {i++;if(i==2)continue;a++;} } }return a;}
```

拒绝示例

```c
int f(int a){do{if(a)goto end;a++;}while(a<3);end:return a;}
```

该输入保持原文，记录 `complex_loop_control_or_scope, no_safe_site`。此外适用上面的公共限制。

### CL8 WhileToDoWhile

逐项理论前提与推导见 [语义契约](sct_semantic_contracts.md#cl8-whiletodowhile)。

使用外层守卫将 while 转为 do/while，完整外层块避免改变原先 else 的归属。

实现文件为 `operators/c/control/loop/replacement/while_to_do_while.py`。

变换前

```c
int f(int a){int i=0;while(i<3){i++;if(i==2)continue;a++;}return a;}
```

变换后

```c
int f(int a){int i=0;{ if ((i<3)) { do {i++;if(i==2)continue;a++;} while ((i<3)); } }return a;}
```

拒绝示例

```c
int f(int a){end:while(a<3){a++;}return a;}
```

该输入保持原文，记录 `complex_loop_control_or_scope, no_safe_site`。此外适用上面的公共限制。

## 验证边界

编译运行测试使用 GCC、-std=c11、-pedantic-errors、UBSan 与禁止恢复的未定义行为检测。原程序采用 -O0，变换程序采用 -O2，在固定输入上比较输出、错误输出和退出状态。无限循环采用双侧超时检查。这些样例不是任意 C 程序行为等价的证明。


## 双向扩展策略

以下 11 项沿用原分类目录，一项一个策略文件。

### WC6 IntegerAdditionComposition

整数加法合成。把同类型整数常量的加法合成为一个常量，检查结果可表示。

适用与拒绝边界。只合成字面量，不对可能溢出的 C 运算做数学化简。

对应方向为 `WC3`。详细前提见 [语义契约](sct_semantic_contracts.md#wc6-integeradditioncomposition)。

变换前

```c
int f(int a){return 3+4;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){return (7);}
```

拒绝或不适用的案例

```c
unsigned f(int a){return 3U+4U;}
```

### WC7 IntegerSubtractionComposition

整数减法合成。把同类型整数常量的减法合成为一个常量。

适用与拒绝边界。保留 int/long 类型，越界结果拒绝，不能套用无限精度整数。

对应方向为 `WC5`。详细前提见 [语义契约](sct_semantic_contracts.md#wc7-integersubtractioncomposition)。

变换前

```c
int f(int a){return 8-1;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){return (7);}
```

拒绝或不适用的案例

```c
int f(int a){return -32767-1;}
```

### WC8 BooleanNegationConstantReduction

逻辑取反常量还原。Java 将 !false、!true 还原为布尔常量，C 将 !0、!1 还原为 int 真值。

适用与拒绝边界。只处理明确的真值常量，不把任意 !x 当作常量。

对应方向为 `WC4`。详细前提见 [语义契约](sct_semantic_contracts.md#wc8-booleannegationconstantreduction)。

变换前

```c
int f(int a){return !0;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){return 1;}
```

拒绝或不适用的案例

```c
int f(int a){return !a;}
```

### SE7 IncrementDecrementContraction

自增自减收缩。把独立语句中的单位加减赋值改为自增或自减。

适用与拒绝边界。只处理结果被丢弃的稳定局部整数目标，不转换被 return 等观察的赋值表达式。

对应方向为 `SE5`。详细前提见 [语义契约](sct_semantic_contracts.md#se7-incrementdecrementcontraction)。

变换前

```c
int f(int a){a=a+1;return a;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){a++;return a;}
```

拒绝或不适用的案例

```c
int f(volatile int a){a=a+1;return a;}
```

### SE8 CompoundAssignmentContraction

复合赋值收缩。把 x=x op E 改为 x op= E，左侧和右侧的 x 必须是同一绑定。

适用与拒绝边界。只接受匹配类型的纯整数右值，保留原运算树，不允许借交换律匹配 x=E op x。

对应方向为 `SE6`。详细前提见 [语义契约](sct_semantic_contracts.md#se8-compoundassignmentcontraction)。

变换前

```c
int f(int a){int b=2;a=a+b;return a;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){int b=2;a += (b);return a;}
```

拒绝或不适用的案例

```c
int f(int a){a=a+g();return a;}
```

### SE9 DeMorganExpansion

德摩根展开。将 !(P&&Q) 改为 !P||!Q，或将 !(P||Q) 改为 !P&&!Q。

适用与拒绝边界。保持左右顺序与短路，Java 只接受基本布尔类型，C 使用普通 int 真值。

对应方向为 `SE10`。详细前提见 [语义契约](sct_semantic_contracts.md#se9-demorganexpansion)。

变换前

```c
int f(int a){return !(a>0 && a<3);}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){return (!(a>0) || !(a<3));}
```

拒绝或不适用的案例

```c
int f(int *a){return !(*a && a);}
```

### SE10 DeMorganContraction

德摩根收缩。把两个显式取反操作数所在的逻辑运算收缩为对偶运算的整体取反。

适用与拒绝边界。不是位运算改写，两个操作数都必须符合已确认的逻辑类型和纯度要求。

对应方向为 `SE9`。详细前提见 [语义契约](sct_semantic_contracts.md#se10-demorgancontraction)。

变换前

```c
int f(int a){return !(a>0) || !(a<3);}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){return !(((a>0)) && ((a<3)));}
```

拒绝或不适用的案例

```c
int f(int a){return a || a;}
```

### CC11 ConditionalExpressionToIf

条件表达式转 if。把 x=P?a:b 的独立赋值语句展开为完整 if/else。

适用与拒绝边界。P 只求值一次，a、b 只执行被选中的一个。首版不转换声明、return 或复杂赋值目标。

对应方向为 `CC12`。详细前提见 [语义契约](sct_semantic_contracts.md#cc11-conditionalexpressiontoif)。

变换前

```c
int f(int a){int x=0;x=a>0 ? a : 0;return x;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){int x=0;if (a>0) { x = a; } else { x = 0; }return x;}
```

拒绝或不适用的案例

```c
int f(int a){int x=0;x=a?g():0;return x;}
```

### CC12 IfToConditionalExpression

if 转条件表达式。把完整 if/else 中对同一局部变量的单条赋值合并为条件表达式赋值。

适用与拒绝边界。两个分支不能包含额外语句，Java 分支类型与目标必须完全一致，避免条件表达式的额外类型推断。

对应方向为 `CC11`。详细前提见 [语义契约](sct_semantic_contracts.md#cc12-iftoconditionalexpression)。

变换前

```c
int f(int a){int x=0;if(a>0){x=a;}else{x=0;}return x;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){int x=0;x = ((a>0)) ? (a) : (0);return x;}
```

拒绝或不适用的案例

```c
int f(int a){int x=0,y=0;if(a){x=1;}else{y=1;}return x+y;}
```

### CC13 DisjunctionBranchSplitting

逻辑或分支拆分。将 if(P||Q){B} 改为 if(P){B}else if(Q){B}。

适用与拒绝边界。P 为真时不求值 Q，B 只执行一次。复制体排除声明、模式绑定与标签等作用域敏感内容。

对应方向为 `CC14`。详细前提见 [语义契约](sct_semantic_contracts.md#cc13-disjunctionbranchsplitting)。

变换前

```c
int f(int a){int x=0;if(a>0 || a < -1){x=3;}return x;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){int x=0;if (a>0) { {x=3;} } else if (a < -1) { {x=3;} }return x;}
```

拒绝或不适用的案例

```c
int f(int a){if(a || g()){a=1;}return a;}
```

### CC14 DisjunctionBranchMerging

逻辑或分支合并。把没有最终 else、两个体完全相同的 if/else if 合并成逻辑或条件。

适用与拒绝边界。必须核对两个体确实相同且没有声明影响绑定，不能仅凭测试结果相似就合并。

对应方向为 `CC13`。详细前提见 [语义契约](sct_semantic_contracts.md#cc14-disjunctionbranchmerging)。

变换前

```c
int f(int a){int x=0;if(a>0){x=3;}else if(a < -1){x=3;}return x;}
```

变换后，seed=42、selection=first、k=1

```c
int f(int a){int x=0;if (((a>0)) || ((a < -1))) { {x=3;} }return x;}
```

拒绝或不适用的案例

```c
int f(int a){if(a>0){a=1;}else if(a<0){a=2;}return a;}
```
