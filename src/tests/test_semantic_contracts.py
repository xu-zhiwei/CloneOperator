"""Contracts, adversarial semantic cases and systematically generated expressions."""
from itertools import product
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operators import create_strategy, get_registry
from operators.base.contracts import _RULES
from audit_semantics_counterexamples import audit, compile_run
from test_sct import JAVA_COMPILER


class ContractTests(unittest.TestCase):
    def test_each_of_eighty_implementations_has_a_distinct_conditional_contract(self):
        for language in ("java", "c"):
            self.assertEqual(set(_RULES), set(get_registry(language)))
            for sid in get_registry(language):
                contract = create_strategy(sid, language=language).semantic_contract
                self.assertEqual(contract.strategy_id, sid)
                self.assertEqual(contract.proof_status, "conditional_argument_not_machine_verified")
                for field in ("law", "premises", "argument", "java", "c"):
                    self.assertTrue(getattr(contract, field).strip())

    def test_all_eighty_rules_reject_their_out_of_fragment_cases(self):
        from sct_cases import REJECTIONS as JAVA
        from c_sct_cases import REJECTIONS as C
        cases = dict(JAVA)
        cases.update({
            "WI1": "int m(int a){class L{int get(){return a;}}return new L().get();}",
            "WC1": "int m(){return 077;}", "WC3": "int m(){return 077;}",
            "WC4": "class T{boolean field=true;}",
            "SE1": "String m(String a){return a+1;}",
            "SD1": "int m(){int a=1;int b=a+1;return b;}",
            "SD2": "abstract class T{abstract int m();}",
            "SS2": "abstract class T{abstract int m();}",
            "CC4": "int m(double a){if(a==1.0)return 1;return 2;}",
            "CC5": "int m(double a){if(a==1.0)return 1;return 2;}",
            "CC6": "int m(Integer a){switch(a){case 1:return 1;default:return 2;}}",
            "CC7": "int m(Integer a){switch(a){case 1:return 1;default:return 2;}}",
            "CL3": "int m(){outer:for(;;){break outer;}return 1;}",
            "CL4": "int m(){outer:while(true){break outer;}return 1;}",
            "CL5": "int m(){outer:for(;;){break outer;}return 1;}",
            "CL6": "int m(){outer:do{break outer;}while(true);return 1;}",
        })
        self.assertEqual(len(cases), 51)
        for language, examples in (("java", cases), ("c", C)):
            self.assertEqual(set(examples), set(get_registry(language)))
            for sid, code in examples.items():
                with self.subTest(language=language, sid=sid):
                    result = create_strategy(sid, language=language).apply(code,3)
                    self.assertEqual(result.code, code, result)
                    self.assertEqual(result.successful, 0, result)

    def test_nested_java_owners_do_not_supply_phantom_bindings(self):
        from operators.java.analysis.semantic import SemanticContext
        for declaration in ("class L {L(int x){}}", "java.util.function.IntConsumer c=(int x)->{};",
                            "class L {{int x=0;}}", "class L {int m(int x){return x;}}"):
            code = 'class T{String x="v";String m(){' + declaration + 'return x+1;}}'
            op = create_strategy("SE1")
            context = SemanticContext(code, op.parser)
            refs = [n for n in context.nodes if n.type == "identifier" and context.text(n) == "x"
                    and n.start_byte > code.index("return x+1")]
            self.assertTrue(refs)
            self.assertTrue(all(context.resolve(n) is None for n in refs))
            self.assertEqual(op(code), code)

    def test_translation_phases_are_rejected_by_every_rule(self):
        from sct_cases import CASES as JAVA
        from c_sct_cases import CASES as C
        for sid, code in JAVA.items():
            wrapped = '// literal Unicode translation marker \\u000a\n' + code
            self.assertEqual(create_strategy(sid)(wrapped), wrapped)
            invisible = '/* ignored identifier character ' + chr(0x200c) + ' */' + code
            self.assertEqual(create_strategy(sid)(invisible), invisible)
        for sid, code in C.items():
            for prefix in ('/* ??/ */\n', '/* splice \\\n */\n', 'int line = __LINE__;\n', '/* \\u00e9 */\n', '/* \\U000000e9 */\n', '/* <: */\n', '/* cr ' + chr(92) + chr(13) + ' */\n'):
                wrapped = prefix + code
                self.assertEqual(create_strategy(sid, language="c")(wrapped), wrapped)

    def test_c_function_declarator_is_not_renamed_as_parameter(self):
        code = 'int f(int f){return f+1;} int main(void){return f(1)!=2;}'
        result = create_strategy("WI1", language="c")(code)
        self.assertIn("int f(int sctName", result)
        self.assertIn("return f(1)", result)

    def test_compatibility_uses_the_checked_rules(self):
        from operators import ConditionReplace, LoopReplace, RedundantConstantInsert
        unsafe = 'int m(int a){while(a>0){if(a==1)break;a--;}return a;}'
        self.assertEqual(ConditionReplace(mode="if_to_switch_nesting")(unsafe), unsafe)
        floating = 'double m(){return -0.0;}'
        self.assertEqual(RedundantConstantInsert(token_vocab=set(), factor=7)(floating), floating)
        original = 'int m(){int x=0;for(int i=0;i<3;i++){try{continue;}finally{x++;}}return x;}'
        transformed = LoopReplace(mode="for_to_while")(original)
        self.assertNotEqual(original, transformed)
        self.assertIn("break sctBody", transformed)

    def test_scope_changing_batch_reparses_for_fresh_names(self):
        code = 'int m(int a){int x=(a+1)*2;int y=(a+2)*3;return x+y;}'
        op = create_strategy("SS4", selection="first")
        output = op.transform_disjoint(code, limit=2)
        self.assertIn("sctTemp0", output)
        self.assertIn("sctTemp1", output)

    def test_switch_conversion_rejects_unproved_definite_assignment(self):
        for sid in ("CC6", "CC7"):
            source = 'int m(int a){int x;switch(a){case 1:x=1;break;default:x=2;break;}return x;}'
            self.assertEqual(create_strategy(sid)(source), source)


