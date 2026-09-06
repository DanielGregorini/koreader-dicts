"""Licence identity, provenance and bundle compatibility.

Every emitted sense carries the licence of the source it came from. Merging is
only legal when one outbound licence exists that all contributing licences
allow their material to be redistributed under. When none exists the build
stops rather than write a file whose terms cannot be stated.

The model is a directed "relicensing" relation.  ``outbound`` lists the licence
ids a work under this licence may be redistributed under (always including
itself).  A set of licences is compatible iff the intersection of their
outbound sets is non-empty; the resulting bundle licence is the most
restrictive member of that intersection, chosen deterministically by
:data:`_RESTRICTIVENESS`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

__all__ = [
    "LICENSES",
    "IncompatibleLicenses",
    "License",
    "LicenseError",
    "attribution_block",
    "get_license",
    "resolve_bundle_license",
]


class LicenseError(Exception):
    """Base class for licence problems."""


class IncompatibleLicenses(LicenseError):
    """Raised when a set of sources cannot legally be merged."""

    def __init__(self, ids: Iterable[str]) -> None:
        self.ids = sorted(ids)
        super().__init__(
            "no single outbound licence covers all sources: "
            + ", ".join(self.ids)
            + " -- these must ship as separate bundles"
        )


@dataclass(frozen=True, slots=True)
class License:
    id: str
    name: str
    url: str
    #: True when the licence permits commercial redistribution.  A False here
    #: disqualifies the source from this project entirely (see PanLex).
    commercial_ok: bool
    #: True when downstream copies must carry the same licence.
    share_alike: bool
    #: True when copies must carry an attribution notice.
    attribution_required: bool
    #: Licence ids this licence's material may be redistributed under.
    outbound: frozenset[str] = field(default_factory=frozenset)
    #: Extra obligations that must appear verbatim in shipped packages.
    notice: str = ""
    #: Set for licences we refuse to ingest at all, with the reason.
    excluded_reason: str = ""

    @property
    def excluded(self) -> bool:
        return bool(self.excluded_reason)


def _lic(*, id: str, outbound: frozenset[str] = frozenset(), **kwargs: object) -> License:
    """Build a :class:`License`, ensuring it is always compatible with itself."""
    return License(id=id, outbound=frozenset(outbound) | {id}, **kwargs)  # type: ignore[arg-type]


_ALL: list[License] = [
    _lic(
        id="PD",
        name="Public domain",
        url="",
        commercial_ok=True,
        share_alike=False,
        attribution_required=False,
        outbound=frozenset({"CC0-1.0", "WordNet-3.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "GPL-3.0-or-later", "CECILL-C"}),
    ),
    _lic(
        id="CC0-1.0",
        name="Creative Commons Zero v1.0 Universal",
        url="https://creativecommons.org/publicdomain/zero/1.0/",
        commercial_ok=True,
        share_alike=False,
        attribution_required=False,
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "GPL-3.0-or-later", "CECILL-C"}),
    ),
    _lic(
        # Permissive, BSD-like, explicitly commercial-friendly and NOT copyleft.
        # The only real obligations are the notice and the advertising clause.
        id="WordNet-3.0",
        name="WordNet 3.0 License (Princeton University)",
        url="https://wordnet.princeton.edu/license-and-commercial-use",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "GPL-3.0-or-later", "CECILL-C"}),
        notice=(
            "WordNet Release 3.0 Copyright 2006 by Princeton University. "
            "All rights reserved. This copyright notice must be retained on all "
            "copies, including modified copies. The name of Princeton University "
            "or Princeton may not be used in advertising or publicity pertaining "
            "to distribution of the software and/or database without specific, "
            "written prior permission."
        ),
    ),
    _lic(
        id="CC-BY-4.0",
        name="Creative Commons Attribution 4.0 International",
        url="https://creativecommons.org/licenses/by/4.0/",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        # BY may be folded into BY-SA output; the reverse is not true.
        outbound=frozenset({"CC-BY-SA-4.0"}),
    ),
    _lic(
        id="CC-BY-3.0",
        name="Creative Commons Attribution 3.0",
        url="https://creativecommons.org/licenses/by/3.0/",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0"}),
    ),
    _lic(
        id="CC-BY-SA-3.0",
        name="Creative Commons Attribution-ShareAlike 3.0",
        url="https://creativecommons.org/licenses/by-sa/3.0/",
        commercial_ok=True,
        share_alike=True,
        attribution_required=True,
        # 3.0 -> 4.0 upgrade is permitted by the "later version" clause.
        outbound=frozenset({"CC-BY-SA-4.0"}),
    ),
    _lic(
        id="CC-BY-SA-4.0",
        name="Creative Commons Attribution-ShareAlike 4.0 International",
        url="https://creativecommons.org/licenses/by-sa/4.0/",
        commercial_ok=True,
        share_alike=True,
        attribution_required=True,
        # CC BY-SA 4.0 has a documented one-way compatibility with GPLv3, but we
        # deliberately do not model it: relicensing our whole corpus to GPL to
        # absorb one GPL source would be a bad trade and the resulting artifact
        # could never take BY-SA-only material again.  GPL data ships separately.
        outbound=frozenset(),
    ),
    _lic(
        id="GPL-3.0-or-later",
        name="GNU General Public License v3.0 or later",
        url="https://www.gnu.org/licenses/gpl-3.0.html",
        commercial_ok=True,
        share_alike=True,
        attribution_required=True,
        outbound=frozenset(),
    ),
    _lic(
        id="GPL-2.0-or-later",
        name="GNU General Public License v2.0 or later",
        url="https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
        commercial_ok=True,
        share_alike=True,
        attribution_required=True,
        outbound=frozenset({"GPL-3.0-or-later"}),
    ),
    _lic(
        id="CECILL-C",
        name="CeCILL-C Free Software License Agreement",
        url="https://cecill.info/licences/Licence_CeCILL-C_V1-en.html",
        commercial_ok=True,
        share_alike=True,
        attribution_required=True,
        # French copyleft, NOT a Creative Commons licence and not compatible
        # with CC BY-SA in either direction.  WOLF (fr) is under this.
        outbound=frozenset(),
        notice=(
            "Contains material from WOLF, distributed under the CeCILL-C licence. "
            "CeCILL-C material may not be redistributed under a Creative Commons "
            "ShareAlike licence."
        ),
    ),
    _lic(
        id="MIT",
        name="MIT License",
        url="https://opensource.org/licenses/MIT",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        # Permissive: material may go into a more restrictively licensed
        # compilation as long as the notice travels with it, which is what the
        # ATTRIBUTION file is for. Wordnet Bahasa (id, zsm) is under this.
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "GPL-3.0-or-later"}),
    ),
    _lic(
        id="Apache-2.0",
        name="Apache License 2.0",
        url="https://www.apache.org/licenses/LICENSE-2.0",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        # Apache 2.0 is one-way compatible with GPLv3 but not GPLv2, and its
        # notice and patent terms must survive into any compilation.
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-4.0", "GPL-3.0-or-later"}),
        notice=(
            "Contains material licensed under the Apache License, Version 2.0. "
            "The NOTICE and attribution requirements of that licence continue to "
            "apply to that material."
        ),
    ),
    _lic(
        id="ODC-By-1.0",
        name="Open Data Commons Attribution License v1.0",
        url="https://opendefinition.org/licenses/odc-by/",
        commercial_ok=True,
        share_alike=False,
        attribution_required=True,
        # A database licence with an attribution condition and no share-alike,
        # so derived databases may be released under other terms. ItalWordNet.
        outbound=frozenset({"CC-BY-4.0", "CC-BY-SA-4.0", "GPL-3.0-or-later"}),
    ),
    _lic(
        id="CC-BY-NC-SA-4.0",
        name="Creative Commons Attribution-NonCommercial-ShareAlike 4.0",
        url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
        commercial_ok=False,
        share_alike=True,
        attribution_required=True,
        outbound=frozenset(),
        excluded_reason=(
            "NonCommercial clause. It would poison every artifact it touched and "
            "makes the output undistributable by anyone who mirrors it "
            "commercially. PanLex is excluded on these grounds."
        ),
    ),
    _lic(
        id="UNKNOWN",
        name="Unknown / unparsed licence",
        url="",
        commercial_ok=False,
        share_alike=True,
        attribution_required=True,
        outbound=frozenset(),
        excluded_reason=(
            "Licence could not be determined from the source data. Refusing to "
            "guess. Declare it explicitly in the source config."
        ),
    ),
]

LICENSES: Mapping[str, License] = {lic.id: lic for lic in _ALL}

# Lower number == less restrictive.  Used to pick the bundle licence
# deterministically out of the compatible set: we always choose the *least*
# restrictive licence that covers every contributing source, so that permissive
# input stays permissive on the way out.
_RESTRICTIVENESS = {
    "PD": 0,
    "CC0-1.0": 1,
    "MIT": 2,
    "WordNet-3.0": 2,
    "Apache-2.0": 3,
    "ODC-By-1.0": 3,
    "CC-BY-3.0": 3,
    "CC-BY-4.0": 4,
    "CC-BY-SA-3.0": 5,
    "CC-BY-SA-4.0": 6,
    "CECILL-C": 7,
    "GPL-2.0-or-later": 8,
    "GPL-3.0-or-later": 9,
    "CC-BY-NC-SA-4.0": 98,
    "UNKNOWN": 99,
}


def get_license(license_id: str) -> License:
    try:
        return LICENSES[license_id]
    except KeyError:
        raise LicenseError(
            f"unknown licence id {license_id!r}; add it to kdicts.licensing "
            "rather than letting it default to something permissive"
        ) from None


def resolve_bundle_license(license_ids: Iterable[str]) -> License:
    """Return the least restrictive licence a bundle of *license_ids* may ship under.

    Raises :class:`LicenseError` for excluded licences and
    :class:`IncompatibleLicenses` when no single outbound licence exists.
    """
    ids = sorted(set(license_ids))
    if not ids:
        raise LicenseError("cannot resolve a bundle licence for zero sources")

    licenses = [get_license(i) for i in ids]
    for lic in licenses:
        if lic.excluded:
            raise LicenseError(f"source licence {lic.id} is excluded: {lic.excluded_reason}")

    candidates: set[str] | None = None
    for lic in licenses:
        outbound = set(lic.outbound) | {lic.id}
        candidates = outbound if candidates is None else (candidates & outbound)
    assert candidates is not None
    if not candidates:
        raise IncompatibleLicenses(ids)

    return get_license(min(candidates, key=lambda i: (_RESTRICTIVENESS.get(i, 99), i)))


def attribution_block(license_ids: Iterable[str], source_credits: Mapping[str, str]) -> str:
    """Human-readable attribution text for the shipped ATTRIBUTION file.

    *source_credits* maps a source id to the credit line the upstream project
    asks for.  Every licence notice that must appear verbatim is appended.
    """
    ids = sorted(set(license_ids))
    bundle = resolve_bundle_license(ids)
    lines = [
        f"This dictionary is distributed under {bundle.name} ({bundle.id}).",
        bundle.url,
        "",
        "It is built from the following sources:",
        "",
    ]
    for source_id, credit in sorted(source_credits.items()):
        lines.append(f"  * {source_id}: {credit}")
    lines.append("")
    for license_id in ids:
        lic = get_license(license_id)
        if lic.notice:
            lines.extend([f"-- {lic.name} --", lic.notice, ""])
    return "\n".join(lines).rstrip() + "\n"
