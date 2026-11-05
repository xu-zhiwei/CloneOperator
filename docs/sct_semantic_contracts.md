> Historical implementation-level documentation. IDs refer to the internal registry. See [paper inventory](operators.md) for the public paper-numbered interface and [C applicability](c-applicability.md) for the broader C profile.

# SCT 行为保持契约与逐策略论证

本文件对应 Java 与 C 两种语言的全部 51 个策略，共 102 个实现。契约的可查询定义位于 `src/operators/base/contracts.py`，实例通过 `semantic_contract` 属性访问。每项均给出变换规律、必要前提、状态与求值轨迹的对应关系、语言限制、实现位置及正例。

这些是可以审查的条件性论证，不是机器验证的形式化证明。实现检查是否充分仍需要独立审查与反例测试。测试通过不能升级为任意输入上的保证，`successful` 也只表示候选检查与语法解析通过。应用记录现在明确写入 `validation = candidate_checks_and_parse_only`。

## 1. 语义模型与共同前提

输入必须是在既定语言版本和编译上下文中合法的程序。独立方法或函数必须提供真实的参数、类型与宏上下文，不能把 Tree-sitter 解析成功当作类型检查成功。Java 编译运行证据来自本机 Java 11。文本块的源码字节保持单独检查，未在该编译器上运行。C 以相同实现、相同整数表示、相同输入和 C11 选项比较两侧，原程序输入限于已定义行为。

对一次执行，以 σ 表示程序状态，以 τ 表示外部可观察的动作序列，以 ρ 表示正常返回、异常退出或不终止。状态投影 π 去掉新引入且不逃逸的局部变量。目标是在每项前提成立时，使原程序和变换程序得到同一 τ、相应的 ρ，以及相同的 π(σ)。重命名使用绑定之间的双射代替直接去掉变量。异常比较关注异常种类及与源代码位置无关的业务内容。

本模型不把源码文本、参数反射名称、调试信息、堆栈行号、诊断中的源码变量名、运行时间、内存占用或资源耗尽视为不变观察量。包含这些观察量的程序不在本次等价主张之内。不能据此声称连这些信息也完全不变。依赖未定义行为或隐藏宏上下文的 C 输入同样不在主张范围内。

Java 的计算检查限制在可解析的局部绑定和受支持的基本类型。字段、数组读写、装箱、拆箱、调用及不明转换不能被当作纯整数计算。捕获作用域和构造函数不能借用外层方法的符号。Java Unicode 转义涉及编译器的词法预处理，当前对含此类转义或标识符可忽略字符的输入与生成片段拒绝变换，避免把编译器认定为相同的名称当成不同拼写。

C 的计算检查聚焦普通局部 int 与 int 参数。常量采用可证明为 int 的无后缀十进制形式，生成常量限制在 -32767 至 32767。字段、指针、数组、限定访问、地址逃逸、混合有符号类型和调用均不作为纯计算处理。函数含枚举、结构体、联合体、泛型选择或数组声明符时，当前候选分析拒绝变换，避免不完整的名字空间和变长类型分析。预处理指令、C11 三字符序列、双字符替代记号、通用字符转义、反斜杠续行及源码位置宏也拒绝变换。

## 2. 共同证明义务

1. **绑定保持。** 变换后的每个原有引用仍对应原来的声明。新增名称检查整个方法或函数，不能捕获原有引用。重命名不得修改函数名、标签、成员或类型名字空间。
2. **类型和值保持。** 表达式替换保留静态类型或经验证的同一转换，不能仅凭数学相等忽略整数提升、窄化、字符串拼接或装箱。Java int/long 的环绕规则与 C 的有符号溢出规则分别处理。
3. **求值轨迹保持。** 保留原表达式树、每个有影响操作的次数与相对顺序，保留短路保护。交换需要读写独立且没有可能被观察的异常。新括号不能仅包住完整表达式而丢掉操作数自身的分组。
4. **控制完成保持。** 区分正常完成、break、continue、return 和 throw。循环转换明确处理跳转的真实目标，不能把内层循环跳转重定向到外层。Java 的 finally 必须先于原 for 的更新执行。
5. **静态合法性保持。** Java 的可达性、确定赋值和受检异常约束是额外证明义务。原程序运行时不走到的分支或条件，仍可能影响编译合法性。不能简单删除后仅做语法解析。
6. **局部到整体的提升。** 表达式规则在同类型、同求值位置的上下文中替换。语句规则按状态投影模拟。每次应用后重新解析并重新检查前提，逐次等价通过传递性推广到有限次组合。引入名称的批量修改必须重新分析，不能同时复用一个旧上下文生成同名临时变量。

上述义务分别由 Java 的 `analysis/semantic.py`、`analysis/completion.py`、条件与循环共享工具，以及 C 的 `analysis/context.py`、`tools/strategy.py`、`tools/control.py`落实。历史入口调用同一受检查的策略，不能直接调用绕过检查的旧字符串构造器。

## 3. 基本论证

对纯且不抛异常的表达式 E，其求值可记为一个不修改外部状态的值函数。中性项规则只在保持类型的情况下替换这个值函数。交换律只交换两个值函数的求值顺序，分别括起两个操作数以保留树形结构。C 不使用结合律重新组合有符号加乘。

对局部计算 S₁、S₂，若 W₁∩(R₂∪W₂)=∅ 且 W₂∩(R₁∪W₁)=∅，并且没有外部效果与异常，则两次状态更新可交换。涉及声明时还检查声明集合与所有跨越语句，避免名字遮蔽改变读写集合的含义。

对新增的未使用局部状态，原步骤对应变换程序中的若干无外部效果的步骤。投影后状态相同。删除规则要求被删状态没有存活引用，并且被删步骤无外部效果和可观察异常，形成反向模拟。提取与内联以同类型的单次求值为基本单位，不能改变受短路保护的求值或移动会失败的计算。

对结构控制规则，先列出条件、分支体、更新和跳转的事件轨迹，再按轨迹逐项对应。switch 转换额外冻结选择值。共享体形式的 active 状态表示已经进入原 switch 且尚未 break，复制体形式则枚举每个入口对应的穿透路径。C 的 do 转换使用常量循环头，将首轮标志和原条件放在内部守卫。这样不会因首轮标志把原常量循环头变成非常量循环头，从而引入 C11 第 6.8.5 节第 6 段的终止假定。循环使用每一轮边界处的相同原状态作为不变式。body 的 continue、break、return、throw 分别模拟，不只比较普通顺序执行。

