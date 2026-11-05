"""Directional metadata, conservative premises, roundtrips and trace regressions."""
from pathlib import Path
import json
import importlib
import random
import subprocess
import tempfile
import unittest

from operators import create_strategy, get_registry, get_relation, PAIRS, RELATIONS
from operators.tools.source import unwrap
from sct_cases import CASES as JAVA
from c_sct_cases import CASES as C
from audit_semantics_counterexamples import compile_run

NEW_IDS = {'WC6','WC7','WC8','SE7','SE8','SE9','SE10','CC11','CC12','CC13','CC14'}


class DirectionalTests(unittest.TestCase):
    def test_all_fifty_one_have_symmetric_family_relations(self):
        self.assertEqual(len(PAIRS), 22)
        self.assertEqual(len(RELATIONS), 51)
        self.assertEqual(set(RELATIONS), set(get_registry()))
        self.assertEqual(sum(sid == r.inverse_id for sid, r in RELATIONS.items()), 7)
        for language in ('java', 'c'):
            for sid in get_registry(language):
                r = create_strategy(sid, language=language).relation
                back = get_relation(r.inverse_id)
                self.assertEqual(back.inverse_id, sid)
                self.assertEqual(back.family_id, r.family_id)
                self.assertEqual(get_relation(sid.lower()), r)
                cls = get_registry(language)[sid]
                package = importlib.import_module(cls.__module__.rpartition(".")[0])
                if hasattr(package, "__all__"):
                    self.assertIn(cls.__name__, package.__all__)

    def test_new_rules_repeat_without_global_random_changes(self):
        for language, examples in (('java', JAVA), ('c', C)):
            for sid in NEW_IDS:
                state = random.getstate()
                op = create_strategy(sid, language=language, selection='first', seed=23)
                a, b = op.apply(examples[sid], 3), op.apply(examples[sid], 3)
                self.assertEqual(a, b)
                self.assertGreater(a.successful, 0)
                self.assertEqual(state, random.getstate())
                self.assertFalse(op.make_context(a.code).tree.root_node.has_error)

    def test_safe_direct_roundtrips_are_applicable(self):
        # Loop/dispatch counterparts need not accept every generated auxiliary
        # label or scope. These pairs intentionally use a common safe fragment.
        direct = [('WC1','WC2'),('WC3','WC6'),('WC5','WC7'),('WC4','WC8'),
                  ('SE2','SE3'),('SE5','SE7'),('SE6','SE8'),('SE9','SE10'),
                  ('SD2','SD3'),('SD4','SD5'),('SS2','SS3'),('SS4','SS5'),
                  ('CC2','CC3'),('CC8','CC9'),('CC11','CC12'),('CC13','CC14'),('CL1','CL2')]
        for language, examples in (('java', JAVA), ('c', C)):
            for forward, backward in direct:
                code = examples[forward]
                a = create_strategy(forward, language=language, selection='first').apply(code)
                b = create_strategy(backward, language=language, selection='first').apply(a.code)
                self.assertEqual(a.successful, 1, (language, forward, a))
                self.assertEqual(b.successful, 1, (language, backward, b))

    def test_wc4_expands_and_wc8_reduces_in_both_languages(self):
        for language, code in [('java','boolean m(){return !false;}'),('c','int f(int a){return !0;}')]:
            reduced = create_strategy('WC8', language=language).apply(code)
            self.assertEqual(reduced.successful, 1)
            # Expansion never replaces the outer unary node with a literal.
            expanded = create_strategy('WC4', language=language).apply(code)
            self.assertIn('!', expanded.code)
            self.assertNotEqual(expanded.code, reduced.code)

    def test_inversion_does_not_accumulate_double_negation(self):
        for language, code in [('java', JAVA['CC10']), ('c', C['CC10'])]:
            op = create_strategy('CC10', language=language, selection='first')
            twice = op(op(code))
            ctx = op.make_context(twice)
            outer = next(n for n in ctx.nodes if n.type == 'if_statement')
            self.assertNotEqual(unwrap(outer.child_by_field_name('condition')).type, 'unary_expression')

    def test_integer_boundaries_and_assignment_conversion_rejected(self):
        examples = {
            'java': [('WC6','int m(){return 2147483647+1;}'),
                     ('WC7','long m(){return -9223372036854775808L-1L;}'),
                     ('SE7','long m(long a){a=a+2L;return a;}'),
                     ('SE8','byte m(byte a){a=(byte)(a+1);return a;}'),
                     ('SE8','int m(int a){return a=a+1;}'),
                     ('CC11','int m(int a){int x=0;x=a>0?(byte)1:(byte)2;return x;}'),
                     ('CC12','int m(int a){int x=0;if(a>0){x=1;}else{x=g();}return x;}')],
            'c': [('WC6','int f(int a){return 32767+1;}'),
                  ('WC7','int f(int a){return -32767-1;}'),
                  ('SE7','int f(int a){return a=a+1;}'),
                  ('SE8','unsigned f(unsigned a){a=a+1U;return a;}'),
                  ('SE8','int f(int a){int *p=&a;*p=*p+1;return a;}'),
                  ('CC11','int f(int a){volatile int x=0;x=a?1:2;return x;}'),
                  ('CC12','int f(int a){int x=0;if(a){x=1;}else{x=g();}return x;}')]
        }
        for language, cases in examples.items():
            for sid, code in cases:
                self.assertEqual(create_strategy(sid, language=language).apply(code).successful, 0, (sid, code))

    def test_patterns_declarations_and_calls_are_not_cloned_or_retyped(self):
        cases = [('java','CC13','Object m(int a){if(a>0||a<0){enum E{A}return E.A;}return null;}'),
                 ('java','CC14','Object m(int a){if(a>0){enum E{A}return E.A;}else if(a<0){enum E{A}return E.A;}return null;}'),
                 ('java','CC13','int m(int a){if(a>0||a<0){int x=1;return x;}return 0;}'),
                 ('java','SE9','boolean m(){return !(f() && g());}'),
                 ('java','CC14','int m(int a){if(a>0){int x=1;return x;}else if(a<0){int x=1;return x;}return 0;}'),
                 ('c','CC13','int f(int a){if(a>0||a<0){int x=1;return x;}return 0;}'),
                 ('c','SE9','int f(int a){return !(g() && a);}'),
                 ('c','CC14','int f(int a){if(a>0){a=1;}else if(a<0){a=1;}else{a=2;}return a;}')]
        for language, sid, code in cases:
            self.assertEqual(create_strategy(sid, language=language).apply(code).successful, 0)

    def test_unicode_offsets_and_shadowed_targets(self):
        for language in ('java','c'):
            code = ('int m(int a)' if language=='java' else 'int f(int a)')+'{/* 中文 */int x=1;{int x2=2;x2=x2+1;}x=x+1;return x+a;}'
            op = create_strategy('SE7', language=language, selection='first')
            r = op.apply(code)
            self.assertEqual(r.successful, 1)
            self.assertIn('/* 中文 */', r.code)
            self.assertIn('x2++;', r.code)
            self.assertIn('x=x+1;', r.code)


