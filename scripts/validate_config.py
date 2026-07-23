#!/usr/bin/env python3
"""Validate Shadowrocket syntax, policy references, and rule precedence."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "Shadowrocket.conf"
REQUIRED_SECTIONS = ("General", "Proxy", "Proxy Group", "Rule", "Host")
BUILTIN_POLICIES = {"DIRECT", "REJECT", "PROXY"}
SECTION_RE = re.compile(r"^\[([^]]+)]$")
URL_RE = re.compile(r"https?://[^,\s]+")
EXPECTED_GROUP_DEFAULTS = {
    "🤖 AI 服务": "🚀 节点选择 1",
    "✨ Gemini": "🚀 节点选择 1",
    "🔍 谷歌服务": "🚀 节点选择 1",
    "📈 券商服务": "🚀 节点选择 2",
    "💳 支付平台": "🚀 节点选择 2",
    "₿ 加密货币": "🚀 节点选择 2",
}
DYNAMIC_SELECTOR_GROUPS = {"🚀 节点选择 1", "🚀 节点选择 2"}

# Each left-hand marker must occur before the right-hand marker. These checks
# encode the intentional exceptions to otherwise broad Google/Apple/country sets.
PRECEDENCE_PAIRS = (
    ("DOMAIN,shortconn.im.qcloud.com,🔒 国内服务", "HK_Broker.list,📈 券商服务"),
    ("BlockHttpDNS.list,🧱 DNS 防泄露", "Advertising.list,🛑 广告拦截"),
    ("DOMAIN,gemini.google.com,✨ Gemini", "Google.list,🔍 谷歌服务"),
    ("AI.list,🤖 AI 服务", "Google.list,🔍 谷歌服务"),
    ("ApplePush.list,🍎 苹果推送", "Apple.list,🍏 苹果服务"),
    ("YouTube.list,📹 油管视频", "China.list,🔒 国内服务"),
    ("PayPal.list,💳 支付平台", "Global.list,🌍 非中国"),
    ("Binance.list,₿ 加密货币", "Global.list,🌍 非中国"),
)


def parse(path: Path) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section_match = SECTION_RE.match(line)
        if section_match:
            current = section_match.group(1)
            if current in sections:
                raise ValueError(f"line {number}: duplicate section [{current}]")
            sections[current] = []
            order.append(current)
            continue
        if current is None:
            raise ValueError(f"line {number}: value appears before the first section")
        sections[current].append(line)
    return sections, order


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
        sections, section_order = parse(path)
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"cannot parse {path}: {exc}"]

    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    if missing:
        errors.append(f"missing sections: {', '.join(missing)}")
    present_required = [name for name in section_order if name in REQUIRED_SECTIONS]
    if present_required != list(REQUIRED_SECTIONS):
        errors.append("required sections are not in Shadowrocket order")

    group_lines = sections.get("Proxy Group", [])
    groups: dict[str, str] = {}
    for line in group_lines:
        if "=" not in line:
            errors.append(f"malformed proxy group: {line!r}")
            continue
        name, definition = (part.strip() for part in line.split("=", 1))
        if name in groups:
            errors.append(f"duplicate proxy group: {name}")
        if not definition.startswith(("select,", "url-test,", "fallback,")):
            errors.append(f"unsupported proxy group type for {name!r}")
        groups[name] = definition

    for name, expected_default in EXPECTED_GROUP_DEFAULTS.items():
        definition = groups.get(name)
        if definition is None:
            errors.append(f"missing proxy group: {name}")
            continue
        values = [part.strip() for part in definition.split(",")]
        actual_default = values[1] if len(values) > 1 else None
        if actual_default != expected_default:
            errors.append(
                f"proxy group {name!r} must default to {expected_default!r}"
            )

    for name in DYNAMIC_SELECTOR_GROUPS:
        definition = groups.get(name)
        if definition is None:
            errors.append(f"missing dynamic proxy group: {name}")
        elif "policy-regex-filter=.*" not in definition:
            errors.append(f"dynamic proxy group {name!r} must include all subscription nodes")

    known_policies = set(groups) | BUILTIN_POLICIES
    rules = sections.get("Rule", [])
    seen_rules: set[str] = set()
    for index, rule in enumerate(rules):
        if rule in seen_rules:
            errors.append(f"duplicate rule: {rule}")
        seen_rules.add(rule)
        parts = [part.strip() for part in rule.split(",")]
        if len(parts) < 2:
            errors.append(f"malformed rule: {rule!r}")
            continue
        policy = parts[1] if parts[0] == "FINAL" else parts[-1]
        if policy == "no-resolve" and len(parts) >= 4:
            policy = parts[-2]
        if policy not in known_policies:
            errors.append(f"rule {index + 1} references unknown policy {policy!r}")

    if not rules or not rules[-1].startswith("FINAL,"):
        errors.append("the final [Rule] entry must be FINAL")

    for before, after in PRECEDENCE_PAIRS:
        before_pos = text.find(before)
        after_pos = text.find(after)
        if before_pos < 0:
            errors.append(f"missing precedence marker: {before}")
        if after_pos < 0:
            errors.append(f"missing precedence marker: {after}")
        if before_pos >= 0 and after_pos >= 0 and before_pos >= after_pos:
            errors.append(f"rule order conflict: {before!r} must precede {after!r}")

    broad_markers = ("China.list,🔒 国内服务", "Global.list,🌍 非中国")
    broad_positions = [text.find(marker) for marker in broad_markers]
    if all(position >= 0 for position in broad_positions):
        first_broad = min(broad_positions)
        for marker in (
            "Telegram.list,📲 电报消息",
            "Twitter.list,🐦 推特/X",
            "Microsoft.list,Ⓜ️ 微软服务",
            "HK_Broker.list,📈 券商服务",
            "Apple.list,🍏 苹果服务",
        ):
            position = text.find(marker)
            if position < 0 or position >= first_broad:
                errors.append(f"specialized rule must precede country rules: {marker}")

    for rule in rules:
        if rule.startswith("RULE-SET,"):
            parts = rule.split(",")
            if len(parts) != 3 or not URL_RE.fullmatch(parts[1]):
                errors.append(f"invalid remote RULE-SET URL: {rule!r}")

    if ".mrs" in text or "rule-providers:" in text or "proxy-groups:" in text:
        errors.append("Mihomo-only syntax found in Shadowrocket configuration")
    if "__UPDATE_URL__" in text and path.name != "Shadowrocket.template.conf":
        errors.append("unrendered update-url marker")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    errors = validate(args.config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
