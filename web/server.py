#!/usr/bin/env python3
"""Read-only loopback learning UI. Run: python3 web/server.py --port 8765."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .catalog import Catalog, FileNotAllowed, read_regular_file
    from .learning import LearningCatalog
    from .launch import public_recipe
else:
    from catalog import Catalog, FileNotAllowed, read_regular_file
    from learning import LearningCatalog
    from launch import public_recipe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
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
            if request.path == "/api/catalog":
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
        except (ValueError, UnicodeError):
            self._error(400, "Invalid request")

    do_HEAD = do_GET

    def _read_only(self):
        if not self._request_allowed():
            self._error(403, "Only requests from this local UI are allowed")
        else:
            self._error(405, "This server is read-only", allow=True)
        self.close_connection = True

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _read_only


def create_server(root=PROJECT_ROOT, host="127.0.0.1", port=8765):
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
    return server


def main():
    parser = argparse.ArgumentParser(description="Serve the learning kit locally without executing any lab commands.")
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = create_server(host=options.host, port=options.port)
    except (OSError, FileNotAllowed) as error:
        parser.error(f"Cannot start the local server: {error}")
    print(f"AWS Interview Arcade: http://{options.host}:{server.server_port}", flush=True)
    print("Read-only source viewer. Run lab commands yourself; Ctrl-C stops this server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
