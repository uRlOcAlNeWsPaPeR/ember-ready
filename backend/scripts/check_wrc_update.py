"""Read-only check: has USDA published a newer Wildfire Risk to Communities
release than the one EmberReady currently ships?

Makes no changes to the repo — it only reports. To actually pull a new
release, run `python -m scripts.fetch_static_layers` (which re-discovers
the current URL itself) and `python -m scripts.build_county_map_data`,
then commit and redeploy.

Run with: python -m scripts.check_wrc_update
Exit code: 0 if up to date or the check itself failed to run, 1 if a
newer release is available (so a scheduler can branch on it easily).
"""
from __future__ import annotations

import sys

from scripts.wrc_source import WrcSourceError, discover_current_download_url, load_known_source


def main() -> int:
    known = load_known_source()
    if known is None:
        print(
            "No recorded WRC source yet (backend/data/wrc_source_meta.json is missing). "
            "Run `python -m scripts.fetch_static_layers` once to establish a baseline."
        )
        return 0

    try:
        current_url = discover_current_download_url()
    except WrcSourceError as exc:
        print(f"Could not check for an update: {exc}")
        return 0

    if current_url == known["download_url"]:
        print(f"Up to date. Current WRC vintage: {known['vintage']} ({known['download_url']})")
        return 0

    print("NEW WRC RELEASE AVAILABLE")
    print(f"  Currently shipping: {known['vintage']} — {known['download_url']}")
    print(f"  Now published:      {current_url}")
    print()
    print("To pull it in: python -m scripts.fetch_static_layers && python -m scripts.build_county_map_data")
    print("Then review the diff, commit, and redeploy.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
