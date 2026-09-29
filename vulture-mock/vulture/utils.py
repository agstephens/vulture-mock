"""Utilities - MOCK version (no netCDF4 / cfchecker dependency)."""

NEWEST_VERSION = "CF-1.8"   # newest value exposed by the CFCheck allowed_values


def get_input(inputs, key, default=None):
    """
    Find the input in inputs dictionary, using key as lookup.
    """
    if key in inputs:
        return inputs[key][0].data

    return default


def resolve_conventions_version(inputs, nc_path):
    """
    MOCK: the real function opens the NetCDF file and reads its `Conventions`
    attribute when "auto" is selected. Here "auto" resolves to the newest version.
    """
    convention_version = get_input(inputs, "CFVersion", "auto")
    if not convention_version or convention_version == "auto":
        return NEWEST_VERSION
    return f"CF-{convention_version}"
