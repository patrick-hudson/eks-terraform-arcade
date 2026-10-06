"""Exercise the public drill boundary over real loopback HTTP."""
import http.client
import json
from pathlib import Path
import threading
import unittest

from web.server import create_server


class DrillAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(Path(__file__).resolve().parents[2], port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request('GET', path, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, json.loads(data)

    def test_public_brief_then_requested_evidence_and_feedback(self):
        status, catalog = self.request('/api/drills')
        self.assertEqual(status, 200)
        self.assertEqual(len(catalog['drills']), 7)
        self.assertNotIn('answer', json.dumps(catalog))
        drill_id = catalog['drills'][0]['id']
        status, brief = self.request('/api/drill?id=' + drill_id)
        self.assertEqual(status, 200)
        self.assertNotIn('answer', brief)
        self.assertTrue(all('output' not in o for o in brief['observations']))
        evidence_id = brief['observations'][0]['id']
        status, evidence = self.request(f'/api/drill-evidence?id={drill_id}&evidence={evidence_id}')
        self.assertEqual(status, 200)
        self.assertEqual(evidence['id'], evidence_id)
        self.assertIn('output', evidence)
        self.assertNotIn('answer', evidence)
        option = brief['question']['options'][0]['id']
        status, feedback = self.request(f'/api/drill-answer?id={drill_id}&answer={option}')
        self.assertEqual(status, 200)
        self.assertIsInstance(feedback['correct'], bool)
        self.assertIn('repair', feedback)

    def test_exact_queries_and_local_authority(self):
        for path in ['/api/drills?extra=1', '/api/drill', '/api/drill?id=a&id=b',
                     '/api/drill?id=../run', '/api/drill-answer?id=a&answer=b&execute=1',
                     '/api/drill-evidence?id=a&evidence=b&evidence=c']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.request('/api/drills', {'Host':'example.com'})[0], 403)
        self.assertEqual(self.request('/api/drills', {'Origin':'https://example.com'})[0], 403)
        self.assertEqual(self.request('/practice/cases.json')[0], 404)


if __name__ == '__main__':
    unittest.main()