语言规则依据见 [JLS 词法与标识符](https://docs.oracle.com/javase/specs/jls/se17/html/jls-3.html)、[JLS 名称与作用域](https://docs.oracle.com/javase/specs/jls/se17/html/jls-6.html)、[JLS 表达式](https://docs.oracle.com/javase/specs/jls/se17/html/jls-15.html)、[JLS 语句与可达性](https://docs.oracle.com/javase/specs/jls/se17/html/jls-14.html)及 [WG14 C11 草案 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)。本文件给出的状态投影和轨迹模拟是本项目的条件性论证。

### 3.1 条件性证明的分解

对规则 i，记 Aᵢ 为上述共同前提与该规则的必要前提，Tᵢ 为其构造。需要证明的是 Aᵢ(P, σ) 成立时，P 与 Tᵢ(P) 在本文件的观察模型中对应。候选分析器返回成功是否确实蕴含 Aᵢ，是另一项实现正确性义务。本次通过代码审查和反例回归检查该义务，尚未把 Python 分析器转换为可由证明助手验证的程序。

**L1 绑定双射。** 对一个声明 d 及其全部引用 R(d)，以全局新鲜的名称 n 同时替换 d 与 R(d)。未替换的引用不能被 n 捕获，已替换的引用不能越过其词法作用域。因而每次读取与写入仍访问同一原变量，按名称映射后的存储状态逐步对应。WI1 使用此论证，必须先排除编译器名称等价规则与分析器原始拼写比较不一致的情况。

**L2 同类型恒等替换。** 对原表达式 e 和替换 e′，证明它们具有同一静态类型、同一值和同一常量表达式资格，并且没有新增效果。v+0、v−0、v×1、v⊕0 的结果与 v 相同。分解 v=a+b 或 v=a−b 时，还分别证明两个操作数可表示。该证明逐个覆盖 WC1—WC5、SE2、SE3，不能跨类型套用数学等式。

**L3 有限宽度交换。** Java 整数加乘在对应位宽的环上满足交换律，位运算按位满足交换律，整数相等与关系比较通过对称关系对应。C 在原执行已定义且类型相同的前提下，交换后的操作数值相同，运算结果和可表示性相同。两种语言均要求两个原子树分别加括号。SE1、SE4 只交换无外部效果、无可观察失败的求值，不能借此重新结合三个操作数。

**L4 局部写入展开。** 设 x 的旧值为 v，纯右值 E 的值为 w。原复合赋值和新普通赋值都向 x 写入同一类型中的 v op w。需要排除转换差异，保证 E 不会改写 x、目标寻址稳定且没有额外可观察读写。独立自增、自减是 w=1 的特例，原表达式值不被使用。SE5、SE6 据此保持最终存储与动作序列。

**L5 独立更新可交换。** 对读写集合满足共同前提第 3 节不交条件的两个有限计算，先执行任一个都不改变另一个读取的值。每个计算无外部动作与异常，最终写入互不覆盖。声明还必须保持名字查找并检查被跨越的声明。对跨越多个语句的模式，逐一应用同一交换步骤，不能只比较两个端点。SD1、SS1 使用这个归纳。

**L6 新状态的静默扩展。** 新声明、计算、恒假分支或零次循环只访问新鲜局部状态。有限初始化与检查不抛异常，分支体和循环体按构造不执行，或执行的计算结果不逃逸。每个原步骤对应零个或有限个额外静默步骤，投影 π 后恢复原状态。SD2、SS2、CC2、CL1 分别证明自己生成的具体片段满足此条件。

**L7 无存活观察的删除。** 被删声明或计算的引用全部位于被删切片，或者原分支、循环体根本不会执行。删除的条件和初始化必须无可观察效果，存活部分不能依赖被删状态。Java 还单独保留受检异常、可达性与确定赋值事实，必要时保留常量 if 外壳。SD3、SS3、CC3、CL2 是不同删除单元，不能用“运行时不执行”替代静态合法性检查。

**L8 初始化位置对应。** SD4 在同一位置先建立原声明，再立即对同一绑定执行原初始化，保留多声明的原先顺序。SD5 为逆向步骤，只在被跨越的代码不改变输入、不使用未初始化目标、不改变名字查找时成立。Java 的 final、var、隐式转换以及 C 的限定符和复杂声明符分别处理。原初始化可能有作用时，只有不改变其执行点和转换上下文的模式可接受。

**L9 let 引入与消去。** SS4 以新鲜变量保存原子树的同类型值，再在原位置读取该值，证明父表达式得到相同操作数。提取不能越过短路保护，否则即使读取没有运行时副作用，也可能失去 Java 的确定赋值条件。SS5 则要求临时值只有一个已解析的使用，输入在移动区间不变。Java 允许安全省略未被求值的纯且总的初始化工作，C 首版额外拒绝短路与条件位置的内联。

**L10 分组置换。** CC1 将每组标签和其完整体视为一个不可分割的入口。标签互异、无穿透且无跨组作用域依赖时，选择值在置换前后到达同一组。原组内部语句和退出不变。模式匹配的优先顺序不满足此前提，因而 Java 模式 switch 不适用。

**L11 条件分派等价。** CC4、CC5 中，全部判断是对同一稳定局部值 v 与不同常量的相等测试。第一次匹配的标签唯一，未匹配时执行原 else。共享体与复制体均只执行一个原体，新增 switch 的 break 只在正常完成后执行。Java 还拒绝未初始化方法局部变量，避免把常量真 if 所建立的确定赋值错误地视为 switch 的确定赋值。

**L12 穿透路径模拟。** 对固定选择值 v，原 switch 唯一确定入口组 i。CC6 的 active 标志在入口 i 置真，在 break 之后置假，其余组按源顺序执行。每个组前的关系是 active 当且仅当原执行已进入 switch 且尚未离开。return、throw 没有后继步骤。CC7 直接复制从 i 起直到第一次退出的后缀，并以互斥条件选择唯一后缀。选择值先求值一次，不能因组内修改原变量而重新选择入口。

**L13 条件轨迹对应。** CC8 与 CC9 都产生“求值 a，若真再求值 b，若仍真才执行体”的轨迹。CC9 不得跨越中间声明和语句。CC10 求值同一个条件一次，将真值取反并交换两体，选择的原体不变。模式绑定不只依赖真假值，还依赖流作用域，所以必须单独拒绝。两种语言分别保持其条件类型与短路规则。

**L14 循环阶段模拟。** 用 I、Q、B、U 分别表示初始化、条件、原体和更新。for 的普通轨迹为 I，随后重复 Q 为真、B、U，最后 Q 为假。CL3 保留该阶段序列，CL5 把第一次 Q 放到外层守卫，之后用 do 的尾部 Q，既不增加也不遗漏测试。普通 continue 从 B 到 U，break、return、throw 跳过 U。Java 将针对该循环的 continue 转为退出新鲜的体标签，让 finally 完成后才到 U。

CL4 仅把 while 的空 I、空 U 显式写入 for。CL6、CL7 的原轨迹从 B 开始，再重复 Q 为真、B，最后 Q 为假。Java 的尾部测试构造通过体标签吸收原 continue，C 的首轮标志恰在第一次原体前为真，后续守卫每轮求值原 Q 一次。C 使用常量循环头，避免新增非常量循环的终止假定。CL8 把第一次 Q 放到外层守卫，再执行 B、Q 的重复阶段。对每轮入口的状态关系作归纳，并分别检查普通完成与四种跳转，即得到这些循环规则的条件性对应。

这些证明步骤说明为何各项前提足够，也说明遗漏前提会出现哪类反例。它们并不证明当前分析器已经覆盖所有编译器的全部语义，不能据此删除文件末尾列出的验证边界。

## 4. 逐策略契约

以下英文契约与可查询定义一致。各项同时受到上述共同前提的约束。实例拒绝任何无法建立必要前提的候选，不表示语言本身不存在更宽的安全变换。

### WI1 IdentifierRenaming

**规律** alpha conversion。

**必要前提** All uses have one lexical binding. The new name is fresh and legal. Captures and opaque scopes are excluded.

**保持语义的推导** A bijection on one binder and exactly its references preserves lookup, values and transfers.

**Java 边界** Constructor, lambda and class boundaries cannot borrow an outer method's scope. Captured or unresolved references reject the rename.

**C 边界** Only ordinary local int or int parameters. Function declarator names are not references. Address escape and opaque type scopes are excluded.

**实现对应** [Java 实现](../src/operators/java/word/identifier/replacement/identifier_renaming.py)，[C 实现](../src/operators/c/word/identifier/replacement/identifier_renaming.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ return a; }
```

**C 正例**

```c
int f(int a){int value=a;return value;}
```

### WC1 ConstantNeutralTermInsertion

**规律** v op identity = v。

**必要前提** The literal and neutral operand have the same promoted type and the result stays a constant expression.

**保持语义的推导** The operation returns the same value without effects or exceptions and has the same expression type.

**Java 边界** Only confirmed decimal int/long, including supported signed minima. Typed 0/1 retain the literal suffix.

**C 边界** Only unsuffixed int constants in the C11 guaranteed range. No unsigned promotion or floating point.

**实现对应** [Java 实现](../src/operators/java/word/constant/redundancy/constant_neutral_term_insertion.py)，[C 实现](../src/operators/c/word/constant/redundancy/constant_neutral_term_insertion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 7; }
```

**C 正例**

```c
int f(int a){return 7;}
```

### WC2 ConstantNeutralTermRemoval

**规律** inverse neutral constant rule。

**必要前提** Both operands are known same-type integer literals and one is the operator's identity.

**保持语义的推导** Removing the neutral operation preserves its typed constant value in every accepted expression context.

**Java 边界** Do not remove an int/long promotion. Constant expression status remains unchanged.

**C 边界** Only int literal plus/minus zero in an rvalue position.

**实现对应** [Java 实现](../src/operators/java/word/constant/redundancy/constant_neutral_term_removal.py)，[C 实现](../src/operators/c/word/constant/redundancy/constant_neutral_term_removal.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return (7 + 0); }
```

**C 正例**

```c
int f(int a){return 7+0;}
```

### WC3 IntegerAdditionDecomposition

**规律** v = a + b。

**必要前提** Both generated operands and their sum are representable in the original type.

**保持语义的推导** Exact typed addition reconstructs v. Parentheses preserve the surrounding expression tree.

**Java 边界** Both terms carry the original long suffix where needed. Negative minima are decomposed into representable negative terms.

**C 边界** Terms and sum remain within -32767..32767; no change to unsigned or implementation-selected literal types.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/integer_addition_decomposition.py)，[C 实现](../src/operators/c/word/constant/replacement/integer_addition_decomposition.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 7; }
```

**C 正例**

```c
int f(int a){return 32767;}
```

### WC4 BooleanNegationReplacement

**规律** boolean or int truth identity。

**必要前提** The source is a confirmed truth constant and logical negation has the same result type.

**保持语义的推导** Negating the opposite truth value reproduces the original value without reading state.

**Java 边界** true is !false and false is !true, all boolean constant expressions.

**C 边界** 0 is !1 and 1 is !0, all int. Removal accepts only fully constant logical expressions.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/boolean_negation_replacement.py)，[C 实现](../src/operators/c/word/constant/replacement/boolean_negation_replacement.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
boolean m(){ return true; }
```

**C 正例**

```c
int f(int a){return 1;}
```

### WC5 IntegerSubtractionRepresentation

**规律** v = a - b。

**必要前提** Generated operands and subtraction result are representable and retain the literal type.

**保持语义的推导** Exact subtraction reconstructs the same typed constant with no intermediate overflow.

**Java 边界** Reject offsets exceeding the int/long limit; preserve suffix and signed-minimum parsing.

**C 边界** At the upper guaranteed limit use (v-1)-(-1), otherwise (v+1)-1.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/integer_subtraction_representation.py)，[C 实现](../src/operators/c/word/constant/replacement/integer_subtraction_representation.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 7; }
```

**C 正例**

```c
int f(int a){return 32767;}
```

### SE1 OperandExchange

**规律** commutative typed operator。

**必要前提** Both operands are pure, local, initialized where required, and non-throwing. The operator is commutative in the confirmed type.

**保持语义的推导** Operand evaluation has no observable effects. Individually parenthesized operands retain their trees. Only their order is exchanged.

**Java 边界** Integral arithmetic, bitwise operations or equality. String, floating point, boxing and heap reads are excluded.

**C 边界** No reassociation. For every originally defined input, the same two values reach the same operation, with the same representability.

**实现对应** [Java 实现](../src/operators/java/statement/expression/reordering/operand_exchange.py)，[C 实现](../src/operators/c/statement/expression/reordering/operand_exchange.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ return a+b; }
```

**C 正例**

```c
int f(int a){return a+1;}
```

### SE2 ExpressionRedundantWrapping

**规律** E op identity = E。

**必要前提** The expression is a confirmed primitive integer rvalue, and the identity operation preserves promoted type.

**保持语义的推导** Evaluate E exactly once in its original context and apply a total identity operation.

**Java 边界** int/long only. Never rewrite declarations, assignment targets or update targets.

**C 边界** Ordinary int only. Address escape, volatile and unknown types are excluded.

**实现对应** [Java 实现](../src/operators/java/statement/expression/redundancy/expression_redundant_wrapping.py)，[C 实现](../src/operators/c/statement/expression/redundancy/expression_redundant_wrapping.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ return a; }
```

**C 正例**

```c
int f(int a){return a;}
```

### SE3 ExpressionRedundantUnwrapping

**规律** inverse expression identity。

**必要前提** The neutral operand is known and removing the operator preserves expression type and tree.

**保持语义的推导** The remaining expression is evaluated once at the same point with the same value.

**Java 边界** Require equality of original and remaining expression types to preserve narrowing and overload contexts.

**C 边界** Only pure int expressions plus/minus zero. Surrounding grouping is retained.

**实现对应** [Java 实现](../src/operators/java/statement/expression/redundancy/expression_redundant_unwrapping.py)，[C 实现](../src/operators/c/statement/expression/redundancy/expression_redundant_unwrapping.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ return (a+0); }
```

**C 正例**

```c
int f(int a){return a+0;}
```

### SE4 RelationalExpressionRewriting

**规律** a < b iff b > a。

**必要前提** Both operands are pure confirmed integral values. The relation is flipped when operands are exchanged.

**保持语义的推导** Typed integral comparison is symmetric under the corresponding reversed relation; no operand effects are reordered.

**Java 边界** Integral local bindings or supported literals, excluding floating point and boxed comparisons.

**C 边界** Only scalar int variables or literals, each independently parenthesized as needed.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/relational_expression_rewriting.py)，[C 实现](../src/operators/c/statement/expression/replacement/relational_expression_rewriting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
boolean m(int a,int b){ return a<b; }
```

**C 正例**

```c
int f(int a){return a<3;}
```

### SE5 IncrementDecrementRewriting

**规律** standalone update expansion。

**必要前提** The target is a plain local integral variable and the update expression's value is discarded.

**保持语义的推导** The old value is read once and the same successor value is written once. No prefix/postfix result is observed.

**Java 边界** int/long without final; wrapping behavior is the same for increment and addition.

**C 边界** int without qualifiers or escaped addresses; overflow exists in both forms on the same inputs.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/increment_decrement_rewriting.py)，[C 实现](../src/operators/c/statement/expression/replacement/increment_decrement_rewriting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ a++; return a; }
```

**C 正例**

```c
int f(int a){a++;return a;}
```

### SE6 CompoundAssignmentRewriting

**规律** compound assignment expansion。

**必要前提** A stable plain local target, pure integral RHS and no required implicit narrowing conversion.

**保持语义的推导** Both forms read the same old target and RHS and perform the same arithmetic and final write.

**Java 边界** int/long only; reject int with long RHS and discard assignment-expression values.

**C 边界** int +=, -= or *= only. No volatile, pointer dereference, fields or RHS writes.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/compound_assignment_rewriting.py)，[C 实现](../src/operators/c/statement/expression/replacement/compound_assignment_rewriting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ a+=b; return a; }
```