class DirectionalBehaviorTests(unittest.TestCase):
    def compare(self, language, code, transformed):
        with tempfile.TemporaryDirectory(prefix='sct-direction-') as d:
            before = compile_run(code, language, Path(d)/'before')
            after = compile_run(transformed, language, Path(d)/'after')
            self.assertEqual(before['compile']['returncode'], 0, before)
            self.assertEqual(after['compile']['returncode'], 0, after)
            self.assertIsNotNone(before['run'])
            self.assertIsNotNone(after['run'])
            self.assertEqual(before['run']['stderr'], '')
            self.assertEqual(after['run']['stderr'], '')
            for key in ('returncode','stdout','stderr'):
                self.assertEqual(before['run'][key], after['run'][key], transformed)

    def test_logic_truth_tables_and_conditional_control_traces(self):
        # Frozen loop inputs provide all boolean combinations while the body
        # has an observable action. Short circuit arithmetic must not evaluate
        # the negation of INT_MIN in the guarded right operand.
        sources = {
            'SE9':'int m(int a,int b){return (!(a!=0 && b!=0))?1:0;}',
            'SE10':'int m(int a,int b){return (!(a!=0) || !(b!=0))?1:0;}',
            'CC11':'int m(int a,int b){int x=0;x=a!=0?a:b;return x;}',
            'CC12':'int m(int a,int b){int x=0;if(a!=0){x=a;}else{x=b;}return x;}',
            'CC13':'int m(int a,int b){int x=0;if(a!=0 || b!=0){x=x+1;}return x;}',
            'CC14':'int m(int a,int b){int x=0;if(a!=0){x=x+1;}else if(b!=0){x=x+1;}return x;}',
        }
        for language in ('java','c'):
            for sid, method in sources.items():
                if language=='c':
                    method=method.replace('m(', 'f(')
                    harness='int putchar(int); int main(void){for(int a=-2;a<=2;a++)for(int b=-2;b<=2;b++)putchar(65+f(a,b));return 0;}'
                    code=method+harness
                else:
                    harness='public static void main(String[] args){T t=new T();for(int a=-2;a<=2;a++)for(int b=-2;b<=2;b++)System.out.print(t.m(a,b)+", ");}'
                    code='public class T{'+method+harness+'}'
                r=create_strategy(sid, language=language,selection='first').apply(code)
                self.assertEqual(r.successful,1,(language,sid,r))
                self.compare(language,code,r.code)

    def test_c_short_circuit_does_not_introduce_signed_overflow(self):
        sources={
            'SE9':'int f(int a){return !(a<0 || -a>0);}',
            'SE10':'int f(int a){return !(a<0) && !(-a>0);}',
            'CC13':'int f(int a){int x=0;if(a<0 || -a>0){x=1;}return x;}',
            'CC14':'int f(int a){int x=0;if(a<0){x=1;}else if(-a>0){x=1;}return x;}',
        }
        for sid, fn in sources.items():
            code=fn+'int main(void){return f(-2147483647-1);}'
            r=create_strategy(sid,language='c',selection='first').apply(code)
            self.assertEqual(r.successful,1,r)
            self.compare('c',code,r.code)

    def test_new_forward_reverse_semantics(self):
        pairs=[('WC3','WC6'),('WC5','WC7'),('WC4','WC8'),('SE5','SE7'),('SE6','SE8'),('SE9','SE10'),('CC11','CC12'),('CC13','CC14')]
        for language, examples in (('java',JAVA),('c',C)):
            for forward, backward in pairs:
                source=examples[forward]
                if language=='java':
                    count=source.split('(',1)[1].split(')',1)[0].count('int ')
                    args=','.join(['2']*count)
                    code='public class T{'+source+'public static void main(String[] args){System.out.print(new T().m('+args+'));}}'
                else:
                    code=source+'int putchar(int);int main(void){putchar(65+f(2)%26);return 0;}'
                a=create_strategy(forward,language=language,selection='first').apply(code)
                b=create_strategy(backward,language=language,selection='first').apply(a.code)
                self.assertEqual(a.successful,1,a)
                self.assertEqual(b.successful,1,b)
                self.compare(language,code,b.code)


    def test_update_contraction_modes_and_dual_demorgan(self):
        for language in ('java', 'c'):
            originals, transformed, calls = [], [], []
            variants = [('SE7','a=a+1;'),('SE7','a=a-1;'),('SE7','a+=1;'),('SE7','a-=1;')]
            variants += [('SE8',f'a=a{op}3;') for op in ('+','-','*','&','|','^') if language=='java' or op in {'+','-','*'}]
            variants += [('SE9','return (!(a>0 || a < -2))?1:0;'),
                         ('SE10','return (!(a>0) && !(a < -2))?1:0;')]
            if language=='java':
                variants += [('SE7','a=a+1L;'),('SE8','a=a*3L;')]
            for i,(sid,statement) in enumerate(variants):
                typ='long' if statement.endswith('L;') else 'int'
                method=f'{typ} f{i}({typ} a){{{statement}'+('}' if statement.startswith('return') else 'return a;}')
                result=create_strategy(sid,language=language,selection='first').apply(method)
                self.assertEqual(result.successful,1,(language,sid,method,result))
                originals.append(method)
                transformed.append(result.code)
                if language=='java':
                    calls.append(f'for(int a=-8;a<=8;a++)System.out.println(t.f{i}(a));')
                else:
                    calls.append(f'for(int a=-8;a<=8;a++)printf("%d\\n",f{i}(a));')
            if language=='java':
                def package(methods):return 'public class T{'+''.join(methods)+'public static void main(String[] args){T t=new T();'+''.join(calls)+'}}'
            else:
                def package(methods):return 'int printf(const char*,...);'+''.join(methods)+'int main(void){'+''.join(calls)+'return 0;}'
            self.compare(language,package(originals),package(transformed))


