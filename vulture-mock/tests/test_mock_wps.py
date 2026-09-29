import os

os.environ.setdefault("MOCK_DELAY_SECONDS", "0")
os.environ.setdefault("DATA_DIR", "/tmp/vulture-mock-tests")

import pytest  # noqa: E402
from werkzeug.test import Client  # noqa: E402

from vulture.wsgi import application  # noqa: E402

EXEC = "/wps?service=WPS&version=1.0.0&request=Execute&identifier={}&DataInputs={}"


@pytest.fixture
def client():
    return Client(application)


def body(resp):
    return resp.get_data(as_text=True)


def test_capabilities_lists_all_processes(client):
    xml = body(client.get("/wps?service=WPS&request=GetCapabilities"))
    for ident in ("CFCheck", "PlotClimateStripes", "PlotClimateStripesGlobal"):
        assert f"<ows:Identifier>{ident}</ows:Identifier>" in xml


def test_uk_stripes_success(client):
    xml = body(client.get(EXEC.format("PlotClimateStripes", "latitude=51.57;longitude=-1.31")))
    assert "ProcessSucceeded" in xml
    assert "stripes.pdf" in xml and "stripes.png" in xml


def test_uk_stripes_outside_uk_fails(client):
    xml = body(client.get(EXEC.format("PlotClimateStripes", "latitude=40.0;longitude=-1.31")))
    assert "outside the HadUK-Grid coverage" in xml


def test_global_stripes_ocean_fails(client):
    xml = body(client.get(EXEC.format("PlotClimateStripesGlobal", "latitude=0;longitude=-150")))
    assert "returned no valid data" in xml


def test_cfcheck_requires_an_input(client):
    xml = body(client.get(EXEC.format("CFCheck", "CFVersion=auto")))
    assert "User must provide one input" in xml


def test_cfcheck_report_scenarios(client):
    xml = body(client.get(EXEC.format("CFCheck", "CFVersion=1.7;NetCDFFilePath=/badc/bad.nc")))
    assert "ProcessSucceeded" in xml
    url = xml.split('href="')[1].split('"')[0].split("/outputs/", 1)[1]
    report = body(client.get("/outputs/" + url))
    assert "ERRORS detected: 2" in report
    assert "CF-1.7" in report


def test_cors_preflight(client):
    resp = client.options("/wps", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