**C 正例**

```c
int f(int a){a+=2;return a;}
```

### SD1 DeclarationExchange

**规律** independent declaration commutation。

**必要前提** Read/write/declaration sets are independent, initializers have no observable effects and scope lookup cannot change.

**保持语义的推导** Each initializer sees the same environment, and the disjoint local updates commute.

**Java 边界** Check every crossed declaration, including final and multiple-declarator dependencies and exception freedom.

**C 边界** Adjacent simple int declarations with total initializers; reject either initializer mentioning either new binder.

**实现对应** [Java 实现](../src/operators/java/statement/declaration/reordering/declaration_exchange.py)，[C 实现](../src/operators/c/statement/declaration/reordering/declaration_exchange.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int a=1; int b=2; return a+b; }
```

**C 正例**

```c
int f(int a){int x=1;int y=2;return a+x+y;}
```

### SD2 RedundantDeclarationInsertion

**规律** fresh unused store。

**必要前提** The new local name is fresh and its initializer is a typed harmless literal at a reachable insertion point.

**保持语义的推导** Projecting away the new local gives exactly the old state and next original statement.

**Java 边界** Typed primitive or null initializers; avoid source names, captures and unreachable insertion sites.

**C 边界** Function entry, fresh int initialized to zero, no opaque control or type scopes.

**实现对应** [Java 实现](../src/operators/java/statement/declaration/redundancy/redundant_declaration_insertion.py)，[C 实现](../src/operators/c/statement/declaration/redundancy/redundant_declaration_insertion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 1; }
```

