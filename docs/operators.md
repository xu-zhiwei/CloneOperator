# Paper operator inventory

Use `sct.create_operator` with the paper ID. `operators.create_strategy` and the historical implementation documents use the implementation ID.

| Paper ID | Operator | Level | Target | Category | Counterpart | Scaling | Implementation ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WI1 | Identifier renaming | Word | Identifiers | Replacement | WI1 | Revisit | WI1 |
| WC1 | Neutral term insertion | Word | Constants | Redundancy | WC2 | Growth | WC1 |
| WC2 | Neutral term removal | Word | Constants | Redundancy | WC1 | Limited | WC2 |
| WC3 | Addition decomposition | Word | Constants | Replacement | WC4 | Limited | WC3 |
| WC4 | Addition composition | Word | Constants | Replacement | WC3 | Limited | WC6 |
| WC5 | Boolean negation | Word | Constants | Replacement | WC6 | Growth | WC4 |
| WC6 | Negation constant reduction | Word | Constants | Replacement | WC5 | Limited | WC8 |
| WC7 | Subtraction representation | Word | Constants | Replacement | WC8 | Growth | WC5 |
| WC8 | Subtraction composition | Word | Constants | Replacement | WC7 | Limited | WC7 |
| SE1 | Operand exchange | Statement | Expressions | Reordering | SE1 | Revisit | SE1 |
| SE2 | Redundant wrapping | Statement | Expressions | Redundancy | SE3 | Growth | SE2 |
| SE3 | Redundant unwrapping | Statement | Expressions | Redundancy | SE2 | Limited | SE3 |
| SE4 | Relational rewriting | Statement | Expressions | Replacement | SE4 | Revisit | SE4 |
| SE5 | Increment/decrement expansion | Statement | Expressions | Replacement | SE6 | Limited | SE5 |
| SE6 | Increment/decrement contraction | Statement | Expressions | Replacement | SE5 | Limited | SE7 |
| SE7 | Compound assignment expansion | Statement | Expressions | Replacement | SE8 | Limited | SE6 |
| SE8 | Compound assignment contraction | Statement | Expressions | Replacement | SE7 | Limited | SE8 |
| SE9 | De Morgan expansion | Statement | Expressions | Replacement | SE10 | Limited | SE9 |
| SE10 | De Morgan contraction | Statement | Expressions | Replacement | SE9 | Limited | SE10 |
| SD1 | Declaration exchange | Statement | Declarations | Reordering | SD1 | Revisit | SD1 |
| SD2 | Declaration insertion | Statement | Declarations | Redundancy | SD3 | Growth | SD2 |
| SD3 | Declaration removal | Statement | Declarations | Redundancy | SD2 | Limited | SD3 |
| SD4 | Declaration splitting | Statement | Declarations | Replacement | SD5 | Limited | SD4 |
| SD5 | Declaration merging | Statement | Declarations | Replacement | SD4 | Limited | SD5 |
| SS1 | Computation exchange | Statement | Ordinary statements | Reordering | SS1 | Revisit | SS1 |
| SS2 | Computation insertion | Statement | Ordinary statements | Redundancy | SS3 | Growth | SS2 |
| SS3 | Computation removal | Statement | Ordinary statements | Redundancy | SS2 | Limited | SS3 |
| SS4 | Computation splitting | Statement | Ordinary statements | Replacement | SS5 | Limited | SS4 |
| SS5 | Computation merging | Statement | Ordinary statements | Replacement | SS4 | Limited | SS5 |
| CC1 | Case group permutation | Control | Conditionals | Reordering | CC1 | Revisit | CC1 |
| CC2 | Branch insertion | Control | Conditionals | Redundancy | CC3 | Growth | CC2 |
| CC3 | Branch removal | Control | Conditionals | Redundancy | CC2 | Limited | CC3 |
| CC4 | if to switch (nesting) | Control | Conditionals | Replacement | CC5 | Limited | CC4 |
| CC5 | switch to if (nesting) | Control | Conditionals | Replacement | CC4 | Limited | CC6 |
| CC6 | if to switch (cloning) | Control | Conditionals | Replacement | CC7 | Limited | CC5 |
| CC7 | switch to if (cloning) | Control | Conditionals | Replacement | CC6 | Limited | CC7 |
| CC8 | Conditional nesting | Control | Conditionals | Replacement | CC9 | Limited | CC8 |
| CC9 | Conditional flattening | Control | Conditionals | Replacement | CC8 | Limited | CC9 |
| CC10 | Condition inversion and branch exchange | Control | Conditionals | Replacement | CC10 | Revisit | CC10 |
| CC11 | Conditional expression to if | Control | Conditionals | Replacement | CC12 | Limited | CC11 |
| CC12 | if to conditional expression | Control | Conditionals | Replacement | CC11 | Limited | CC12 |
| CC13 | Disjunction branch splitting | Control | Conditionals | Replacement | CC14 | Limited | CC13 |
| CC14 | Disjunction branch merging | Control | Conditionals | Replacement | CC13 | Limited | CC14 |
| CL1 | Loop insertion | Control | Loops | Redundancy | CL2 | Growth | CL1 |
| CL2 | Loop removal | Control | Loops | Redundancy | CL1 | Limited | CL2 |
| CL3 | for to while | Control | Loops | Replacement | CL4 | Limited | CL3 |
| CL4 | while to for | Control | Loops | Replacement | CL3 | Limited | CL4 |
| CL5 | for to do-while | Control | Loops | Replacement | CL6 | Limited | CL5 |
| CL6 | do-while to for | Control | Loops | Replacement | CL5 | Limited | CL6 |
| CL7 | do-while to while | Control | Loops | Replacement | CL8 | Limited | CL7 |
| CL8 | while to do-while | Control | Loops | Replacement | CL7 | Limited | CL8 |
