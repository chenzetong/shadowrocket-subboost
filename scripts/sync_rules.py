#!/usr/bin/env python3
"""Fetch and vendor every remote RULE-SET used by the Shadowrocket template."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "Shadowrocket.template.conf"
RULES_DIR = ROOT / "rules"
MANIFEST = RULES_DIR / "manifest.json"
RULE_SET_RE = re.compile(r"^RULE-SET,(https://[^,]+),", re.MULTILINE)
AUGMENT_SOURCES = {
    # The classical Apple.list currently contains UA/IP rules but omits the
    # ~1,550 domain rules advertised by its header. Merge the domain variant.
    "Apple.list": (
        "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/"
        "master/rule/Shadowrocket/Apple/Apple_Domain.list",
    ),
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "shadowrocket-subboost-rule-sync/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read()
        content_type = response.headers.get_content_type()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        if content_type == "text/html":
            raise RuntimeError(f"unexpected HTML response for {url}")
        return body


def normalize_rule_list(body: bytes, url: str) -> bytes:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"rule list is not UTF-8: {url}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    active_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", ";"))
    ]
    if not active_lines:
        raise RuntimeError(f"rule list has no active rules: {url}")
    if any("," not in line for line in active_lines):
        raise RuntimeError(f"rule list contains a malformed rule: {url}")
    return text.encode("utf-8")


def normalize_domain_set(body: bytes, url: str) -> bytes:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"domain set is not UTF-8: {url}") from exc
    converted: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            converted.append(raw_line)
        elif line.startswith("."):
            converted.append(f"DOMAIN-SUFFIX,{line[1:]}")
        elif "," in line:
            converted.append(line)
        else:
            converted.append(f"DOMAIN,{line}")
    content = ("\n".join(converted).rstrip() + "\n").encode("utf-8")
    return normalize_rule_list(content, url)


def merge_rule_lists(primary: bytes, supplements: list[tuple[str, bytes]]) -> bytes:
    lines = primary.decode("utf-8").rstrip().splitlines()
    seen = {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith(("#", ";"))
    }
    for source, content in supplements:
        lines.extend(("", f"# > Daily supplement: {source}"))
        for line in content.decode("utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")) or stripped in seen:
                continue
            lines.append(stripped)
            seen.add(stripped)
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def write_if_changed(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return True


def main() -> int:
    template = TEMPLATE.read_text(encoding="utf-8")
    urls = list(dict.fromkeys(RULE_SET_RE.findall(template)))
    if not urls:
        raise SystemExit("No remote RULE-SET URLs found in the template.")

    filenames: set[str] = set()
    entries: list[dict[str, object]] = []
    changed = 0
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    for url in urls:
        filename = Path(urlparse(url).path).name
        if not filename.endswith(".list"):
            raise SystemExit(f"RULE-SET URL does not end in .list: {url}")
        if filename in filenames:
            raise SystemExit(f"duplicate vendored rule filename: {filename}")
        filenames.add(filename)
        try:
            body = fetch(url)
            content = normalize_rule_list(body, url)
            supplement_contents: list[tuple[str, bytes]] = []
            source_urls = [url]
            for supplement_url in AUGMENT_SOURCES.get(filename, ()):
                supplement_body = fetch(supplement_url)
                supplement_contents.append(
                    (
                        supplement_url,
                        normalize_domain_set(supplement_body, supplement_url),
                    )
                )
                source_urls.append(supplement_url)
            if supplement_contents:
                content = merge_rule_lists(content, supplement_contents)
        except (OSError, RuntimeError, urllib.error.URLError) as exc:
            raise SystemExit(f"Failed to sync {url}: {exc}") from exc

        destination = RULES_DIR / filename
        changed += int(write_if_changed(destination, content))
        active_count = sum(
            1
            for line in content.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(("#", ";"))
        )
        entry: dict[str, object] = {
            "file": filename,
            "sources": source_urls,
            "sha256": hashlib.sha256(content).hexdigest(),
            "rules": active_count,
        }
        entries.append(entry)
        print(f"Synced {filename}: {active_count} rules")

    aggregate_input = "\n".join(
        f"{entry['file']}:{entry['sha256']}" for entry in entries
    ).encode("utf-8")
    manifest = {
        "schema": 1,
        "aggregate_sha256": hashlib.sha256(aggregate_input).hexdigest(),
        "sources": entries,
    }
    manifest_content = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    changed += int(write_if_changed(MANIFEST, manifest_content))
    print(f"Synchronized {len(entries)} sources; {changed} files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