**C 正例**

```c
int f(int a){return a;}
```

### SD3 RedundantDeclarationRemoval

**规律** dead declaration elimination。

**必要前提** The binding has no live or captured references and initialization is total with no observable effects.

**保持语义的推导** The removed transition changes only an unobserved local. State projection is unchanged.

**Java 边界** Keep remaining declarators in original order; reject uncertain captures and exceptional initializers.

**C 边界** Unused plain int with a total initializer; reject volatile, address escape and opaque control flow.

**实现对应** [Java 实现](../src/operators/java/statement/declaration/redundancy/redundant_declaration_removal.py)，[C 实现](../src/operators/c/statement/declaration/redundancy/redundant_declaration_removal.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int a=1; return 2; }
```

**C 正例**

```c
int f(int a){int unused=1;return a;}
```

### SD4 DeclarationSplitting

**规律** declaration followed by initialization。

**必要前提** No final/const restriction, the type is explicit, lookup is unchanged and no code is inserted between the two parts.

**保持语义的推导** Declaration establishes the same binder and the next assignment evaluates the same initializer and stores the same value.

**Java 边界** Preserve declarator order and explicit array initializer construction; reject var and unsupported modifiers.

**C 边界** Single plain int declaration in a compound block, excluding loop heads, VLA and complex declarators.

**实现对应** [Java 实现](../src/operators/java/statement/declaration/replacement/declaration_splitting.py)，[C 实现](../src/operators/c/statement/declaration/replacement/declaration_splitting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int b=a+1; return b; }
```

**C 正例**

```c
int f(int a){int x=a+1;return x;}
```

### SD5 DeclarationMerging

**规律** initial assignment folded into declaration。

**必要前提** The first matching assignment targets the same binder, does not read its uninitialized value and crosses no dependency or effect.

**保持语义的推导** Initializer lookup and evaluation inputs are unchanged, yielding the same first store at the equivalent point.

**Java 边界** Nonadjacent mode additionally checks every crossed statement and all earlier uses.

**C 边界** Strictly adjacent uninitialized int declaration and pure plain assignment.

**实现对应** [Java 实现](../src/operators/java/statement/declaration/replacement/declaration_merging.py)，[C 实现](../src/operators/c/statement/declaration/replacement/declaration_merging.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int b; b=a+1; return b; }
```

**C 正例**

```c
int f(int a){int x;x=a+1;return x;}
```

### SS1 IndependentComputationExchange

**规律** independent transition commutation。

**必要前提** Pure local computations have disjoint write/read conflicts and no exceptions. Every crossed statement is also independent.

**保持语义的推导** Each transition reads identical inputs and their disjoint stores commute; the observable trace remains empty.

**Java 边界** Integral local assignments/updates only, with exception analysis and optional distance bounds.

**C 边界** Adjacent int plain assignments with read/write dependency checks.

**实现对应** [Java 实现](../src/operators/java/statement/ordinary_statement/reordering/independent_computation_exchange.py)，[C 实现](../src/operators/c/statement/ordinary_statement/reordering/independent_computation_exchange.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ a=a+1; b=b+2; return a+b; }
```

