import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from route_verifier import evaluate, permissions
ROOT = Path(__file__).resolve().parents[1]
class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.document=json.loads((ROOT/'fixtures/passing.json').read_text())
    def test_exact_multihop_and_hook_routes(self):
        report=evaluate(self.document)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['routes']),3)
        self.assertEqual(report['routes'][2]['review_flags'],['custom_accounting','dynamic_fee','hook_permissions_require_behavior_review'])
    def test_receipt_is_deterministic(self):
        self.assertEqual(evaluate(self.document),evaluate(copy.deepcopy(self.document)))
    def test_changed_quote_fails(self):
        self.document['routes'][0]['hops'][0]['observed_out']='900'
        self.assertFalse(evaluate(self.document)['passed'])
    def test_minimum_output_fails_independently(self):
        self.document['routes'][0]['minimum_out']='9999'
        self.assertFalse(evaluate(self.document)['routes'][0]['minimum_out_passed'])
    def test_route_continuity_is_required(self):
        self.document['routes'][1]['hops'][1]['amount_in']='1000'
        with self.assertRaisesRegex(ValueError,'continuous'):evaluate(self.document)
    def test_uint256_without_precision_loss(self):
        self.document['routes']=self.document['routes'][:1]
        hop=self.document['routes'][0]['hops'][0]
        hop['reference_out']=hop['observed_out']=str((1<<256)-1)
        self.assertTrue(evaluate(self.document)['passed'])
    def test_rejects_invalid_inputs(self):
        for key,value in [('amount_in',True),('reference_out',-1),('observed_out','1e20'),('token_in','bad'),('fee',1000001)]:
            d=copy.deepcopy(self.document);d['routes'][0]['hops'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):evaluate(d)
    def test_permission_bits_match_known_boundaries(self):
        self.assertEqual(permissions('0x'+'0'*36+'2000'),['beforeInitialize'])
        self.assertEqual(permissions('0x'+'0'*39+'1'),['afterRemoveLiquidityReturnsDelta'])
    def test_cli_has_distinct_pass_fail_and_invalid_exit_codes(self):
        with tempfile.TemporaryDirectory() as root:
            for name,code in [('passing.json',0),('failing.json',1)]:
                run=subprocess.run([sys.executable,'-m','route_verifier',str(ROOT/'fixtures'/name),'--output',root],capture_output=True,text=True,cwd=ROOT)
                self.assertEqual(run.returncode,code,run.stderr)
                self.assertTrue((Path(root)/'receipt.json').exists())
            invalid=Path(root)/'invalid.json';invalid.write_text('{"schema_version":1,"schema_version":1}')
            run=subprocess.run([sys.executable,'-m','route_verifier',str(invalid)],capture_output=True,text=True,cwd=ROOT)
            self.assertEqual(run.returncode,2)
