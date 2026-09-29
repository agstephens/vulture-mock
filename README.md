# vulture-mock

A cut-down, publicly deployable mock of [cedadev/vulture](https://github.com/cedadev/vulture)
(the CEDA compliance-checking / climate-stripes WPS) for building front ends against.

It runs **real PyWPS** with **the same three processes** — `CFCheck`, `PlotClimateStripes`,
`PlotClimateStripesGlobal` — so GetCapabilities, DescribeProcess, Execute (sync and async),
status documents, exception reports and output references all behave like the real service.
The `DescribeProcess` response is identical to upstream vulture (checked by diffing the XML).

Only the data access is mocked: no CEDA archive, no kerchunk, no NetCDF, no cfchecker.

## What is mocked

| Process | Real service | Mock |
|---|---|---|
| `PlotClimateStripes` | HadUK-Grid via kerchunk reference file | Deterministic synthetic series (1836–2022) seeded by lat/lon; real PNG + PDF rendered with the original matplotlib/xhtml2pdf code |
| `PlotClimateStripesGlobal` | CRU TS 4.08 NetCDF on `/badc` | Synthetic series (1901–2023); NaN over mock ocean boxes |
| `CFCheck` | Downloads/opens the file, runs cfchecker 4.1.0 | Nothing is fetched; a realistic CF-Checker text report is generated |

### Scenario hooks (to exercise error/edge UI)

| Trigger | Result |
|---|---|
| `PlotClimateStripes` with a location outside the UK (e.g. `latitude=40`) | ProcessFailed: outside HadUK-Grid coverage |
| `PlotClimateStripesGlobal` at `0, -150` (Pacific), `0, -30` (Atlantic), `-20, 75` (Indian Ocean) or lat < -60 | ProcessFailed: "returned no valid data…" (the real service's message) |
| `CFCheck` with no file input | ProcessFailed: "User must provide one input from…" |
| `CFCheck` file name/URL/path containing `error` or `bad` | Report with 2 ERRORS |
| … containing `warn` | Report with 2 WARNINGS |
| … containing `fail` | ProcessFailed: "Cannot read NetCDF file" |
| Invalid `CFVersion` (e.g. `9.9`) | PyWPS `InvalidParameterValue` exception |

`MOCK_DELAY_SECONDS` (default 1.5) adds a pause per processing step, so async jobs move through
Accepted → Started 10% → 70% → Succeeded, giving your progress UI something to show.

## Run locally

```bash
pip install -r requirements.txt
gunicorn -b 0.0.0.0:5000 -w 1 --threads 4 vulture.wsgi:application
# or: python -m vulture.wsgi
open http://localhost:5000/
```

or with Docker:

```bash
docker build -t vulture-mock .
docker run -p 5000:5000 vulture-mock
```

Tests: `pip install -r requirements_dev.txt && pytest`

## Deploy for free

### Render (recommended)
1. Push this folder to a GitHub repo.
2. Render dashboard → **New → Blueprint** → pick the repo (uses `render.yaml`, Docker, free plan).
3. The service URL is picked up automatically from `RENDER_EXTERNAL_URL`, so output and
   status links point to the public host.

Free instances sleep after ~15 min idle; the first request then takes ~30–60 s to wake.
Disk is ephemeral, so outputs disappear on restart — fine for front-end work.

### Hugging Face Spaces
Create a Space with the **Docker** SDK, push these files, and add `app_port: 5000` to the
Space's README front-matter. `SPACE_HOST` is detected automatically.

### Why not Netlify?
Netlify's serverless functions don't run a persistent Python server, and WPS async execution
needs somewhere that keeps status documents and outputs between requests (the job runs in
the background after the Execute call returns). A small always-on container is the natural fit.
If your *front end* is on Netlify, point it at the Render/HF URL — CORS is enabled.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `PUBLIC_URL` | auto (Render / HF) or `http://localhost:$PORT` | Base URL used in output/status links |
| `PORT` | `5000` | Listen port |
| `CORS_ALLOW_ORIGIN` | `*` | Set to your front end's origin to lock it down |
| `MOCK_DELAY_SECONDS` | `1.5` | Simulated time per step (`0` = instant) |
| `OUTPUT_TTL_HOURS` | `24` | Old outputs/workdirs are pruned |
| `DATA_DIR` | `/tmp/vulture-mock` | Outputs, workdirs, PyWPS log + sqlite |

## Endpoints

- `GET/POST /wps` — WPS 1.0.0 and 2.0.0 (KVP or XML)
- `GET /outputs/...` — outputs and async status documents
- `GET /health`, `GET /` (landing page with example requests)

## Front-end example (async)

```js
const WPS = "https://vulture-mock.onrender.com/wps";
const params = new URLSearchParams({
  service: "WPS", version: "1.0.0", request: "Execute",
  identifier: "PlotClimateStripes",
  DataInputs: "latitude=51.57;longitude=-1.31;start_year=1901;end_year=2022;n_colours=20",
  storeExecuteResponse: "true", status: "true",
});
const xml = new DOMParser().parseFromString(
  await (await fetch(`${WPS}?${params}`)).text(), "text/xml");
const statusUrl = xml.documentElement.getAttribute("statusLocation");
// poll statusUrl until wps:ProcessSucceeded / wps:ProcessFailed,
// then read wps:Reference/@href for "output" (PDF) and "png_output" (PNG)
```

## Differences from upstream worth knowing

- Mock data is not real climate data — don't use the figures for anything.
- `CFCheck` never downloads the URL, so unreachable URLs still "succeed".
- `CFVersion=auto` always resolves to CF-1.8 (the real service reads the file's `Conventions`).
- If the chosen time range doesn't overlap the 1901–2000 reference period, the mock uses the
  whole selected range as the reference (the real code would produce NaNs).
- The PNG is embedded in the PDF as a data URI, because current xhtml2pdf refuses to read
  files outside the working directory.
- `vulture/__init__.py` no longer enforces the cfchecker version match.

Licence: Apache 2.0, as upstream.