**C 正例**

```c
int f(int a){int x=0;int y=0;x=a+1;y=a+2;return x+y;}
```

### SS2 RedundantComputationInsertion

**规律** isolated dead computation。

**必要前提** All stores target fresh locals, inputs are initialized and operations cannot cause observable failures.

**保持语义的推导** The finite fragment is a sequence of silent steps whose state projection is identity.

**Java 边界** int/long updates wrap safely; historical primitive fragments are initialized with typed literals.

**C 边界** Only fixed small int literals and initialized isolated locals, avoiding signed overflow.

**实现对应** [Java 实现](../src/operators/java/statement/ordinary_statement/redundancy/redundant_computation_insertion.py)，[C 实现](../src/operators/c/statement/ordinary_statement/redundancy/redundant_computation_insertion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 1; }
```

**C 正例**

```c
int f(int a){return a;}
```

### SS3 RedundantComputationRemoval

**规律** dead computation slice elimination。

**必要前提** All uses of the removed local belong to the removed slice; computations are total and write no other binding.

**保持语义的推导** No surviving transition observes the slice's state and deleting silent total steps preserves the trace.

**Java 边界** Same-block assignments/updates with non-throwing integer expressions; reject escaping or captured uses.

**C 边界** Adjacent declaration and plain assignment, with totality checked for initializer and RHS.

**实现对应** [Java 实现](../src/operators/java/statement/ordinary_statement/redundancy/redundant_computation_removal.py)，[C 实现](../src/operators/c/statement/ordinary_statement/redundancy/redundant_computation_removal.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int a=0; a=a+1; return 2; }
```

**C 正例**

```c
int f(int a){int unused=0;unused=1+2;return a;}
```

### SS4 ComputationSplitting

**规律** subexpression let introduction。

**必要前提** The subexpression keeps its exact tree and type, is pure, and cannot be moved outside conditional protection or before required initialization.

**保持语义的推导** A fresh temporary stores precisely the value the original subtree would produce. Replacing that subtree with the value preserves its parent computation.

**Java 边界** Only total integral subexpressions; reject final/narrowing contexts and keep method-wide fresh names.

**C 边界** Extract only the unconditional left subtree of a non-short-circuit pure assignment, without reassociation.

**实现对应** [Java 实现](../src/operators/java/statement/ordinary_statement/replacement/computation_splitting.py)，[C 实现](../src/operators/c/statement/ordinary_statement/replacement/computation_splitting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ a=(a+1)*b; return a; }
```

**C 正例**

```c
int f(int a){a=(a+1)*2;return a;}
```

### SS5 ComputationMerging

**规律** single-use let elimination。

**必要前提** Exactly one resolved use, no capture, identical type and no input changes before the use. Evaluation remains safe at the destination.

**保持语义的推导** Substitution reproduces the initializer value once while removing only the unobservable temporary store.

**Java 边界** Require non-throwing integral initializer and pure target, and check all intervening writes and declarations.

**C 边界** Adjacent pure assignment only; reject substitution into short-circuit or conditional evaluation.

**实现对应** [Java 实现](../src/operators/java/statement/ordinary_statement/replacement/computation_merging.py)，[C 实现](../src/operators/c/statement/ordinary_statement/replacement/computation_merging.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ int temp=a+1; a=temp*b; return a; }
```

**C 正例**

```c
int f(int a){int tmp=a+1;a=tmp*2;return a;}
```

### CC1 IndependentCaseGroupPermutation

**规律** independent switch group permutation。

**必要前提** Whole label groups are distinct, retain order internally, have no fallthrough and expose no cross-group scope dependency.

**保持语义的推导** The selector reaches exactly the same labeled body, which executes the same statements and exit.

**Java 边界** Traditional colon labels only. Reject direct declarations, incomplete groups and unsupported rules.

**C 边界** Confirmed int selector and constant labels. Reject nested labels/switches, declarations and complex transfers.

**实现对应** [Java 实现](../src/operators/java/control/conditional/reordering/independent_case_group_permutation.py)，[C 实现](../src/operators/c/control/conditional/reordering/independent_case_group_permutation.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int x=0; switch(a){case 1: case 2:x=1;break;default:x=2;break;} return x; }
```

**C 正例**

```c
int f(int a){switch(a){case 0:case 1:a=2;break;default:a=3;break;}return a;}
```

### CC2 RedundantBranchInsertion

**规律** unreachable branch introduction。

**必要前提** The condition is a constant false (or true with a dead else) and generated declarations are fresh and valid.

**保持语义的推导** The branch body is never evaluated. Original state and next statement are unchanged.

**Java 边界** Use an if construct rather than unreachable while(false), preserving Java reachability rules.

**C 边界** Use if(0), independent of Java boolean literals.

**实现对应** [Java 实现](../src/operators/java/control/conditional/redundancy/redundant_branch_insertion.py)，[C 实现](../src/operators/c/control/conditional/redundancy/redundant_branch_insertion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 1; }
```

**C 正例**

```c
int f(int a){return a;}
```

### CC3 RedundantBranchRemoval

**规律** constant branch elimination。

**必要前提** Condition evaluation is total and constant. Removing the arm cannot invalidate scoping, checked exceptions or reachability.

**保持语义的推导** The live arm has the same trace. Where Java requires it, a constant-if shell retains compile-time completion facts.

**Java 边界** Reject possible checked-catch invalidation and preserve normal/abrupt completion of the original if.

**C 边界** Only provably false constant condition and safe structured function; keep the executable else inside its scope.

**实现对应** [Java 实现](../src/operators/java/control/conditional/redundancy/redundant_branch_removal.py)，[C 实现](../src/operators/c/control/conditional/redundancy/redundant_branch_removal.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ if(false){ int a=0; } return 1; }
```

**C 正例**

```c
int f(int a){if(0){a=2;}else{a=3;}return a;}
```

### CC4 IfToSwitchNesting

**规律** stable equality dispatch, shared body。

**必要前提** All tests compare one stable local integer selector to distinct representable constants; a new switch cannot capture transfers.

**保持语义的推导** Exactly the same first match is chosen. Grouped labels share the untouched branch body and exit it as the original chain did.

**Java 边界** Keep branch scopes verbatim; append break only on normally completing paths. Reject uninitialized method locals, patterns, captures and unsafe breaks.

**C 边界** Only local int equality/OR chains with confirmed constants; reject goto, labels and unsafe breaks.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/if_to_switch_nesting.py)，[C 实现](../src/operators/c/control/conditional/replacement/if_to_switch_nesting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int x=0; if(a==1){x=1;}else if(a==2){x=2;}else{x=3;} return x; }
```

