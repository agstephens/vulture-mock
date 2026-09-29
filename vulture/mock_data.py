"""
Synthetic stand-ins for the CEDA archive datasets used by vulture.

The real service reads:
  - HadUK-Grid tas (1836-2022) via a kerchunk reference file  -> PlotClimateStripes
  - CRU TS 4.08 tmp (1901-2023) from NetCDF on /badc          -> PlotClimateStripesGlobal

Here we generate deterministic annual-mean temperature series so the same request
always returns the same stripes. Shapes roughly follow observed warming
(flat-ish to ~1970, then ~0.025 C/yr), plus seeded year-to-year noise.
"""
import hashlib
import os
import time

import numpy as np

UK_YEARS = (1836, 2022)
GLOBAL_YEARS = (1901, 2023)

# Rough bounding box of the HadUK-Grid domain
UK_BBOX = {"lat": (49.9, 60.9), "lon": (-8.2, 1.8)}

# Points in these boxes return all-NaN (as CRU TS does over ocean / Antarctica),
# so front ends can exercise the "no valid data" error path in PlotClimateStripesGlobal.
# (lat_min, lat_max, lon_min, lon_max)
MOCK_NO_DATA_BOXES = [
    (-90.0, -60.0, -180.0, 180.0),   # Antarctica (not in CRU TS)
    (-40.0, 40.0, -170.0, -120.0),   # central Pacific
    (-40.0, 40.0, -40.0, -20.0),     # mid Atlantic
    (-40.0, 0.0, 60.0, 90.0),        # Indian Ocean
]


def _rng(lat, lon, salt=""):
    key = f"{round(float(lat), 2)}:{round(float(lon), 2)}:{salt}".encode()
    seed = int(hashlib.sha256(key).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def _warming(years):
    years = np.asarray(years, dtype=float)
    early = 0.003 * (years - years[0])
    late = np.where(years > 1970, 0.025 * (years - 1970), 0.0)
    return early + late


def in_uk(lat, lon):
    return (UK_BBOX["lat"][0] <= lat <= UK_BBOX["lat"][1]
            and UK_BBOX["lon"][0] <= lon <= UK_BBOX["lon"][1])


def approx_bng(lat, lon):
    """Very rough lat/lon -> British National Grid (metres), for display only."""
    easting = 400000 + (lon + 2.0) * 69000 * np.cos(np.radians(lat))
    northing = -100000 + (lat - 49.0) * 111000
    return float(round(easting, -3)), float(round(northing, -3))


def uk_series(lat, lon):
    years = np.arange(UK_YEARS[0], UK_YEARS[1] + 1)
    baseline = 9.3 - 0.45 * (lat - 51.5) + 0.15 * (lon + 1.0)
    noise = _rng(lat, lon, "uk").normal(0, 0.45, len(years))
    return years, baseline + _warming(years) + noise


def global_series(lat, lon):
    years = np.arange(GLOBAL_YEARS[0], GLOBAL_YEARS[1] + 1)
    for lat0, lat1, lon0, lon1 in MOCK_NO_DATA_BOXES:
        if lat0 <= lat <= lat1 and lon0 <= lon <= lon1:
            return years, np.full(len(years), np.nan)
    baseline = 28.0 - 0.5 * abs(lat)
    # higher latitudes warm faster (Arctic amplification, roughly)
    amplification = 1.0 + abs(lat) / 60.0
    noise = _rng(lat, lon, "global").normal(0, 0.35, len(years))
    return years, baseline + amplification * _warming(years) + noise


def pause(seconds=None):
    """
    Simulate processing time so async status polling can be exercised.
    Controlled by MOCK_DELAY_SECONDS (default 1.5s per step, 0 to disable).
    """
    if seconds is None:
        seconds = float(os.environ.get("MOCK_DELAY_SECONDS", "1.5"))
    if seconds > 0:
        time.sleep(seconds)
