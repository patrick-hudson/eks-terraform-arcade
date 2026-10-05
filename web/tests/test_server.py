"""Loopback-only HTTP contract tests; all files are temporary fixtures."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import quote

from web.server import create_server
from web.tests.test_catalog import write_fixture


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        write_fixture(cls.root, {
            "README.md": "# Kit\n",
            "labs/00-example/README.md": "# 00 - Example\n\nRead only.\n",
            "labs/00-example/solution/main.tf": "# exact source\n",
        })
        (cls.root / "web").mkdir()
        (cls.root / "web/index.html").write_text("<!doctype html><title>Local kit</title>")
        (cls.root / "web/server.py").write_text("PRIVATE_SERVER_SOURCE")
        (cls.root / "lab-recipes.json").write_text(json.dumps({"schemaVersion":1,"recipes":[{"id":"00-example","alias":"00","title":"Example","kind":"terraform","runDirectory":"00-example","prerequisites":[],"cost":"Local only","modes":{"starter":{"label":"Starter","description":"Broken exercise","files":[{"source":"PRIVATE_SOURCE","destination":"main.tf"}],"steps":[{"title":"hidden","command":"PRIVATE_COMMAND"}],"cleanup":[]}}}]}))
        for filename in ("workspace.css", "practice-core.js", "practice.js", "verification-core.js", "verification.js"):
            (cls.root / "web" / filename).write_text("/* public fixture */")
        (cls.root / "toolchain.json").write_text(json.dumps({"verifiedOn": "2026-10-04", "tools": [{"name": "terraform", "version": "example"}]}))
        (cls.root / "web/playbooks.json").write_text(json.dumps({"00-example": {
            "id": "00-example", "objective": "Diagnose an example", "skills": [], "prerequisites": [],
            "stages": [{"id": "investigate", "title": "Investigate", "tasks": [], "hints": [
                {"title": "Start with evidence", "body": "HIDDEN_FIRST_HINT"},
                {"title": "Narrow the cause", "body": "HIDDEN_SECOND_HINT"}]}],
            "questions": [{"id": "reasoning", "prompt": "What is evidence?", "options": ["A guess", "An observation"], "correctIndex": 1, "explanation": "HIDDEN_ANSWER_EXPLANATION"}],
            "debriefPrompts": []}}))
        cls.server = create_server(cls.root, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.directory.cleanup()

    def request(self, path, method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_catalog_and_source_contract(self):
        status, headers, body = self.request("/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["schemaVersion"], 1)
        path = "labs/00-example/solution/main.tf"
        status, headers, body = self.request("/api/file?path=" + quote(path))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"path": path, "content": "# exact source\n", "language": "hcl"})
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_only_explicit_frontend_routes_are_served(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/index.html")[0], 200)
        for path in ("/workspace.css", "/practice-core.js", "/practice.js", "/verification-core.js", "/verification.js"):
            self.assertEqual(self.request(path)[0], 200)
        for path in ("/web/server.py", "/server.py", "/playbooks.json", "/toolchain.json", "/labs/00-example/README.md", "/MANIFEST.sha256", "/vendor/", "/%2e%2e/README.md"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_launch_metadata_excludes_file_maps_and_commands(self):
        status, _, body = self.request("/api/launch?id=00-example")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["alias"], "00")
        self.assertEqual(data["modes"], {"starter": {"label": "Starter", "description": "Broken exercise"}})
        self.assertNotIn(b"PRIVATE_", body)
        self.assertEqual(self.request("/api/launch?id=../run")[0], 400)
        self.assertEqual(self.request("/api/launch?id=00-example&execute=1")[0], 400)
        self.assertEqual(self.request("/lab-recipes.json")[0], 404)

    def test_traversal_runtime_and_unlisted_sources_are_denied(self):
        for path in ("../README.md", "/etc/passwd", "run/terraform.tfstate", "web/server.py", "labs/../README.md", "%2e%2e/README.md", "README.md\x00"):
            with self.subTest(path=path):
                self.assertEqual(self.request("/api/file?path=" + quote(path, safe=""))[0], 404)

    def test_api_rejects_missing_duplicate_and_extra_query_parameters(self):
        for path in ("/api/file", "/api/file?path=", "/api/file?path=README.md&path=README.md", "/api/file?path=README.md&write=1", "/api/catalog?path=README.md"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)

    def test_public_lesson_excludes_hints_and_answer_keys(self):
        status, _, body = self.request("/api/lesson?id=00-example")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["id"], "00-example")
        self.assertEqual(payload["stages"][0]["hintCount"], 2)
        self.assertNotIn(b"HIDDEN_", body)
        self.assertNotIn(b'"hints"', body)
        self.assertNotIn(b"correctIndex", body)
        self.assertNotIn(b"explanation", body)

    def test_hint_reveals_only_requested_level(self):
        status, _, body = self.request("/api/hint?id=00-example&stage=investigate&level=1")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"title": "Start with evidence", "body": "HIDDEN_FIRST_HINT", "level": 1, "total": 2})
        self.assertNotIn(b"HIDDEN_SECOND_HINT", body)
        self.assertNotIn(b"HIDDEN_ANSWER_EXPLANATION", body)

    def test_answer_submission_checks_right_and_wrong_without_exposing_index(self):
        for answer, correct in ((0, False), (1, True)):
            with self.subTest(answer=answer):
                status, _, body = self.request(f"/api/check?id=00-example&question=reasoning&answer={answer}")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), {"correct": correct, "explanation": "HIDDEN_ANSWER_EXPLANATION"})

    def test_learning_endpoints_reject_invalid_query_shapes_and_identifiers(self):
        paths = (
            "/api/lesson", "/api/lesson?id=", "/api/lesson?id=missing", "/api/lesson?id=../README.md",
            "/api/lesson?id=00-example&id=00-example", "/api/lesson?id=00-example&path=README.md",
            "/api/hint?id=00-example&stage=investigate", "/api/hint?id=00-example&stage=&level=1",
            "/api/hint?id=00-example&stage=missing&level=1", "/api/hint?id=00-example&stage=investigate&level=3",
            "/api/hint?id=00-example&stage=investigate&level=1&level=2", "/api/hint?id=00-example&stage=investigate&level=1&path=x",
            "/api/check?id=00-example&question=reasoning", "/api/check?id=00-example&question=&answer=0",
            "/api/check?id=00-example&question=missing&answer=0", "/api/check?id=00-example&question=reasoning&answer=2",
            "/api/check?id=00-example&question=reasoning&answer=0&answer=1", "/api/check?id=00-example&question=reasoning&answer=0&write=1",
            "/api/toolchain?path=README.md", "/api/toolchain?version=",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 400)

    def test_learning_indices_use_canonical_unsigned_decimal_integers(self):
        for value in ("", "-1", "+1", "1.0", "1e0", "true", " 1", "01", "١", "0x1"):
            for route, key in (("/api/hint?id=00-example&stage=investigate", "level"), ("/api/check?id=00-example&question=reasoning", "answer")):
                with self.subTest(value=value, route=route):
                    self.assertEqual(self.request(route + "&" + key + "=" + quote(value, safe=""))[0], 400)
        self.assertEqual(self.request("/api/hint?id=00-example&stage=investigate&level=0")[0], 400)

    def test_toolchain_is_a_fixed_read_only_document(self):
        status, _, body = self.request("/api/toolchain")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["tools"][0]["name"], "terraform")
        status, _, body = self.request("/api/toolchain", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    def test_foreign_host_and_origin_are_denied(self):
        for headers in ({"Host": f"attacker.test:{self.port}"}, {"Host": "localhost:1"}, {"Origin": "https://attacker.test"}, {"Origin": "null"}, {"Origin": "http://127.0.0.1:1"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request("/api/catalog", headers=headers)[0], 403)

    def test_localhost_and_ipv4_hosts_and_origins_work(self):
        for name in ("localhost", "127.0.0.1"):
            with self.subTest(name=name):
                self.assertEqual(self.request("/api/catalog", headers={"Host": f"{name}:{self.port}", "Origin": f"http://{name}:{self.port}"})[0], 200)

    def test_write_methods_are_rejected_without_mutation(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            for path in ("/api/file?path=README.md", "/api/lesson?id=00-example", "/api/hint?id=00-example&stage=investigate&level=1", "/api/check?id=00-example&question=reasoning&answer=1", "/api/toolchain"):
                with self.subTest(method=method, path=path):
                    status, headers, _ = self.request(path, method=method)
                    self.assertEqual(status, 405)
                    self.assertEqual(headers["Allow"], "GET, HEAD")
        self.assertEqual((self.root / "README.md").read_text(), "# Kit\n")

    def test_new_endpoints_keep_host_origin_and_cross_site_checks(self):
        for path in ("/api/lesson?id=00-example", "/api/hint?id=00-example&stage=investigate&level=1", "/api/check?id=00-example&question=reasoning&answer=1", "/api/toolchain"):
            for headers in ({"Host": f"attacker.test:{self.port}"}, {"Origin": "https://attacker.test"}, {"Sec-Fetch-Site": "cross-site"}):
                with self.subTest(path=path, headers=headers):
                    self.assertEqual(self.request(path, headers=headers)[0], 403)

    def test_security_headers_and_head_response(self):
        status, headers, body = self.request("/", method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
