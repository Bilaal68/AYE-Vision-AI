import http.server
import socketserver
import os
import re

PORT = 9000
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

class S3Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/minio/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        clean_path = self.path.split("?")[0].lstrip("/")
        file_path = os.path.join(DATA_DIR, clean_path)

        if os.path.isdir(file_path):
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(b'<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"></ListBucketResult>')
            return

        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(file_path)))
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_response(404)
        self.end_headers()

    def do_HEAD(self):
        if self.path.startswith("/minio/health"):
            self.send_response(200)
            self.end_headers()
            return

        clean_path = self.path.split("?")[0].lstrip("/")
        file_path = os.path.join(DATA_DIR, clean_path)

        if os.path.exists(file_path):
            self.send_response(200)
            if os.path.isfile(file_path):
                self.send_header("Content-Length", str(os.path.getsize(file_path)))
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        content_length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(content_length) if content_length > 0 else b""

        clean_path = self.path.split("?")[0].lstrip("/")
        file_path = os.path.join(DATA_DIR, clean_path)

        if "/" not in clean_path:
            # Bucket creation
            os.makedirs(file_path, exist_ok=True)
            self.send_response(200)
            self.end_headers()
            return

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(data)

        self.send_response(200)
        self.send_header("ETag", '"dummyetag"')
        self.end_headers()

    def do_DELETE(self):
        clean_path = self.path.split("?")[0].lstrip("/")
        file_path = os.path.join(DATA_DIR, clean_path)
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path, ignore_errors=True)
        self.send_response(204)
        self.end_headers()

with socketserver.ThreadingTCPServer(("", PORT), S3Handler) as httpd:
    print(f"Serving S3 Mock on port {PORT}")
    httpd.serve_forever()
