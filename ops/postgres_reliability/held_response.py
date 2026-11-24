"""Internal lab-only HTTP gate. It holds a selected response after the mock commits."""

import http.client
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RUN_ID = os.environ.get("SYNCOPS_LAB_RUN_ID")
ROUTES = {f"/internal/{system}/deliver" for system in ("crm", "erp", "tms")}


class Gate(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path not in ROUTES:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 73728:
                self.send_error(413)
                return
            body = self.rfile.read(length)
            event = json.loads(body)
            if RUN_ID is None or event["payload"].get("lab_crash") != RUN_ID:
                self.send_error(422)
                return
            connection = http.client.HTTPConnection("mock", port=8001, timeout=5)
            try:
                connection.request(
                    "POST",
                    self.path,
                    body,
                    {
                        "Authorization": self.headers.get("Authorization", ""),
                        "Content-Type": "application/json",
                    },
                )
                with connection.getresponse() as response:
                    response_body = response.read(16384)
                    status = response.status
            finally:
                connection.close()
        except (ValueError, KeyError, TypeError, OSError, http.client.HTTPException):
            self.send_error(502)
            return

        # The test kills the real worker while this handler is withholding a committed result.
        if status == 200:
            time.sleep(30)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response_body)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8010), Gate).serve_forever()
