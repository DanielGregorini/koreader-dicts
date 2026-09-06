"""Licence compatibility. Getting this wrong ships an unlicensable file."""

from __future__ import annotations

import pytest
from kdicts.licensing import (
    IncompatibleLicenses,
    LicenseError,
    attribution_block,
    get_license,
    resolve_bundle_license,
)


def test_permissive_input_stays_permissive():
    """A bundle must not be relicensed more restrictively than it has to be."""
    assert resolve_bundle_license(["WordNet-3.0"]).id == "WordNet-3.0"
    assert resolve_bundle_license(["PD"]).id == "PD"


def test_wordnet_plus_share_alike_becomes_share_alike():
    assert resolve_bundle_license(["WordNet-3.0", "CC-BY-SA-4.0"]).id == "CC-BY-SA-4.0"


def test_attribution_only_input_does_not_become_share_alike():
    assert resolve_bundle_license(["WordNet-3.0", "CC-BY-4.0"]).id == "CC-BY-4.0"
    assert resolve_bundle_license(["WordNet-3.0", "CC-BY-3.0"]).id == "CC-BY-4.0"


def test_version_upgrade_is_allowed_downgrade_is_not():
    assert resolve_bundle_license(["CC-BY-SA-3.0", "CC-BY-SA-4.0"]).id == "CC-BY-SA-4.0"
    assert "CC-BY-SA-3.0" not in get_license("CC-BY-SA-4.0").outbound


def test_cecill_c_cannot_be_bundled_with_share_alike():
    """WOLF (French) is CeCILL-C. This is the case the spec calls out."""
    with pytest.raises(IncompatibleLicenses):
        resolve_bundle_license(["CC-BY-SA-4.0", "CECILL-C"])


def test_cecill_c_alone_with_permissive_material_is_fine():
    assert resolve_bundle_license(["WordNet-3.0", "CECILL-C"]).id == "CECILL-C"


def test_gpl_data_cannot_be_merged_into_a_cc_bundle():
    """GCIDE is GPL. It ships as its own bundle, never merged."""
    with pytest.raises(IncompatibleLicenses):
        resolve_bundle_license(["CC-BY-SA-4.0", "GPL-3.0-or-later"])


def test_noncommercial_is_excluded_outright():
    """PanLex's NC clause would poison everything it touched."""
    with pytest.raises(LicenseError, match="excluded"):
        resolve_bundle_license(["CC-BY-4.0", "CC-BY-NC-SA-4.0"])
    assert get_license("CC-BY-NC-SA-4.0").excluded
    assert not get_license("CC-BY-NC-SA-4.0").commercial_ok


def test_unknown_licence_fails_rather_than_defaulting():
    with pytest.raises(LicenseError, match="excluded"):
        resolve_bundle_license(["UNKNOWN"])
    with pytest.raises(LicenseError, match="unknown licence id"):
        resolve_bundle_license(["Definitely-Not-A-Licence"])


def test_empty_bundle_is_an_error():
    with pytest.raises(LicenseError):
        resolve_bundle_license([])


def test_omw_licence_set_resolves():
    """The licences actually present across OMW 1.4, minus the French one."""
    observed = [
        "CC-BY-SA-3.0", "CC-BY-SA-4.0", "CC-BY-3.0", "WordNet-3.0",
        "MIT", "Apache-2.0", "ODC-By-1.0",
    ]
    assert resolve_bundle_license(observed).id == "CC-BY-SA-4.0"
    with pytest.raises(IncompatibleLicenses):
        resolve_bundle_license([*observed, "CECILL-C"])


def test_attribution_block_carries_mandatory_notices():
    text = attribution_block(
        ["WordNet-3.0", "CC-BY-SA-4.0"],
        {"pwn30": "Princeton University WordNet 3.0", "omw-pt": "OpenWN-PT"},
    )
    assert "CC-BY-SA-4.0" in text or "ShareAlike" in text
    # The WordNet licence requires the copyright notice on modified copies.
    assert "Princeton University" in text
    assert "must be retained on all" in text
    assert "OpenWN-PT" in text
