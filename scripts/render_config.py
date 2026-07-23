#!/usr/bin/env python3
"""Render an importable Shadowrocket configuration from the tracked template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Shadowrocket.template.conf"
DEFAULT_OUTPUT = ROOT / "Shadowrocket.conf"
UPDATE_URL_MARKER = "# __UPDATE_URL__"
RULES_SNAPSHOT_MARKER = "# __RULES_SNAPSHOT__"
MANIFEST = ROOT / "rules" / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-url",
        help=(
            "Optional public HTTP(S) URL for future configuration updates. "
            "Do not pass a node subscription URL here."
        ),
    )
    parser.add_argument(
        "--rules-base-url",
        help=(
            "Optional raw base URL for vendored rules, for example "
            "https://raw.githubusercontent.com/owner/repo/main/rules."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    update_line = "# No update-url: import this local file directly."
    if args.update_url:
        parsed = urlparse(args.update_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SystemExit("Update URL must be an absolute HTTP(S) URL.")
        update_line = f"update-url = {args.update_url}"

    rules_base_url: str | None = None
    if args.rules_base_url:
        parsed = urlparse(args.rules_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SystemExit("Rules base URL must be an absolute HTTP(S) URL.")
        rules_base_url = args.rules_base_url.rstrip("/")

    output = args.output.expanduser().resolve()
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite {output}; pass --force to replace it.")

    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(UPDATE_URL_MARKER) != 1:
        raise SystemExit("Template update-url marker is missing or duplicated.")
    if template.count(RULES_SNAPSHOT_MARKER) != 1:
        raise SystemExit("Template rules snapshot marker is missing or duplicated.")

    snapshot_line = "# Rules snapshot: upstream live URLs"
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        digest = manifest.get("aggregate_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise SystemExit("rules/manifest.json has an invalid aggregate digest.")
        snapshot_line = f"# Rules snapshot: {digest}"

    rendered = template.replace(UPDATE_URL_MARKER, update_line).replace(
        RULES_SNAPSHOT_MARKER, snapshot_line
    )
    if rules_base_url:
        rewritten: list[str] = []
        for line in rendered.splitlines():
            if line.startswith("RULE-SET,https://"):
                kind, source, policy = line.split(",", 2)
                filename = Path(urlparse(source).path).name
                line = f"{kind},{rules_base_url}/{filename},{policy}"
            rewritten.append(line)
        rendered = "\n".join(rewritten) + "\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {output}")
    print("Add your node subscription separately in Shadowrocket before selecting policies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
