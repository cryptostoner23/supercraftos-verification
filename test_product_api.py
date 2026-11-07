import http.client
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from supercraftos_cli import BoundedHTTPServer, Handler


class ProductAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated_products = []
        cls.server = BoundedHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.client = http.client.HTTPConnection

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=3)
        from product_design import PRODUCTS
        for ident in cls.generated_products:
            shutil.rmtree(PRODUCTS / ident, ignore_errors=True)

    def request(self, path, spec=None):
        connection = self.client('127.0.0.1', self.server.server_port, timeout=50)
        headers = {}
        if spec is not None:
            connection.request('GET', '/api/session')
            headers['X-SuperCraftOS-Token'] = json.loads(connection.getresponse().read())['token']
        connection.request('POST' if spec is not None else 'GET', path, json.dumps(spec) if spec is not None else None, headers)
        response = connection.getresponse(); status = response.status; data = response.read(); connection.close()
        return status, data

    def test_invalid_dimensions_and_schema_types(self):
        for spec in [{'width_mm': -1}, {'wall_mm': 99}, {'width_mm': float('nan')}, {'template': []}, {'material': []}, {'execute': 'shell'}]:
            self.assertEqual(self.request('/api/products/screen', spec)[0], 400)

    def test_the_workspace_is_pruned_so_the_product_lab_keeps_working(self) -> None:
        # The workspace used to grow until it hit a hard limit, and every
        # product build then failed for good.
        import os
        import tempfile
        from pathlib import Path
        import product_design
        with tempfile.TemporaryDirectory() as temporary:
            original = product_design.PRODUCTS
            product_design.PRODUCTS = Path(temporary)
            try:
                for index in range(30):
                    workspace = product_design.PRODUCTS / f"design-{index:03d}"
                    workspace.mkdir(parents=True)
                    (workspace / 'spec.json').write_text('{}')
                    os.utime(workspace, (1000 + index, 1000 + index))
                removed = product_design.prune_products(keep=20)
                self.assertEqual(removed, 10)
                remaining = sorted(p.name for p in product_design.PRODUCTS.iterdir() if p.is_dir())
                self.assertEqual(len(remaining), 20)
                # The newest designs are the ones that are kept.
                self.assertIn('design-029', remaining)
                self.assertNotIn('design-000', remaining)
            finally:
                product_design.PRODUCTS = original

    def test_a_thin_plate_is_a_valid_design(self) -> None:
        # A badge plate is thin by nature. The height floor used to be 5 mm for
        # every template, which rejected ordinary plates.
        code, body = self.request('/api/products/screen', {
            'template': 'plate', 'width_mm': 50, 'depth_mm': 30, 'height_mm': 3,
            'wall_mm': 2, 'hole_mm': 0, 'load_n': 0})
        self.assertEqual(code, 200)
        report = json.loads(body)
        self.assertEqual(report['readiness'], 'prototype_candidate')
        self.assertEqual(report['spec']['height_mm'], 2)
        self.assertEqual(report['effective_envelope_mm']['height_mm'], 2)
        self.assertTrue(any(row['code'] == 'plate_height_input' for row in report['checks']))

    def test_a_thin_enclosure_is_still_rejected(self) -> None:
        code, body = self.request('/api/products/screen', {
            'template': 'enclosure', 'width_mm': 50, 'depth_mm': 30, 'height_mm': 3,
            'wall_mm': 2, 'hole_mm': 0, 'load_n': 0})
        self.assertEqual(code, 400)
        self.assertEqual(json.loads(body)['error'], 'invalid_request')
        self.assertIn('height_mm', json.loads(body)['detail'])

    def test_normalized_thin_plate_can_be_screened_again(self):
        from product_design import screen_product, product_tools
        report = screen_product({'template': 'plate', 'wall_mm': .4})
        self.assertEqual(screen_product(report['spec'])['spec']['height_mm'], .4)
        schema = product_tools()[0]['inputSchema']
        self.assertLessEqual(schema['properties']['height_mm']['minimum'], .4)

    def test_process_mismatch_is_risk_not_feasibility_claim(self):
        code, body = self.request('/api/products/screen', {'material': 'Aluminum 6061-T6', 'process': 'FDM'})
        self.assertEqual(code, 200)
        report = json.loads(body)
        self.assertEqual(report['readiness'], 'redesign_required')
        self.assertTrue(any(check['status'] == 'unknown' for check in report['checks']))

    def test_beam_equation_known_case(self):
        code, body = self.request('/api/products/screen', {'template': 'plate', 'width_mm': 100, 'depth_mm': 50, 'height_mm': 20, 'wall_mm': 5, 'hole_mm': 0, 'load_n': 10})
        report = json.loads(body)
        self.assertEqual(code, 200)
        self.assertAlmostEqual(report['beam_screen']['bending_stress_mpa'], 1.2)
        self.assertAlmostEqual(report['beam_screen']['tip_deflection_mm'], 0.16)

    @unittest.skipUnless((Path(__file__).resolve().parent / '.cad-venv/bin/python').exists(), 'Optional CAD environment is not installed')
    def test_all_three_templates_generate_real_files(self):
        # Discovery loads unrelated model/runtime modules into the test runner.
        # Exercise the real HTTP handler in a clean service-sized process so
        # those imports do not consume the production controller's RSS budget.
        # The child runs this exact test, including all artifact assertions;
        # neither the 384 MB worker cap nor the 512 MB combined cap is changed.
        if os.environ.get('SUPERCRAFTOS_CAD_API_TEST_CHILD') != '1':
            environment = dict(os.environ)
            environment.pop('PYTHONPATH', None)
            environment.update({'SUPERCRAFTOS_CAD_API_TEST_CHILD': '1',
                                'DD_TRACE_ENABLED': 'false', 'DD_CIVISIBILITY_ENABLED': 'false'})
            completed = subprocess.run(
                [sys.executable, '-m', 'unittest', '-q',
                 'test_product_api.ProductAPITests.test_all_three_templates_generate_real_files'],
                cwd=Path(__file__).resolve().parent, env=environment,
                capture_output=True, text=True, timeout=160)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return
        for template in ('enclosure', 'plate', 'bracket'):
            code, body = self.request('/api/products/build', {'template': template, 'hole_mm': 0 if template == 'enclosure' else 4})
            self.assertEqual(code, 201, body)
            report = json.loads(body)
            self.generated_products.append(report['id'])
            self.assertTrue(report['geometry']['valid_solid'])
            self.assertTrue(report['geometry']['step_roundtrip_valid'])
            self.assertLess(report['worker_peak_rss_mb'], 384)
            if template == 'enclosure': self.assertAlmostEqual(report['geometry']['volume_mm3'], 52488, places=2)
            if template == 'plate': self.assertAlmostEqual(report['geometry']['volume_mm3'], 100*70*3-4*math.pi*2**2*3, places=2)
            if template == 'plate':
                self.assertEqual(report['geometry']['bounds_mm']['z'], 3)
                self.assertEqual(report['geometry']['effective_thickness_mm'], 3)
                self.assertEqual(report['effective_envelope_mm']['height_mm'], 3)
            for name, path in report['files'].items():
                code, artifact = self.request(path)
                self.assertEqual(code, 200)
                self.assertGreater(len(artifact), 10)
                if name.endswith('.step'): self.assertIn(b'ISO-10303-21', artifact)
                if name.endswith('.dxf'): self.assertIn(b'ENTITIES', artifact)

    def test_download_rejects_non_artifact_paths(self):
        self.assertEqual(self.request('/api/products/invalid/files/.env')[0], 404)

    def test_platform_registry_reports_install_state(self):
        code, body = self.request('/api/platforms')
        self.assertEqual(code, 200)
        rows = json.loads(body)['platforms']
        expected = (Path(__file__).resolve().parent / '.cad-venv/bin/python').exists()
        self.assertTrue(any(row['id'] == 'cadquery' and row['installed'] == expected for row in rows))
        self.assertTrue(all(not row['installed'] for row in rows if row['id'] != 'cadquery'))


if __name__ == '__main__': unittest.main()
