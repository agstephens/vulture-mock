"""
CFCheck process - MOCK version.

The inputs, outputs, identifier and metadata are identical to cedadev/vulture.
The handler does NOT download or open any NetCDF file and does NOT run the real
cfchecker; it produces a realistic-looking CF-Checker report instead.

Scenario hooks (based on the file name/URL/path supplied):
  - contains "error" or "bad"   -> report includes ERRORS
  - contains "warn"             -> report includes WARNINGS
  - contains "fail"             -> the process raises a ProcessError (like an unreadable file)
  - anything else               -> clean report
"""
import os
import posixpath

from pywps import LiteralInput, Process, FORMATS, ComplexOutput
from pywps.app.Common import Metadata
from pywps.app.exceptions import ProcessError

from ..utils import get_input, resolve_conventions_version
from ..mock_data import pause

import logging
LOGGER = logging.getLogger("PYWPS")

CFCHECKER_VERSION = "4.1.0"


class CFCheck(Process):
    def __init__(self):
        inputs = [
            LiteralInput(
                "CFVersion",
                "CF Version",
                abstract=("Version of the CF Conventions that the NetCDF file should be checked against. "
                          "E.g.: auto, 1.6, 1.7, 1.8."),
                allowed_values=["auto", "1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8"],
                data_type="string",
                default="auto",
                min_occurs=1,
                max_occurs=1
            ),
            LiteralInput(
                "NetCDFFileURL",
                "NetCDF File URL",
                abstract="URL to a NetCDF file accessible via the internet.",
                data_type="string",
                min_occurs=0,
                max_occurs=1
            ),
            LiteralInput(
                "NetCDFFileUpload",
                "NetCDF File Upload",
                abstract="You may upload a NetCDF file to this service using this loader.",
                data_type="string",
                min_occurs=0,
                max_occurs=1
            ),
            LiteralInput(
                "NetCDFFilePath",
                "NetCDF File Path",
                abstract="A file path pointing to a NetCDF file in the CEDA Archive.",
                data_type="string",
                min_occurs=0,
                max_occurs=1
            ),
        ]

        outputs = [
            ComplexOutput('output', 'Output',
                          abstract='Outputs from the CF-Checker',
                          as_reference=True,
                          supported_formats=[FORMATS.TEXT])]

        super(CFCheck, self).__init__(
            self._handler,
            identifier="CFCheck",
            title="CF-Checker",
            abstract="Run the CF-Checker on a NetCDF file.",
            keywords=['check', 'cf', 'conventions', 'climate', 'forecasts', 'checking', 'standards',
                      'ocean', 'atmosphere'],
            metadata=[
                Metadata('CEDA WPS UI', 'https://ceda-wps-ui.ceda.ac.uk'),
                Metadata('CEDA WPS', 'https://ceda-wps.ceda.ac.uk'),
                Metadata('CF-Checker source', 'https://github.com/cedadev/cf-checker'),
                Metadata('CF Conventions', 'https://cfconventions.org/'),
                Metadata('Disclaimer', 'https://help.ceda.ac.uk/article/4642-disclaimer')
            ],
            version='1.0.0',
            inputs=inputs,
            outputs=outputs,
            store_supported=True,
            status_supported=True
        )

    def _get_nc_path(self, inputs):
        """MOCK: pick the input the same way as the real service, but don't fetch anything."""
        nc_url = get_input(inputs, "NetCDFFileURL")
        nc_file_upload = get_input(inputs, "NetCDFFileUpload")
        nc_file_path = get_input(inputs, "NetCDFFilePath")

        if nc_url:
            # Real service downloads to <workdir>/testfile.nc
            return os.path.join(self.workdir, "testfile.nc"), nc_url
        elif nc_file_upload:
            return nc_file_upload, nc_file_upload
        elif nc_file_path:
            return nc_file_path, nc_file_path
        raise Exception()

    def _handler(self, request, response):
        response.update_status('Job is now running', 0)

        try:
            nc_path, source = self._get_nc_path(request.inputs)
        except Exception:
            raise ProcessError(("User must provide one input from: NetCDFFileURL, "
                                "NetCDFFileUpload or NetCDFFilePath."))

        name = posixpath.basename(source.split("?")[0]).lower()
        if "fail" in name:
            raise ProcessError('Cannot read NetCDF file')

        response.update_status('Reading NetCDF file (mock)', 20)
        pause()

        version = resolve_conventions_version(request.inputs, nc_path)
        response.update_status('Running CF-Checker (mock)', 50)
        pause()

        output = make_mock_report(nc_path, version, name)
        output_file = os.path.join(self.workdir, 'cfchecker_output.txt')
        with open(output_file, "w") as fout:
            fout.write(output)

        response.update_status('CF-Checks completed', 90)
        LOGGER.info(f'Written output file: {output_file}')
        response.outputs['output'].file = output_file
        return response


def make_mock_report(nc_path, version, name):
    errors, warnings, info = [], [], []

    if "error" in name or "bad" in name:
        errors = [
            ("tas", "(3.3): Invalid standard_name: air_temp"),
            ("time", "(4.4): Invalid units: days since"),
        ]
    if "warn" in name:
        warnings = [
            ("global", "(2.6.2): No 'history' global attribute"),
            ("lat", "(3.1): No 'units' attribute; assumed dimensionless"),
        ]

    def section(var):
        lines = ["", "------------------", f"Checking variable: {var}", "------------------"]
        for v, msg in errors:
            if v == var:
                lines.append(f"ERROR: {msg}")
        for v, msg in warnings:
            if v == var:
                lines.append(f"WARN: {msg}")
        return lines

    lines = [
        f"CHECKING NetCDF FILE: {nc_path}",
        "=====================",
        f"Using CF Checker Version {CFCHECKER_VERSION}",
        f"Checking against CF Version {version}",
        "Using Standard Name Table Version 84 (2024-01-19T15:55:10Z)",
        "Using Area Type Table Version 11 (06 July 2023)",
        "Using Standardized Region Name Table Version 5 (16 December 2022)",
        "",
    ]
    for v, msg in warnings:
        if v == "global":
            lines.append(f"WARN: {msg}")
    for var in ("lat", "lon", "tas", "time"):
        lines.extend(section(var))

    lines += [
        "",
        f"ERRORS detected: {len(errors)}",
        f"WARNINGS given: {len([w for w in warnings])}",
        f"INFORMATION messages: {len(info)}",
        "",
        "[MOCK] This report was generated by vulture-mock; no file was actually checked.",
        "",
    ]
    return "\n".join(lines)