**C 正例**

```c
int f(int a){if(a==0 || a==1){a=2;}else{a=3;}return a;}
```

### CC5 IfToSwitchCloning

**规律** stable equality dispatch, cloned body。

**必要前提** Same dispatch premises as CC4, and each copied body keeps an independent lexical scope.

**保持语义的推导** Distinct case labels select exactly one copy of the same original body, so no runtime work is duplicated.

**Java 边界** No source reindentation or brace stripping. Preserve abrupt completion and definite assignment.

**C 边界** All copied bodies remain in blocks, with no macro or opaque control context.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/if_to_switch_cloning.py)，[C 实现](../src/operators/c/control/conditional/replacement/if_to_switch_cloning.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int x=0; if(a==1){x=1;}else if(a==2){x=2;}else{x=3;} return x; }
```

**C 正例**

```c
int f(int a){if(a==0 || a==1){a=2;}else{a=3;}return a;}
```

### CC6 SwitchToIfNesting

**规律** switch fallthrough state simulation。

**必要前提** Evaluate selector once, preserve source group order, and reject unsupported transfers/declarations and assignment-flow uncertainty.

**保持语义的推导** The fresh active flag denotes that the original switch has entered a group and has not broken. Each following body executes iff the original would reach it.

**Java 边界** Only traditional int-family statement switches, initialized nonfinal locals, and a trailing return for nonvoid methods.

**C 边界** Plain int selector; only final direct switch break is stripped. Return terminates without a synthetic successor.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/switch_to_if_nesting.py)，[C 实现](../src/operators/c/control/conditional/replacement/switch_to_if_nesting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int x=0; switch(a){case 1:x=1;break;case 2:x=2;break;default:x=3;break;} return x; }
```

**C 正例**

```c
int f(int a){switch(a){case 0:a+=1;case 1:a+=2;break;default:a=3;}return a;}
```

### CC7 SwitchToIfCloning

**规律** switch path expansion。

**必要前提** Selector is evaluated once and each entry's fallthrough suffix is known, terminating at the same exit.

**保持语义的推导** An exclusive guard chooses one copied suffix, containing exactly the original sequence of bodies for that entry.

**Java 边界** Same checked scope and definite-assignment fragment as CC6; reject switch expressions and complex transfers.

**C 边界** Confirmed literal labels and complete groups, with no cross-group declarations or opaque jumps.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/switch_to_if_cloning.py)，[C 实现](../src/operators/c/control/conditional/replacement/switch_to_if_cloning.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ int x=0; switch(a){case 1:x=1;break;case 2:x=2;break;default:x=3;break;} return x; }
```

**C 正例**

```c
int f(int a){switch(a){case 0:a+=1;case 1:a+=2;break;default:a=3;}return a;}
```

### CC8 ConditionalNesting

**规律** conjunction nesting。

**必要前提** No else, original condition order retained and no unsupported flow-scoped declarations.

**保持语义的推导** Evaluate a once. Evaluate b iff a is true. Enter the original body iff both succeed.

**Java 边界** Reject instanceof/record pattern bindings; side effects in ordinary conditions retain short-circuit order.

**C 边界** Only confirmed pure int conditions in a safe structured function.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/conditional_nesting.py)，[C 实现](../src/operators/c/control/conditional/replacement/conditional_nesting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ if(a>0 && b>0){a=1;} return a; }
```

**C 正例**

```c
int f(int a){if(a>0 && a<3){a=2;}return a;}
```

### CC9 ConditionalFlattening

**规律** nested conjunction flattening。

**必要前提** Each removed level has no else and no intervening statements/declarations. Operand order and grouping are retained.

**保持语义的推导** The short-circuit conjunction takes exactly the same tests and reaches the same final body.

**Java 边界** Keep an inner if/else intact rather than dropping it; reject flow patterns.

**C 边界** Exactly two nested ifs, pure confirmed conditions and intact final body.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/conditional_flattening.py)，[C 实现](../src/operators/c/control/conditional/replacement/conditional_flattening.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){ if(a>0){ if(b>0){a=1;} } return a; }
```

**C 正例**

```c
int f(int a){if(a>0){if(a<3){a=2;}}return a;}
```

### CC10 ConditionInversionAndBranchExchange

**规律** condition complement and arm exchange。

**必要前提** A complete if/else, one evaluation of the same condition and no unsupported flow-scoped bindings.

**保持语义的推导** Complementing truth and exchanging arms selects the identical original body with identical condition effects.

**Java 边界** Preserve each arm as a block; reject pattern scoping that depends on condition polarity.

**C 边界** Pure confirmed int condition, with C logical negation and unchanged arm scopes.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/condition_inversion_and_branch_exchange.py)，[C 实现](../src/operators/c/control/conditional/replacement/condition_inversion_and_branch_exchange.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){ if(a>0){a=1;}else{a=2;} return a; }
```

**C 正例**

```c
int f(int a){if(a>0){a=2;}else{a=3;}return a;}
```

### CL1 RedundantLoopInsertion

**规律** zero-iteration loop introduction。

**必要前提** Fresh initialized nonfinal local false flag, finite harmless initialization and no name capture.

**保持语义的推导** The first test is false, so no body/update executes. Discarding the fresh state restores the old state.

**Java 边界** A local boolean avoids Java compile-time unreachable-body restrictions.

**C 边界** A fresh int initialized to zero, with no macro or unsafe control context.

**实现对应** [Java 实现](../src/operators/java/control/loop/redundancy/redundant_loop_insertion.py)，[C 实现](../src/operators/c/control/loop/redundancy/redundant_loop_insertion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ return 1; }
```

**C 正例**

```c
int f(int a){return a;}
```

### CL2 RedundantLoopRemoval

**规律** zero-iteration loop elimination。

**必要前提** First condition is provably false, evaluation is total, and any removed initialization has no external effect.

**保持语义的推导** The original executes no body/update. Removing silent initialization/test steps preserves external state and trace.

**Java 边界** Track unchanged local definitions and preserve checked-catch validity; for init must be isolated.

**C 边界** No for initializer; accept a constant zero condition or an immediate unused zero-valued local flag.

**实现对应** [Java 实现](../src/operators/java/control/loop/redundancy/redundant_loop_removal.py)，[C 实现](../src/operators/c/control/loop/redundancy/redundant_loop_removal.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ {boolean flag=false; while(flag){int a=0;}} return 1; }
```

**C 正例**

```c
int f(int a){while(0){a++;}return a;}
```

### CL3 ForToWhile

**规律** for to while phase simulation。

**必要前提** Preserve init/test/body/update phases and lexical scopes; continue must reach update and break/return must skip it.

**保持语义的推导** One original iteration corresponds to test, body exit, update and next test. Redirect only continues targeting this loop.

