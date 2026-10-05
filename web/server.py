#!/usr/bin/env python3
"""Loopback learning UI with an explicitly enabled local session runner."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hmac
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .catalog import Catalog, FileNotAllowed, read_regular_file
    from .learning import LearningCatalog
    from .session import JobCoordinator, Busy
    from .launch import public_recipe
else:
    from catalog import Catalog, FileNotAllowed, read_regular_file
    from learning import LearningCatalog
    from session import JobCoordinator, Busy
    from launch import public_recipe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts import drill_engine

ASSETS = {
    "/session.js": ("session.js", "text/javascript; charset=utf-8"),
    "/session.css": ("session.css", "text/css; charset=utf-8"),
    "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
    "/theme.css": ("theme.css", "text/css; charset=utf-8"),
    "/drills.js": ("drills.js", "text/javascript; charset=utf-8"),
    "/drills-core.js": ("drills-core.js", "text/javascript; charset=utf-8"),
    "/drills.css": ("drills.css", "text/css; charset=utf-8"),
    "/launcher-core.js": ("launcher-core.js", "text/javascript; charset=utf-8"),
    "/launcher.js": ("launcher.js", "text/javascript; charset=utf-8"),
    "/verification-core.js": ("verification-core.js", "text/javascript; charset=utf-8"),
    "/verification.js": ("verification.js", "text/javascript; charset=utf-8"),
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/core.js": ("core.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/workspace.css": ("workspace.css", "text/css; charset=utf-8"),
    "/practice-core.js": ("practice-core.js", "text/javascript; charset=utf-8"),
    "/practice.js": ("practice.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/vendor/marked.umd.js": ("vendor/marked.umd.js", "text/javascript; charset=utf-8"),
    "/vendor/purify.min.js": ("vendor/purify.min.js", "text/javascript; charset=utf-8"),
}
CSP = "; ".join(("default-src 'none'", "script-src 'self'", "style-src 'self'", "img-src 'self' data:", "connect-src 'self'", "font-src 'self'", "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'", "object-src 'none'"))


class ArcadeHandler(BaseHTTPRequestHandler):
    server_version = "ArcadeLocal/1"
    sys_version = ""

    def log_message(self, format_string, *args):
        # Do not log source query strings or learner paths.
        return

    def _local_authority(self, authority):
        try:
            parsed = urlsplit("//" + authority)
            port = parsed.port if parsed.port is not None else 80
            return (parsed.hostname in {"localhost", "127.0.0.1"}
                    and parsed.username is None and parsed.password is None
                    and not parsed.path and not parsed.query and not parsed.fragment
                    and port == self.server.server_port)
        except ValueError:
            return False

    def _request_allowed(self):
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or not self._local_authority(hosts[0]):
            return False
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1:
            return False
        if origins:
            try:
                origin = urlsplit(origins[0])
            except ValueError:
                return False
            if origin.scheme != "http" or origin.path or origin.query or origin.fragment or not self._local_authority(origin.netloc):
                return False
        return self.headers.get("Sec-Fetch-Site") != "cross-site"

    def _send(self, status, content, content_type="application/json; charset=utf-8", allow=False):
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if allow:
            self.send_header("Allow", "GET, HEAD")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _error(self, status, message, allow=False):
        self._send(status, json.dumps({"error": message}), allow=allow)

    @staticmethod
    def _query(raw, expected_keys):
        query = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=8)
        if set(query) != set(expected_keys) or any(len(values) != 1 or not values[0] for values in query.values()):
            raise ValueError("Supply each expected query parameter exactly once")
        return {key: values[0] for key, values in query.items()}

    @staticmethod
    def _index(value):
        if not re.fullmatch(r"0|[1-9][0-9]*", value):
            raise ValueError("Use an unsigned decimal integer")
        return int(value)

    def do_GET(self):
        if not self._request_allowed():
            self._error(403, "Only requests from this local UI are allowed")
            return
        try:
            request = urlsplit(self.path)
            if request.scheme or request.netloc or request.fragment:
                self._error(400, "Use a local request path")
                return
            if request.path == "/api/session":
                raw = parse_qs(request.query, keep_blank_values=True)
                expected = {"id", "root"} if "root" in raw else {"id"}
                query = self._query(request.query, expected)
                root = query.get("root")
                if root is not None and root not in {".", "access", "workload"}:
                    raise ValueError("Invalid Terraform root")
                session = self.server.sessions.describe(query["id"], root)
                self._send(200, json.dumps({"session":session,
                    "runnerEnabled":self.server.sessions.enabled,
                    "token":self.server.sessions.token,
                    "job":self.server.sessions.latest(query["id"]),
                    "activeJob":self.server.sessions.active()}, ensure_ascii=False))
            elif request.path == "/api/session/job":
                query = self._query(request.query, {"id"})
                self._send(200, json.dumps(self.server.sessions.get(query["id"]), ensure_ascii=False))
            elif request.path == "/api/catalog":
                if request.query:
                    self._error(400, "Catalog takes no query parameters")
                    return
                self._send(200, json.dumps(self.server.catalog.build(), ensure_ascii=False))
            elif request.path == "/api/file":
                query = self._query(request.query, {"path"})
                self._send(200, json.dumps(self.server.catalog.read_file(query["path"]), ensure_ascii=False))
            elif request.path == "/api/lesson":
                query = self._query(request.query, {"id"})
                self._send(200, json.dumps(self.server.learning.public_lesson(query["id"]), ensure_ascii=False))
            elif request.path == "/api/drills":
                if request.query:
                    raise ValueError("Drill catalog takes no query parameters")
                self._send(200, json.dumps(drill_engine.list_drills(root=self.server.root), ensure_ascii=False))
            elif request.path == "/api/drill":
                query = self._query(request.query, {"id"})
                self._send(200, json.dumps(drill_engine.public_drill(query["id"], root=self.server.root), ensure_ascii=False))
            elif request.path == "/api/drill-evidence":
                query = self._query(request.query, {"id", "evidence"})
                self._send(200, json.dumps(drill_engine.evidence(query["id"], query["evidence"], root=self.server.root), ensure_ascii=False))
            elif request.path == "/api/drill-answer":
                query = self._query(request.query, {"id", "answer"})
                self._send(200, json.dumps(drill_engine.answer(query["id"], query["answer"], root=self.server.root), ensure_ascii=False))
            elif request.path == "/api/launch":
                query = self._query(request.query, {"id"})
                self._send(200, json.dumps(public_recipe(self.server.root, query["id"]), ensure_ascii=False))
            elif request.path == "/api/hint":
                query = self._query(request.query, {"id", "stage", "level"})
                hint = self.server.learning.hint(query["id"], query["stage"], self._index(query["level"]))
                self._send(200, json.dumps(hint, ensure_ascii=False))
            elif request.path == "/api/check":
                query = self._query(request.query, {"id", "question", "answer"})
                result = self.server.learning.check_answer(query["id"], query["question"], self._index(query["answer"]))
                self._send(200, json.dumps(result, ensure_ascii=False))
            elif request.path == "/api/toolchain":
                if request.query:
                    raise ValueError("Toolchain takes no query parameters")
                toolchain = json.loads(read_regular_file(self.server.root, "toolchain.json"))
                self._send(200, json.dumps(toolchain, ensure_ascii=False))
            elif request.path in ASSETS:
                path, mime = ASSETS[request.path]
                self._send(200, read_regular_file(self.server.root, "web/" + path), mime)
            else:
                self._error(404, "Not found")
        except FileNotAllowed:
            self._error(404, "Source is unavailable or not allowed")
        except (ValueError, UnicodeError, RuntimeError):
            self._error(400, "Invalid request")

    do_HEAD = do_GET

    def _read_only(self):
        if not self._request_allowed():
            self._error(403, "Only requests from this local UI are allowed")
        else:
            self._error(405, "This server is read-only", allow=True)
        self.close_connection = True

    def do_POST(self):
        if not self._request_allowed():
            self._error(403, "Only requests from this local UI are allowed")
            self.close_connection = True
            return
        if not self.server.sessions.enabled:
            self._read_only()
            return
        origin = self.headers.get("Origin", "")
        token = self.headers.get_all("X-Arcade-Token", [])
        if not origin or len(token) != 1 or not hmac.compare_digest(token[0], self.server.sessions.token):
            self._error(403, "Reload the local runner to obtain its session capability")
            self.close_connection = True
            return
        if self.path != "/api/session/operation":
            self._error(404, "Not found")
            self.close_connection = True
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isdigit() or self.headers.get("Transfer-Encoding"):
                raise ValueError("Supply one bounded JSON body")
            length = int(lengths[0])
            if not 1 <= length <= 8192 or self.headers.get("Content-Type") != "application/json":
                raise ValueError("Supply a JSON body under 8 KiB")
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(length))
            job = self.server.sessions.start(payload)
            self._send(202, json.dumps(job, ensure_ascii=False))
        except Busy as error:
            self._error(409, str(error))
        except (ValueError, UnicodeError, RuntimeError, OSError):
            self._error(400, "Invalid session operation; choose a catalog mission and its supported inputs")
        finally:
            self.close_connection = True

    do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _read_only


def create_server(root=PROJECT_ROOT, host="127.0.0.1", port=8765, *, runner=False, session_factory=None):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The learning UI must bind to localhost or 127.0.0.1")
    root = Path(root).resolve()
    catalog = Catalog(root)
    learning = LearningCatalog(root)
    server = ThreadingHTTPServer((host, port), ArcadeHandler)
    server.daemon_threads = True
    server.root = root
    server.catalog = catalog
    server.learning = learning
    server.sessions = JobCoordinator(root, enabled=runner, factory=session_factory)
    return server


def main():
    parser = argparse.ArgumentParser(description="Serve the learning kit locally; opt in to Terraform session operations with --runner.")
    parser.add_argument("--runner", action="store_true", help="Enable explicitly approved local Terraform session operations")
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = create_server(host=options.host, port=options.port, runner=options.runner)
    except (OSError, FileNotAllowed) as error:
        parser.error(f"Cannot start the local server: {error}")
    print(f"AWS Interview Arcade: http://{options.host}:{server.server_port}", flush=True)
    print("Local runner enabled. Review and approve each saved plan; active jobs finish if the tab closes." if options.runner else "Read-only source viewer. Use --runner to enable session operations.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
