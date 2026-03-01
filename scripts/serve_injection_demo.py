"""
Serve a demo page with hidden injection on localhost:8765.
Default: attacks/malicious_webpage.txt (Financial News).
For curated web demo (movie rating site): use --movie or pass path.

Run from project root:
  python scripts/serve_injection_demo.py
  python scripts/serve_injection_demo.py --movie
  python scripts/serve_injection_demo.py attacks/malicious_movie_site.html
"""

import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOT = Path(__file__).resolve().parent.parent
ATTACKS = ROOT / "attacks"
DEFAULT_PAGE = ATTACKS / "malicious_webpage.txt"
MOVIE_PAGE = ATTACKS / "malicious_movie_site.html"
PORT = 8765


def get_page() -> Path:
    args = sys.argv[1:]
    if not args:
        return DEFAULT_PAGE
    if args[0] == "--movie":
        return MOVIE_PAGE
    p = Path(args[0])
    if not p.is_absolute():
        p = ROOT / p
    return p


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.server.page_path.exists():
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.server.page_path.read_bytes(encoding="utf-8"))

    def log_message(self, *args):
        pass


def main():
    page = get_page()
    if not page.exists():
        print(f"Missing {page}")
        sys.exit(1)
    server = HTTPServer(("", PORT), Handler)
    server.page_path = page
    print(f"Injection demo server: http://localhost:{PORT}")
    print(f"Serving: {page.name}")
    print("Stop with Ctrl+C.")
    server.serve_forever()


if __name__ == "__main__":
    main()