**Java 边界** Exit the body through a fresh label before the update, so finally runs before update. Keep the original body nested.

**C 边界** No goto/labels/VLA. Insert update before targeted continue, excluding name capture by nested declarations.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/for_to_while.py)，[C 实现](../src/operators/c/control/loop/replacement/for_to_while.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; for(int i=0;i<3;i++){x=x+1;} return x; }
```

**C 正例**

```c
int f(int a){for(int i=0;i<3;i++){if(i==1)continue;a++;}return a;}
```

### CL4 WhileToFor

**规律** while to empty-init/update for。

**必要前提** Identical test and body, unchanged transfer targets and lexical scope.

**保持语义的推导** Both loops alternate the same test and body. Empty initializer/update add no state changes.

**Java 边界** Reject labels, capture and pattern scope uncertainty. Keep body bytes intact.

**C 边界** Safe structured function, preserving original condition and body.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/while_to_for.py)，[C 实现](../src/operators/c/control/loop/replacement/while_to_for.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; while(x<3){x=x+1;} return x; }
```

**C 正例**

```c
int f(int a){int i=0;while(i<3){i++;if(i==2)continue;a++;}return a;}
```

### CL5 ForToDoWhile

**规律** for to guarded do phase simulation。

**必要前提** Same phases and transfer premises as CL3. The guard must preserve zero iterations and compiler completion facts.

**保持语义的推导** Evaluate the first test in the guard, then body/update/test repeatedly. No extra test is evaluated between guard and first body.

**Java 边界** Constant true omits the guard. Reject uncertain return reachability and unreachable trailing condition.

**C 边界** Preserve update before targeted continue and reject name capture; no labels/goto/VLA.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/for_to_do_while.py)，[C 实现](../src/operators/c/control/loop/replacement/for_to_do_while.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; for(int i=0;i<3;i++){x=x+1;} return x; }
```

**C 正例**

```c
int f(int a){for(int i=0;i<3;i++){if(i==1)continue;a++;}return a;}
```

### CL6 DoWhileToFor

**规律** do to for phase simulation。

**必要前提** Preserve the unconditional first body, later condition tests and all transfer targets.

**保持语义的推导** An unconditional for with a body-exit label and trailing condition in Java, or a first-iteration flag in C, simulates each original do iteration.

**Java 边界** Reuse the checked post-test construction and its completion/checked-exception restrictions.

**C 边界** Use a constant for header. The first flag is cleared by the update, including continue, before the next guarded condition test.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/do_while_to_for.py)，[C 实现](../src/operators/c/control/loop/replacement/do_while_to_for.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; do{x=x+1;}while(x<3); return x; }
```

**C 正例**

```c
int f(int a){int i=0;do{i++;if(i==2)continue;a++;}while(i<3);return a;}
```

### CL7 DoWhileToWhile

**规律** do to while phase simulation。

**必要前提** First body must execute unconditionally. A targeted continue must evaluate the condition after finalization.

**保持语义的推导** Java's body-exit label or C's first flag gives one unconditional iteration, then exactly one original condition test per ordinary/continue exit.

**Java 边界** Keep constant-loop reachability, finally overrides and checked catches. First-flag option has stricter definite-assignment premises.

**C 边界** A constant header avoids new C11 forward-progress assumptions. The flag is cleared at body entry; the next guarded test evaluates the original condition.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/do_while_to_while.py)，[C 实现](../src/operators/c/control/loop/replacement/do_while_to_while.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; do{x=x+1;}while(x<3); return x; }
```

**C 正例**

```c
int f(int a){int i=0;do{i++;if(i==2)continue;a++;}while(i<3);return a;}
```

### CL8 WhileToDoWhile

**规律** while to guarded do phase simulation。

**必要前提** Original condition is evaluated once before the first body, once after each ordinary/continue exit, and never after break/return.

**保持语义的推导** The outer guard covers zero iterations, then the do repeats the same test/body trace. A constant true specialization keeps infinite-loop completion.

**Java 边界** Preserve labels, Java reachability and pattern restrictions. Alternative condition-at-start mode has the same trace.

**C 边界** Keep the guard and original body in a block and reject labels/goto/VLA.

**实现对应** [Java 实现](../src/operators/java/control/loop/replacement/while_to_do_while.py)，[C 实现](../src/operators/c/control/loop/replacement/while_to_do_while.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){ int x=0; while(x<3){x=x+1;} return x; }
```

**C 正例**

```c
int f(int a){int i=0;while(i<3){i++;if(i==2)continue;a++;}return a;}
```

### WC6 IntegerAdditionComposition

**规律** typed literal addition folding。

**必要前提** Both operands are same-type integer literals; exact sum is representable.

**保持语义的推导** Exact addition reconstructs the same constant and static type.

**Java 边界** int/long suffixes must match; no overflow folding.

**C 边界** Guaranteed-range int literals only; no unsigned promotions.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/integer_addition_composition.py)，[C 实现](../src/operators/c/word/constant/replacement/integer_addition_composition.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){return 3+4;}
```

**C 正例**

```c
int f(int a){return 3+4;}
```

### WC7 IntegerSubtractionComposition

**规律** typed literal subtraction folding。

**必要前提** Both operands are same-type integer literals; exact difference is representable.

**保持语义的推导** Exact subtraction reconstructs the same constant and static type.

**Java 边界** int/long suffixes must match; signed minima are explicitly represented.

**C 边界** Guaranteed-range int literals only.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/integer_subtraction_composition.py)，[C 实现](../src/operators/c/word/constant/replacement/integer_subtraction_composition.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(){return 8-1;}
```

**C 正例**

```c
int f(int a){return 8-1;}
```

### WC8 BooleanNegationConstantReduction

**规律** constant truth negation reduction。

**必要前提** Negated operand is a literal truth constant, not a mutable or boxed value.

**保持语义的推导** Logical negation returns the opposite literal with no effects.

**Java 边界** Only primitive true/false under !.

**C 边界** Only !0 or !1 at a supported int rvalue position.

