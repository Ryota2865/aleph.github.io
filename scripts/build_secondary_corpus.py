"""Build a tiny secondary corpus for transmutation pilots.

Usage examples:
  uv run python scripts/build_secondary_corpus.py law --sample
  uv run python scripts/build_secondary_corpus.py rfc --sample
  uv run python scripts/build_secondary_corpus.py law --limit 20
  uv run python scripts/build_secondary_corpus.py rfc --limit 20
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "corpus" / "secondary" / "works.jsonl"

EGOV_API_BASE = "https://laws.e-gov.go.jp/api/1"
RFC_BASE = "https://www.rfc-editor.org/rfc"

SAMPLE_LAWS = [
    {
        "id": "sample-law:constitution-1",
        "title": "日本国憲法（抄）",
        "author": "e-Gov 法令検索",
        "text": (
            "第一条　天皇は、日本国の象徴であり日本国民統合の象徴であつて、"
            "この地位は、主権の存する日本国民の総意に基く。\n"
            "第二条　皇位は、世襲のものであつて、国会の議決した皇室典範の"
            "定めるところにより、これを継承する。"
        ),
        "meta": {
            "source": "e-Gov 法令API sample fragment",
            "law_id": "321CONSTITUTION",
            "law_no": "昭和二十一年憲法",
        },
    },
    {
        "id": "sample-law:civil-code-1",
        "title": "民法（抄）",
        "author": "e-Gov 法令検索",
        "text": (
            "第一条　私権は、公共の福祉に適合しなければならない。\n"
            "２　権利の行使及び義務の履行は、信義に従い誠実に行わなければならない。\n"
            "３　権利の濫用は、これを許さない。"
        ),
        "meta": {
            "source": "e-Gov 法令API sample fragment",
            "law_id": "129AC0000000089",
            "law_no": "明治二十九年法律第八十九号",
        },
    },
    {
        "id": "sample-law:admin-procedure-1",
        "title": "行政手続法（抄）",
        "author": "e-Gov 法令検索",
        "text": (
            "第一条　この法律は、処分、行政指導及び届出に関する手続並びに"
            "命令等を定める手続に関し、共通する事項を定めることによつて、"
            "行政運営における公正の確保と透明性の向上を図ることを目的とする。\n"
            "第二条　この法律において「法令」とは、法律、法律に基づく命令、"
            "条例及び地方公共団体の執行機関の規則をいう。"
        ),
        "meta": {
            "source": "e-Gov 法令API sample fragment",
            "law_id": "405AC0000000088",
            "law_no": "平成五年法律第八十八号",
        },
    },
]

SAMPLE_RFCS = [
    {
        "id": "sample-rfc:2119",
        "title": "RFC 2119: Key words for use in RFCs to Indicate Requirement Levels",
        "author": "RFC Editor",
        "text": (
            "Abstract\n\n"
            "In many standards track documents several words are used to signify the "
            "requirements in the specification. These words are often capitalized.\n\n"
            "1. MUST\n\n"
            "This word, or the terms REQUIRED or SHALL, mean that the definition is an "
            "absolute requirement of the specification.\n\n"
            "3. SHOULD\n\n"
            "This word means that there may exist valid reasons in particular "
            "circumstances to ignore a particular item."
        ),
        "meta": {"source": "RFC Editor sample fragment", "rfc_number": 2119},
    },
    {
        "id": "sample-rfc:8446",
        "title": "RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3",
        "author": "RFC Editor",
        "text": (
            "Abstract\n\n"
            "This document specifies version 1.3 of the Transport Layer Security (TLS) "
            "protocol.\n\n"
            "1. Introduction\n\n"
            "TLS allows client/server applications to communicate over the Internet in "
            "a way that is designed to prevent eavesdropping, tampering, and message "
            "forgery.\n\n"
            "4.2. Extensions\n\n"
            "Implementations MUST NOT send extension responses if the remote endpoint "
            "did not send the corresponding extension requests."
        ),
        "meta": {"source": "RFC Editor sample fragment", "rfc_number": 8446},
    },
    {
        "id": "sample-rfc:9110",
        "title": "RFC 9110: HTTP Semantics",
        "author": "RFC Editor",
        "text": (
            "Abstract\n\n"
            "The Hypertext Transfer Protocol (HTTP) is a stateless application-level "
            "request/response protocol.\n\n"
            "1. Introduction\n\n"
            "HTTP provides a uniform interface for interacting with a resource.\n\n"
            "9.3.1. GET\n\n"
            "The GET method requests transfer of a current selected representation "
            "for the target resource. A client SHOULD NOT generate content in a GET "
            "request unless it is made directly to an origin server."
        ),
        "meta": {"source": "RFC Editor sample fragment", "rfc_number": 9110},
    },
]

RFC_NUMBERS = [
    768,
    791,
    792,
    793,
    821,
    822,
    1122,
    1459,
    1738,
    1945,
    2119,
    3986,
    5246,
    6749,
    7231,
    7540,
    8446,
    9000,
    9110,
    9114,
]

RFC_TITLES = {
    768: "User Datagram Protocol",
    791: "Internet Protocol",
    792: "Internet Control Message Protocol",
    793: "Transmission Control Protocol",
    821: "Simple Mail Transfer Protocol",
    822: "Standard for the Format of ARPA Internet Text Messages",
    1122: "Requirements for Internet Hosts - Communication Layers",
    1459: "Internet Relay Chat Protocol",
    1738: "Uniform Resource Locators (URL)",
    1945: "Hypertext Transfer Protocol -- HTTP/1.0",
    2119: "Key words for use in RFCs to Indicate Requirement Levels",
    3986: "Uniform Resource Identifier (URI): Generic Syntax",
    5246: "The Transport Layer Security (TLS) Protocol Version 1.2",
    6749: "The OAuth 2.0 Authorization Framework",
    7231: "Hypertext Transfer Protocol (HTTP/1.1): Semantics and Content",
    7540: "Hypertext Transfer Protocol Version 2 (HTTP/2)",
    8446: "The Transport Layer Security (TLS) Protocol Version 1.3",
    9000: "QUIC: A UDP-Based Multiplexed and Secure Transport",
    9110: "HTTP Semantics",
    9114: "HTTP/3",
}

LAW_BLOCK_TAGS = {
    "LawTitle",
    "PartTitle",
    "ChapterTitle",
    "SectionTitle",
    "SubsectionTitle",
    "DivisionTitle",
    "ArticleCaption",
    "ArticleTitle",
    "Paragraph",
    "Item",
    "Subitem1",
    "Subitem2",
    "Sentence",
    "SupplProvision",
    "AppdxTableTitle",
}


def _url_text(url: str, *, timeout: float) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ALEPH secondary corpus pilot/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(element: ET.Element, name: str) -> str:
    for child in element.iter():
        if _local_name(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _find_first(element: ET.Element, names: set[str]) -> ET.Element | None:
    for child in element.iter():
        if _local_name(child.tag) in names:
            return child
    return None


def _xml_plain_text(element: ET.Element) -> str:
    pieces: list[str] = []

    def add_text(value: str | None) -> None:
        if value and value.strip():
            pieces.append(re.sub(r"\s+", " ", value.strip()))

    def walk(node: ET.Element) -> None:
        name = _local_name(node.tag)
        if name in LAW_BLOCK_TAGS:
            pieces.append("\n")
        add_text(node.text)
        for child in node:
            walk(child)
            add_text(child.tail)
        if name in LAW_BLOCK_TAGS:
            pieces.append("\n")

    walk(element)
    text = " ".join(pieces)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_law_text(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    body = _find_first(root, {"LawFullText", "LawContents", "Law"})
    if body is None:
        body = root
    return _xml_plain_text(body)


def _law_list(law_type: str, *, timeout: float) -> list[dict]:
    xml_text = _url_text(f"{EGOV_API_BASE}/lawlists/{law_type}", timeout=timeout)
    root = ET.fromstring(xml_text)
    infos = []
    for info in root.iter():
        if _local_name(info.tag) != "LawNameListInfo":
            continue
        infos.append(
            {
                "law_id": _first_text(info, "LawId"),
                "title": _first_text(info, "LawName"),
                "law_no": _first_text(info, "LawNo"),
                "promulgation_date": _first_text(info, "PromulgationDate"),
            }
        )
    return [info for info in infos if info["law_id"] and info["title"]]


def _fetch_law_record(info: dict, *, timeout: float, max_chars: int) -> dict | None:
    law_id = info["law_id"]
    quoted = urllib.parse.quote(law_id, safe="")
    xml_text = _url_text(f"{EGOV_API_BASE}/lawdata/{quoted}", timeout=timeout)
    text = _extract_law_text(xml_text)
    if not text:
        return None
    if max_chars and len(text) > max_chars:
        return None
    return {
        "id": f"law:{law_id}",
        "title": info["title"],
        "author": "e-Gov 法令検索",
        "text": text,
        "corpus": "secondary",
        "form_type": "law",
        "meta": {
            "source": "e-Gov 法令API Version 1",
            "law_id": law_id,
            "law_no": info.get("law_no", ""),
            "promulgation_date": info.get("promulgation_date", ""),
            "source_url": f"{EGOV_API_BASE}/lawdata/{quoted}",
        },
    }


def build_law_records(args: argparse.Namespace) -> list[dict]:
    if args.sample:
        return [_with_secondary_fields(record, "law") for record in SAMPLE_LAWS[: args.limit]]

    records = []
    candidates = _law_list(args.law_type, timeout=args.timeout)
    for info in candidates[: args.max_candidates]:
        if len(records) >= args.limit:
            break
        try:
            record = _fetch_law_record(info, timeout=args.timeout, max_chars=args.max_chars)
        except (ET.ParseError, OSError, TimeoutError, UnicodeDecodeError) as exc:
            print(f"skip law {info.get('law_id')}: {exc}")
            continue
        if record is not None:
            records.append(record)
    return records


def _clean_rfc_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    text = re.sub(r"\n[^\n]*\s+\[Page \d+\]\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def _fetch_rfc_record(number: int, *, timeout: float, max_chars: int) -> dict:
    url = f"{RFC_BASE}/rfc{number}.txt"
    text = _clean_rfc_text(_url_text(url, timeout=timeout))
    truncated = False
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rstrip()
        truncated = True
    title = RFC_TITLES.get(number, f"RFC {number}")
    return {
        "id": f"rfc:{number}",
        "title": f"RFC {number}: {title}",
        "author": "RFC Editor",
        "text": text,
        "corpus": "secondary",
        "form_type": "rfc",
        "meta": {
            "source": "RFC Editor",
            "rfc_number": number,
            "source_url": url,
            "truncated": truncated,
        },
    }


def build_rfc_records(args: argparse.Namespace) -> list[dict]:
    if args.sample:
        return [_with_secondary_fields(record, "rfc") for record in SAMPLE_RFCS[: args.limit]]

    records = []
    for number in RFC_NUMBERS[: args.limit]:
        try:
            records.append(_fetch_rfc_record(number, timeout=args.timeout, max_chars=args.max_chars))
        except (OSError, TimeoutError, UnicodeDecodeError) as exc:
            print(f"skip rfc {number}: {exc}")
    return records


def _with_secondary_fields(record: dict, form_type: str) -> dict:
    return {**record, "corpus": "secondary", "form_type": form_type}


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_records(records: list[dict], path: Path, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if replace:
        merged = records
    else:
        form_types = {record.get("form_type") for record in records}
        existing = [
            record
            for record in _load_existing(path)
            if record.get("form_type") not in form_types
        ]
        merged = existing + records

    with path.open("w", encoding="utf-8") as f:
        for record in merged:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sample", action="store_true", help="write bundled 3-record sample data")
    parser.add_argument("--limit", type=int, default=20, help="maximum records for this form type")
    parser.add_argument("--out", type=Path, default=OUT_PATH, help="output works.jsonl path")
    parser.add_argument("--replace", action="store_true", help="replace output instead of merging form types")
    parser.add_argument("--timeout", type=float, default=30.0, help="network timeout in seconds")
    parser.add_argument("--max-chars", type=int, default=20000, help="skip or trim records beyond this size")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    law = subparsers.add_parser("law", help="fetch short Japanese laws from e-Gov")
    _add_common_args(law)
    law.add_argument("--law-type", default="1", choices=("1", "2", "3", "4"), help="e-Gov law type")
    law.add_argument("--max-candidates", type=int, default=200, help="law list candidates to probe")
    law.set_defaults(builder=build_law_records)

    rfc = subparsers.add_parser("rfc", help="fetch representative RFC text files")
    _add_common_args(rfc)
    rfc.set_defaults(builder=build_rfc_records)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = args.builder(args)
    write_records(records, args.out, replace=args.replace)
    print(f"wrote {len(records)} {args.command} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
