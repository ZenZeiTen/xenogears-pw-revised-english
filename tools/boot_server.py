"""Minimal stand-in for Retroglot's player server: boots one PS1 disc with the cached
EmulatorJS runtime + pcsx_rearmed core, same headers and path mapping as Retroglot.

  python bootsrv.py DISC.bin [port]
"""
import http.server
import os
import re
import socketserver
import sys
from pathlib import Path

RT = Path(os.environ["APPDATA"]) / "Retroglot" / "runtime"
DATA = RT / "emulatorjs" / "data"
BIOS = Path.home() / ".retroglot" / "bios" / "scph5501.bin"
DISC = Path(sys.argv[1]).resolve()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765

PAGE = f"""<!doctype html><html><head><meta charset="utf-8"><title>boot test</title>
<style>html,body{{margin:0;background:#05060a;height:100%}}#game{{width:960px;height:720px}}</style></head>
<body><div id="game"></div><script>
EJS_player='#game'; EJS_core='pcsx_rearmed'; EJS_gameUrl='/rom/{DISC.name}'; EJS_gameName='boottest';
EJS_pathtodata='/ejs/'; EJS_DEBUG_XX=true; EJS_startOnLoaded=true; EJS_threads=false;
EJS_biosUrl='/bios/scph5501.bin'; EJS_language='en-US'; EJS_disableAutoLang=true;
EJS_defaultOptions={{'save-state-location':'browser'}};
window.EJS_onGameStart=function(){{document.title='STARTED';}};
</script><script src="/ejs/loader.js"></script></body></html>"""

TYPES = {".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".html": "text/html",
         ".wasm": "application/wasm", ".data": "application/octet-stream", ".bin": "application/octet-stream"}


def resolve(rel):
    clean = os.path.normpath("/" + rel).replace("\\", "/").lstrip("/")
    if clean.startswith(".."):
        return None
    m = re.fullmatch(r"cores/reports/([a-z0-9_]+)\.json", clean)
    if m:
        return RT / "cores" / m[1] / "reports" / f"{m[1]}.json"
    m = re.fullmatch(r"cores/([a-z0-9_]+?)(-thread)?(-legacy)?-wasm\.data", clean)
    if m:
        return RT / "cores" / m[1] / Path(clean).name
    return DATA / clean


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def headers_common(self, ctype, length):
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")

    def send_path(self, f):
        if not f or not f.is_file():
            self.send_error(404); return
        size = f.stat().st_size
        self.send_response(200)
        self.headers_common(TYPES.get(f.suffix, "application/octet-stream"), size)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(f, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            body = PAGE.encode()
            self.send_response(200); self.headers_common("text/html", len(body)); self.end_headers()
            self.wfile.write(body); return
        if p.startswith("/ejs/"):
            return self.send_path(resolve(p[5:]))
        if p.startswith("/rom/"):
            return self.send_path(DISC)
        if p.startswith("/bios/"):
            return self.send_path(BIOS)
        self.send_error(404)

    do_HEAD = do_GET


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"serving {DISC} on http://localhost:{PORT}/", flush=True)
    S(("127.0.0.1", PORT), H).serve_forever()