@unittest.skipUnless(JAVA_COMPILER and shutil.which("gcc"), "Existing Java compiler module and GCC required")
class SemanticBehaviorTests(unittest.TestCase):
    def test_four_historical_failures_are_repaired(self):
        report = audit()
        self.assertTrue(all(c["repaired"] for c in report["cases"]))

    def compare_java_methods(self, scenarios):
        original, changed, calls = [], [], []
        for i, (sid, method, options) in enumerate(scenarios):
            op = create_strategy(sid, **options)
            result = op.apply(method)
            self.assertEqual(result.successful, 1, (sid, method, result))
            for target, code in ((original, method), (changed, result.code)):
                target.append(code.replace(' m(', f' m{i}(', 1))
            for value in (-2, 0, 1, 3):
                calls.append(f'try {{System.out.println(new T().m{i}({value}));}}catch(Throwable e){{System.out.println(e.getClass().getName());}}')
        main = ' public static void main(String[] args){' + ''.join(calls) + '}'
        with tempfile.TemporaryDirectory() as directory:
            before = compile_run('public class T{' + '\n'.join(original) + main + '}', 'java', Path(directory)/'before')
            after = compile_run('public class T{' + '\n'.join(changed) + main + '}', 'java', Path(directory)/'after')
        for run in (before, after):
            self.assertEqual(run['compile']['returncode'], 0, run['compile']['stderr'])
            self.assertEqual(run['run']['returncode'], 0, run)
        self.assertEqual(before['run']['stdout'], after['run']['stdout'])

    def test_java_control_completion_scopes_and_finally(self):
        scenarios = []
        for sid in ('CC4', 'CC5'):
            for method in (
                'int m(int a){if(a==1){return 7;}else{return 8;}}',
                'int m(int a){int x=0;if(a==1){int b=2;x=b;}else if(a==2){int b=3;x=b;}return x;}',
                'int m(int a){int x=0;if(a==1||a==2)x=7;else x=8;return x;}',
            ):
                scenarios.append((sid, method, {}))
        for sid in ('CC6', 'CC7'):
            scenarios.append((sid, 'int m(int a){int x=0;switch(a){case 1:x++;default:x+=2;case 2:x+=3;break;case 3:return 9;}return x;}', {}))
        for sid in ('CL3', 'CL5'):
            for method in (
                'int m(int a){int x=0;for(int i=0;i<3;x+=10,i++){try{if(i<2)continue;x++;}finally{x+=2;}}return x;}',
                'int m(int a){int x=0;for(int i=0;i<3;i++){try{continue;}finally{if(i==1)break;x++;}}return x;}',
                'int m(int a){int x=0;int i=0;for(x=1,i=0;i<3;x++,i++){x+=2;}return x;}',
                'int m(int a){int x=0;for(int i=0;i<3;i++){for(int j=0;j<2;j++){continue;}x++;}return x;}',
            ):
                scenarios.append((sid, method, {'selection':'first'}))
        for sid in ('CL6', 'CL7'):
            scenarios.append((sid, 'int m(int a){int x=0;do{try{x++;continue;}finally{if(x==2)break;}}while(x<3);return x;}', {}))
        for method in (
            'int m(int a){if(true){return 1;}return 2;}',
            'int m(int a){if(!false){return 1;}else{return 2;}}',
            'int m(int a){if(true){return 1;}else{a++;}return a;}',
            'int m(int a){if(false){a++;}else{return 2;}return a;}',
        ):
            scenarios.append(('CC3', method, {}))
        scenarios.append(('SS1', 'int m(int a){Integer b=null;int x=0;try{x=b;a++;}catch(NullPointerException e){return a;}return x+a;}', {}))
        # This case must be refused, since unboxing can throw before a changes.
        last = scenarios.pop()
        self.assertEqual(create_strategy(last[0])(last[1]), last[1])
        self.compare_java_methods(scenarios)

    def test_boxed_final_is_not_a_java_compile_time_constant(self):
        from operators.java.analysis.semantic import SemanticContext
        source = 'int m(){final Boolean flag=true;do{}while(flag);return 1;}'
        op = create_strategy('CL7')
        context = SemanticContext(source,op.parser)
        flag = next(n for n in context.nodes if n.type=='do_statement').child_by_field_name('condition')
        self.assertIsNone(context.constant_value(flag))
        for sid in ('CL7','CL8'):
            code = source if sid=='CL7' else source.replace('do{}while(flag);','while(flag){}')
            changed=create_strategy(sid)(code)
            # Compile-only, because both programs deliberately do not terminate.
            with tempfile.TemporaryDirectory() as directory:
                for i,method in enumerate((code,changed)):
                    path=Path(directory)/'T.java'
                    path.write_text('class T{'+method+'}')
                    compiled=subprocess.run(JAVA_COMPILER+[str(path)],capture_output=True,text=True,timeout=20)
                    self.assertEqual(compiled.returncode,0,compiled.stderr)

    def test_unboxing_and_generated_name_collision_compile_and_run(self):
        from types import SimpleNamespace
        cases = []
        method = 'int m(){Integer b=null;int x=0;int a=0;try{x=b;a++;}catch(NullPointerException e){return a;}return x+a;}'
        cases.append((method, create_strategy('SS1')(method)))
        method = 'int m(){return 7;}'
        op = create_strategy('CL1', modes=('while',))
        op.sampler = SimpleNamespace(sample=lambda *args: ('int','active0','0'))
        cases.append((method,op(method)))
        for original, transformed in cases:
            with tempfile.TemporaryDirectory() as directory:
                outputs = []
                for i, code in enumerate((original,transformed)):
                    program = 'public class T{' + code + 'public static void main(String[] a){System.out.print(new T().m());}}'
                    result = compile_run(program,'java',Path(directory)/str(i))
                    self.assertEqual(result['compile']['returncode'],0,result)
                    self.assertEqual(result['run']['returncode'],0,result)
                    outputs.append(result['run']['stdout'])
                self.assertEqual(*outputs)

    def test_extraction_preserves_guard_dependent_definite_assignment(self):
        method='boolean m(){int b;return false && b>0;}'
        changed=create_strategy('SS4',extract='subexpressions')(method)
        self.assertEqual(changed,method)
        with tempfile.TemporaryDirectory() as directory:
            original=compile_run('public class T{'+method+'public static void main(String[] a){System.out.print(new T().m());}}','java',Path(directory)/'original')
        self.assertEqual(original['compile']['returncode'],0,original)
        self.assertEqual(original['run']['stdout'],'false',original)

    def test_constant_if_dispatch_cannot_lose_definite_assignment(self):
        method='int m(){final int a=1;int x;if(a==1){x=7;}return x;}'
        for sid in ('CC4','CC5'):
            self.assertEqual(create_strategy(sid)(method),method)
        with tempfile.TemporaryDirectory() as directory:
            original=compile_run('public class T{'+method+'public static void main(String[] a){System.out.print(new T().m());}}','java',Path(directory)/'original')
        self.assertEqual(original['compile']['returncode'],0,original)
        self.assertEqual(original['run']['stdout'],'7',original)

    def test_java_text_block_bytes_are_preserved(self):
        # Host Java 11 cannot compile text blocks. This is a structural check,
        # explicitly separate from the Java compiler/run evidence.
        text = '"""\n    hello\n      world\n    """'
        method = 'int m(int a){String x="";if(a==1){x=' + text + ';}else{x="bye";}return x.hashCode();}'
        for sid in ('CC4','CC5'):
            result = create_strategy(sid)(method)
            self.assertNotEqual(method, result)
            self.assertIn(text, result)

    def test_java_elided_condition_cannot_invalidate_checked_catch(self):
        code = 'class T{boolean p() throws java.io.IOException{return false;}int m(){try{do{return 1;}while(p());}catch(java.io.IOException e){return 2;}}}'
        for sid in ('CL6','CL7'):
            self.assertEqual(create_strategy(sid)(code), code)

    def test_c_generated_expression_trees_preserve_results(self):
        # All 7 operators crossed with both compound operand shapes, across
        # two extraction positions and repeated application (224 variants).
        operators = ('+', '*', '&', '|', '^', '==', '!=')
        expressions = [f'a {inner} b {outer} c' for inner, outer in product(operators, repeat=2)]
        expressions += [f'a {op} (b-c)' for op in operators]
        before, after, calls = [], [], []
        for i, (expression, selection, k) in enumerate(product(expressions, ('first', 'last'), (1,3))):
            source = f'int f{i}(int a,int b,int c){{return {expression};}}'
            result = create_strategy('SE1', language='c', selection=selection).apply(source,k)
            self.assertGreater(result.successful, 0, result)
            before.append(source)
            after.append(result.code)
            for a,b,c in product((-2,0,2), repeat=3):
                calls.append(f'printf("%d\\n",f{i}({a},{b},{c}));')
        main = '\n#include <stdio.h>\nint main(void){' + ''.join(calls) + 'return 0;}'
        # The generation pipeline sees only directive-free functions. Headers
        # belong to the test harness added after transformation.
        with tempfile.TemporaryDirectory() as directory:
            first = compile_run('\n'.join(before)+main, 'c', Path(directory)/'before')
            second = compile_run('\n'.join(after)+main, 'c', Path(directory)/'after')
        for run in (first,second):
            self.assertEqual(run['compile']['returncode'],0,run['compile']['stderr'])
            self.assertEqual(run['run']['returncode'],0,run['run'])
            self.assertEqual(run['run']['stderr'],'',run['run'])
        self.assertEqual(first['run']['stdout'],second['run']['stdout'])

    def test_c_post_test_conversion_preserves_constant_loop_headers(self):
        from operators.c.analysis.context import CContext
        for sid,kind in (('CL6','for_statement'),('CL7','while_statement')):
            source='int f(void){do{for(;;){continue;}}while(0);}'
            op=create_strategy(sid,language='c')
            result=op.apply(source)
            self.assertEqual(result.successful,1,result)
            context=CContext(result.code,op.parser)
            loop=next(n for n in context.nodes if n.type==kind)
            self.assertEqual(context.integer(loop.child_by_field_name('condition')),1)
            with tempfile.TemporaryDirectory() as directory:
                for index,code in enumerate((source,result.code)):
                    path=Path(directory)/f'{index}.c'
                    binary=Path(directory)/str(index)
                    path.write_text(code+'int main(void){return f();}')
                    compiled=subprocess.run(['gcc','-std=c11','-pedantic-errors','-O2',str(path),'-o',str(binary)],capture_output=True,text=True,timeout=20)
                    self.assertEqual(compiled.returncode,0,compiled.stderr)
                    with self.assertRaises(subprocess.TimeoutExpired):
                        subprocess.run([str(binary)],capture_output=True,timeout=0.15)

    def test_identifier_spellings_with_language_equivalence_are_refused(self):
        cases = [
            ('java', 'public class T{int m(){int ab=1;return a\u200cb;}public static void main(String[] a){System.out.print(new T().m());}}'),
            ('c', 'int f(void){int caf\\u00e9=1;return café;}int main(void){return f()!=1;}'),
        ]
        for language,source in cases:
            result=create_strategy('WI1',language=language).apply(source)
            self.assertEqual(result.successful,0,result)
            self.assertEqual(result.code,source)
            with tempfile.TemporaryDirectory() as directory:
                original=compile_run(source,language,Path(directory)/'original')
            self.assertEqual(original['compile']['returncode'],0,original)
            self.assertEqual(original['run']['returncode'],0,original)

    def test_c_alpha_conversion_preserves_function_and_shadowing(self):
        for source in ('int f(int f){return f+1;}int main(void){return f(1)!=2;}',
                       'int f(int a){int x=1;{int a=2;x+=a;}return a+x;}int main(void){return f(3)!=6;}'):
            transformed=create_strategy('WI1',language='c',selection='first')(source,3)
            with tempfile.TemporaryDirectory() as directory:
                first=compile_run(source,'c',Path(directory)/'before')
                second=compile_run(transformed,'c',Path(directory)/'after')
            self.assertEqual(first['compile']['returncode'],0,first)
            self.assertEqual(second['compile']['returncode'],0,second)
            self.assertEqual(first['run']['returncode'],second['run']['returncode'])


if __name__ == '__main__':
    unittest.main()