**实现对应** [Java 实现](../src/operators/java/word/constant/replacement/boolean_negation_constant_reduction.py)，[C 实现](../src/operators/c/word/constant/replacement/boolean_negation_constant_reduction.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
boolean m(){return !false;}
```

**C 正例**

```c
int f(int a){return !0;}
```

### SE7 IncrementDecrementContraction

**规律** unit assignment contraction。

**必要前提** Standalone assignment to stable local int state; original unit computation has the same type.

**保持语义的推导** Both forms read and write the same value; discarded result does not change observations.

**Java 边界** Non-final int/long; reject narrowing and non-unit expressions.

**C 边界** Initialized non-escaped ordinary int; exclude volatile and observed update values.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/increment_decrement_contraction.py)，[C 实现](../src/operators/c/statement/expression/replacement/increment_decrement_contraction.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){a=a+1;return a;}
```

**C 正例**

```c
int f(int a){a=a+1;return a;}
```

### SE8 CompoundAssignmentContraction

**规律** compound assignment contraction。

**必要前提** Standalone x=x op E with identical target binding, pure RHS and matching type.

**保持语义的推导** The same old value and E reach the same operation and store.

**Java 边界** int/long only, no implicit narrowing differences.

**C 边界** Initialized ordinary int, +=/-=/*= only; no pointers or qualifiers.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/compound_assignment_contraction.py)，[C 实现](../src/operators/c/statement/expression/replacement/compound_assignment_contraction.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a,int b){a=a+b;return a;}
```

**C 正例**

```c
int f(int a){int b=2;a=a+b;return a;}
```

### SE9 DeMorganExpansion

**规律** ordered De Morgan expansion。

**必要前提** Negated &&/|| expression has confirmed logical operand types and pure operands.

**保持语义的推导** Truth table and left-to-right short circuit select the same operands in the same order.

**Java 边界** Primitive boolean only; reject boxed and flow-scoped pattern operands.

**C 边界** Ordinary int truth; logical operators continue to return int 0/1.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/de_morgan_expansion.py)，[C 实现](../src/operators/c/statement/expression/replacement/de_morgan_expansion.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
boolean m(int a,int b){return !(a>0 && b>0);}
```

**C 正例**

```c
int f(int a){return !(a>0 && a<3);}
```

### SE10 DeMorganContraction

**规律** ordered De Morgan contraction。

**必要前提** Both operands are explicit negations under &&/|| with confirmed logical types.

**保持语义的推导** The dual logical operation under one negation preserves the original short circuit trace.

**Java 边界** Primitive boolean only.

**C 边界** Ordinary int truth; do not substitute bitwise operators.

**实现对应** [Java 实现](../src/operators/java/statement/expression/replacement/de_morgan_contraction.py)，[C 实现](../src/operators/c/statement/expression/replacement/de_morgan_contraction.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
boolean m(int a,int b){return !(a>0) || !(b>0);}
```

**C 正例**

```c
int f(int a){return !(a>0) || !(a<3);}
```

### CC11 ConditionalExpressionToIf

**规律** conditional assignment expansion。

**必要前提** Stable local target; condition typed and pure; branches have identical target type.

**保持语义的推导** Evaluate condition once and precisely one RHS, then store in the same binding.

**Java 边界** int/long exact branch types, no boxing or declaration conversion.

**C 边界** Pure int branches, ordinary target; exclude goto/labels/VLA.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/conditional_expression_to_if.py)，[C 实现](../src/operators/c/control/conditional/replacement/conditional_expression_to_if.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){int x=0;x=a>0 ? a : 0;return x;}
```

**C 正例**

```c
int f(int a){int x=0;x=a>0 ? a : 0;return x;}
```

### CC12 IfToConditionalExpression

**规律** conditional assignment contraction。

**必要前提** Both complete branches consist of one plain assignment to the same binding.

**保持语义的推导** Exactly one RHS is evaluated after the original condition, with the same final store.

**Java 边界** Exact int/long branch types; non-final target.

**C 边界** Ordinary int; no qualifiers or escaped addresses.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/if_to_conditional_expression.py)，[C 实现](../src/operators/c/control/conditional/replacement/if_to_conditional_expression.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){int x=0;if(a>0){x=a;}else{x=0;}return x;}
```

**C 正例**

```c
int f(int a){int x=0;if(a>0){x=a;}else{x=0;}return x;}
```

### CC13 DisjunctionBranchSplitting

**规律** short-circuit disjunction branch splitting。

**必要前提** No else; typed pure conditions; branch has no declarations or flow-scoped names.

**保持语义的推导** P true runs B once; otherwise Q is evaluated and may run B once.

**Java 边界** Reject pattern scopes and local declarations before cloning.

**C 边界** Reject opaque scopes, goto and labels; preserve truth conversion.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/disjunction_branch_splitting.py)，[C 实现](../src/operators/c/control/conditional/replacement/disjunction_branch_splitting.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){int x=0;if(a>0 || a < -1){x=3;}return x;}
```

**C 正例**

```c
int f(int a){int x=0;if(a>0 || a < -1){x=3;}return x;}
```

### CC14 DisjunctionBranchMerging

**规律** short-circuit disjunction branch merging。

**必要前提** Exact else-if without final else, identical scoped bodies and pure typed conditions.

**保持语义的推导** P is tested first; Q only on false; selected identical B executes once.

**Java 边界** No declarations or flow-scoped names in either body.

**C 边界** Ordinary int conditions, no scope-sensitive body declarations.

**实现对应** [Java 实现](../src/operators/java/control/conditional/replacement/disjunction_branch_merging.py)，[C 实现](../src/operators/c/control/conditional/replacement/disjunction_branch_merging.py)。每个实现的 `analyze_site` 检查本项前提，共同分析由上一节的共享工具提供。

**Java 正例**

```java
int m(int a){int x=0;if(a>0){x=3;}else if(a < -1){x=3;}return x;}
```

**C 正例**

```c
int f(int a){int x=0;if(a>0){x=3;}else if(a < -1){x=3;}return x;}
```

## 5. 验证与尚未完成的证明

全部 102 个实现均保留实际修改代码的正例，并分别有拒绝范围外输入的测试。部分拒绝案例是语法、类型或目标范围不适用的输入，不能统一解释为所有潜在危险模式都已覆盖。重复应用、种子、中文源码与兼容路径继续运行原有回归。

新增 `src/tests/test_semantic_contracts.py` 按共同证明义务组织检查，覆盖构造函数和 lambda 的绑定边界、C 函数名与参数名相同、所有规则的翻译阶段边界、临时名批量冲突、隐式拆箱异常、装箱 final 的常量误判、Java 确定赋值、受检异常、标识符拼写等价，以及 for 更新和 finally 的顺序。补充短路提取与常量 if 分派的确定赋值反例，C do 转换在常量循环头下验证不终止场景。C SE1 通过 56 个表达式形状、两种位置选择和两种强度组合生成 224 个变体，并在 27 个不同参数组合上检查 6048 次结果，启用 UBSan。这个有限矩阵用于检查实现，不是交换律的证明本身。


新增 WC6—WC8、SE7—SE10、CC11—CC14 的类型、短路、往返和入口验证见 [双向策略说明](sct_bidirectional.md)。反向关系是结构上的对应，不承诺所有生成结果都在反向策略接受范围内，也不提供逐字源码撤销。

尚未完成的工作包括由证明助手验证语义规则、证明分析器实现与契约一致，以及在完整编译上下文中穷尽 Java/C 语言特性。本项目当前交付是有明确前提、实现检查和回归证据的保守策略库，不能标记为全语言、任意程序上的形式化等价保证。