class DirectionalEntrypointTests(unittest.TestCase):
    def test_new_combination_cli_logs_relations_and_refuses_overwrite(self):
        import sys
        script = Path(__file__).resolve().parents[1] / 'operate_source.py'
        for language in ('java', 'c'):
            with tempfile.TemporaryDirectory(prefix='sct-direction-cli-') as d:
                source = Path(d)/'input.txt'
                code = ('int m(int a)' if language=='java' else 'int f(int a)')+'{int x=0;x=a>0?a:0;a=a+1;return x+a;}'
                source.write_text(code)
                output = Path(d)/('output_'+ ('c_' if language=='c' else '')+'CC11k1_CC12k1_SE7k1.txt')
                command = [sys.executable,str(script),'--input',str(source),'--output',str(output),
                           '--language',language,'--strategies','CC11:1,CC12:1,SE7:1']
                result = subprocess.run(command,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                records = [json.loads(line) for line in Path(str(output)+'.applications.jsonl').read_text().splitlines()]
                self.assertTrue(records[-1]['completed'])
                applications = records[1:-1]
                self.assertEqual(len(applications),3)
                for r in applications:
                    self.assertEqual(r['successful'],1,r)
                    self.assertEqual(r['changes'][0]['inverse_id'],get_relation(r['strategy_id']).inverse_id)
                original_bytes=output.read_bytes()
                repeated=subprocess.run(command,capture_output=True,text=True,timeout=30)
                self.assertNotEqual(repeated.returncode,0)
                self.assertEqual(output.read_bytes(),original_bytes)

    def test_new_rules_are_selected_by_applicability_audit(self):
        from audit_sct_applicability import audit
        for language, examples in (('java',JAVA),('c',C)):
            with tempfile.TemporaryDirectory(prefix='sct-direction-audit-') as d:
                path=Path(d)/'input.tsv'
                path.write_text(''.join(f'{i}\t{examples[sid]}\n' for i,sid in enumerate(sorted(NEW_IDS))))
                report=audit(path,11,sorted(NEW_IDS),seed=42,language=language)
                self.assertEqual(report['language'],language)
                self.assertEqual(set(report['strategies']),NEW_IDS)
                for sid in NEW_IDS:
                    self.assertGreater(report['strategies'][sid]['changed'],0,(sid,report['strategies'][sid]))
