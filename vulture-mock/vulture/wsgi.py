"""
WSGI entry point for vulture-mock.

Routes:
  /wps        -> PyWPS service (WPS 1.0.0 and 2.0.0, GET KVP and POST XML)
  /outputs/*  -> generated outputs and async status documents
  /health     -> "ok"
  /           -> small landing page with example requests

Environment variables:
  PUBLIC_URL            Public base URL, e.g. https://vulture-mock.onrender.com
                        (auto-detected on Render and Hugging Face Spaces)
  PORT                  Port for local runs (default 5000)
  DATA_DIR              Where outputs/workdirs/logs go (default /tmp/vulture-mock)
  CORS_ALLOW_ORIGIN     Value for Access-Control-Allow-Origin (default "*")
  MOCK_DELAY_SECONDS    Simulated time per processing step (default 1.5)
  OUTPUT_TTL_HOURS      Delete outputs older than this (default 24)
"""
import os
import time
import shutil
import threading

from pywps.app.Service import Service
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wrappers import Response

from .processes import processes


def _public_url():
    url = os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    if not url and os.environ.get("SPACE_HOST"):          # Hugging Face Spaces
        url = "https://" + os.environ["SPACE_HOST"]
    if not url:
        url = f"http://localhost:{os.environ.get('PORT', '5000')}"
    return url.rstrip("/")


PUBLIC_URL = _public_url()
DATA_DIR = os.environ.get("DATA_DIR", "/tmp/vulture-mock")
OUTPUT_DIR = os.path.join(DATA_DIR, "outputs")
WORK_DIR = os.path.join(DATA_DIR, "workdir")
CORS_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*")
OUTPUT_TTL = float(os.environ.get("OUTPUT_TTL_HOURS", "24")) * 3600

for d in (OUTPUT_DIR, WORK_DIR):
    os.makedirs(d, exist_ok=True)


def _write_runtime_config():
    cfg = os.path.join(DATA_DIR, "runtime.cfg")
    with open(cfg, "w") as f:
        f.write(f"""[server]
url = {PUBLIC_URL}/wps
outputurl = {PUBLIC_URL}/outputs
outputpath = {OUTPUT_DIR}
workdir = {WORK_DIR}

[logging]
file = {os.path.join(DATA_DIR, 'pywps.log')}
database = sqlite:///{os.path.join(DATA_DIR, 'pywps-logs.sqlite')}
""")
    return cfg


def create_app(cfgfiles=None):
    config_files = [os.path.join(os.path.dirname(__file__), "default.cfg"), _write_runtime_config()]
    if cfgfiles:
        config_files.extend(cfgfiles)
    if "PYWPS_CFG" in os.environ:
        config_files.append(os.environ["PYWPS_CFG"])
    return Service(processes=processes, cfgfiles=config_files)


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>vulture-mock WPS</title>
<style>body{{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;line-height:1.5}}
code{{background:#eee;padding:.1em .3em;border-radius:3px;word-break:break-all}}</style></head><body>
<h1>vulture-mock</h1>
<p>A mock of the <a href="https://github.com/cedadev/vulture">cedadev/vulture</a> WPS with the same
process interfaces and synthetic data. For front-end development only.</p>
<ul>
<li><a href="{u}/wps?service=WPS&request=GetCapabilities">GetCapabilities</a></li>
<li><a href="{u}/wps?service=WPS&version=1.0.0&request=DescribeProcess&identifier=all">DescribeProcess (all)</a></li>
<li><a href="{u}/wps?service=WPS&version=1.0.0&request=Execute&identifier=PlotClimateStripes&DataInputs=latitude=51.57;longitude=-1.31;start_year=1901;end_year=2022">Execute PlotClimateStripes (sync)</a></li>
<li><a href="{u}/wps?service=WPS&version=1.0.0&request=Execute&identifier=PlotClimateStripesGlobal&DataInputs=latitude=48.85;longitude=2.35&storeExecuteResponse=true&status=true">Execute PlotClimateStripesGlobal (async)</a></li>
<li><a href="{u}/wps?service=WPS&version=1.0.0&request=Execute&identifier=CFCheck&DataInputs=CFVersion=auto;NetCDFFilePath=/badc/some/file_with_errors.nc">Execute CFCheck (sync, with errors)</a></li>
</ul>
<p>WPS endpoint: <code>{u}/wps</code></p>
</body></html>"""


class App:
    """Dispatch /wps to PyWPS, serve /outputs, add CORS, prune old outputs."""

    def __init__(self):
        self.wps = create_app()
        self.outputs = SharedDataMiddleware(self._not_found, {"/outputs": OUTPUT_DIR}, cache=False)
        self._last_prune = 0
        self._lock = threading.Lock()

    @staticmethod
    def _not_found(environ, start_response):
        return Response("Not found", status=404)(environ, start_response)

    def _prune(self):
        now = time.time()
        with self._lock:
            if now - self._last_prune < 600:
                return
            self._last_prune = now
        for base in (OUTPUT_DIR, WORK_DIR):
            for name in os.listdir(base):
                path = os.path.join(base, name)
                try:
                    if now - os.path.getmtime(path) > OUTPUT_TTL:
                        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
                except OSError:
                    pass

    def __call__(self, environ, start_response):
        self._prune()
        path = environ.get("PATH_INFO", "/")

        def cors_start_response(status, headers, exc_info=None):
            headers = [h for h in headers if h[0].lower() != "access-control-allow-origin"]
            headers += [
                ("Access-Control-Allow-Origin", CORS_ORIGIN),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization"),
                ("Access-Control-Expose-Headers", "Content-Type, Content-Length, Content-Disposition"),
            ]
            return start_response(status, headers, exc_info)

        if environ.get("REQUEST_METHOD") == "OPTIONS":
            return Response(status=204)(environ, cors_start_response)

        if path.rstrip("/") == "/wps":
            return self.wps(environ, cors_start_response)
        if path.startswith("/outputs/"):
            return self.outputs(environ, cors_start_response)
        if path == "/health":
            return Response("ok")(environ, cors_start_response)
        if path == "/":
            html = INDEX_HTML.format(u=PUBLIC_URL)
            return Response(html, mimetype="text/html")(environ, cors_start_response)
        return self._not_found(environ, cors_start_response)


application = App()


if __name__ == "__main__":
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", int(os.environ.get("PORT", "5000")), application, threaded=True)
