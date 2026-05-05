import ast
import hashlib
import hmac
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler

MAX_CONTENT_LENGTH = 64 * 1024  # 64 KB
MAX_FIELD_LENGTH = 4096
ALLOWED_FILENAME_RE = re.compile(r'^[\w\-]+\.py$')


def _verify_webhook_secret(body: bytes, signature_header: str | None) -> bool:
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not signature_header:
        return False
    return hmac.compare_digest(expected, signature_header)


def _sanitize(value: str, max_len: int = MAX_FIELD_LENGTH) -> str:
    return str(value)[:max_len]


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # silence default access log
        pass

    def _send_json(self, code: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._send_json(200, {"status": "webhook ready"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_CONTENT_LENGTH:
                self._send_json(413, {"status": "error", "message": "Payload too large"})
                return

            body = self.rfile.read(content_length)
            if not body:
                self._send_json(400, {"status": "error", "message": "Empty body"})
                return

            # Verify webhook secret
            signature = self.headers.get("X-Webhook-Secret-Signature")
            if not _verify_webhook_secret(body, signature):
                self._send_json(401, {"status": "error", "message": "Unauthorized"})
                return

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json(400, {"status": "error", "message": "Invalid JSON"})
                return

            properties = data.get("event", {}).get("properties", {})
            if not properties:
                properties = data.get("properties", {})

            error_message = _sanitize(properties.get("error_message", "Unknown Error"))
            traceback_text = _sanitize(properties.get("traceback", "No traceback"))
            file_name = properties.get("file_name", "fake_app.py")

            # Strict filename whitelist — no path traversal possible
            if not ALLOWED_FILENAME_RE.match(str(file_name)):
                self._send_json(400, {"status": "error", "message": "Invalid file_name"})
                return
            file_name = _sanitize(file_name, 256)

            github_token = os.environ.get("GITHUB_PAT")
            if not github_token:
                self._send_json(500, {"status": "error", "message": "Server misconfigured"})
                return

            repo = os.environ.get("GITHUB_REPO")
            if not repo or "/" not in repo:
                self._send_json(500, {"status": "error", "message": "Server misconfigured"})
                return

            url = f"https://api.github.com/repos/{repo}/dispatches"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {github_token}",
                "Content-Type": "application/json",
            }
            dispatch_payload = {
                "event_type": "posthog_error",
                "client_payload": {
                    "error_message": error_message,
                    "traceback": traceback_text,
                    "file_name": file_name,
                },
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(dispatch_payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()

            self._send_json(200, {"status": "success", "dispatched": True})

        except Exception:
            # Never expose internal error details to the caller
            self._send_json(500, {"status": "error", "message": "Internal server error"})
