"""C-1改訂版（前半）: 青空文庫書誌からの era・言語・形式被覆の台帳直接計算.

PLAN_CHANGELOG 0.7.19 問2の決定——「持っている真値を推定し直さない」——の実装。
era軸・言語軸（＋NDC由来の形式軸）はクラスタリングにも埋め込みにも依存せず、
corpus/aozora/works.jsonl の meta（青空文庫マスター書誌）から直接計算できる。
埋め込み由来の注釈が必要なのは主題・視点など書誌に無い軸のみで、それらは
作品単位の層化サンプリング注釈（後半、別実装）が担う。

era は二本立てで報告する（真値の性格が異なるため混ぜない）:
- author_death_decade: 著者没年の年代。全PD作品でほぼ必ず存在する下界的な代理。
- first_publication_decade: 初出欄からパースできた発表年の年代。真の発表時期に
  最も近いが、欄が空・年不記載の作品では unknown になる（欠測は欠測と報告する）。
※ 底本初版発行年は「復刻・全集の刊行年」であり作品の時代の真値ではないため使わない。

Usage:
  uv run python scripts/corpus_coverage_metadata.py \
      --corpus corpus/aozora/works.jsonl --out reports/CORPUS_COVERAGE_METADATA_<date>.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# NDC 9xx の2桁目 → 言語圏（文学のみ。9以外の類は「文学外」として別掲する）
NDC_LANGUAGE = {
    "91": "日本文学",
    "92": "中国文学",
    "93": "英米文学",
    "94": "ドイツ文学",
    "95": "フランス文学",
    "96": "スペイン文学",
    "97": "イタリア文学",
    "98": "ロシア文学",
    "99": "その他の諸文学",
}

# NDC 9x? の3桁目 → 形式
NDC_FORM = {
    "0": "文学総記",
    "1": "詩歌",
    "2": "戯曲",
    "3": "小説・物語",
    "4": "評論・随筆",
    "5": "日記・書簡・紀行",
    "6": "記録・ルポルタージュ",
    "7": "箴言・風刺",
    "8": "作品集",
    "9": "その他",
}

_ERA_NAMES = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988}
_WESTERN_YEAR = re.compile(r"(1[6-9]\d\d|20[0-4]\d)")
_ERA_YEAR = re.compile(r"(明治|大正|昭和|平成)(\d{1,2})年")


def parse_ndc(raw: str) -> list[dict]:
    """分類番号欄（例: "NDC 913", "NDC K913", "NDC 914 915"）を構造化する.

    各コードについて {code, juvenile, language, form} を返す。9類以外
    （例: 723 絵画）は language/form とも None（文学外として集計側で別掲）。
    """
    results = []
    for token in (raw or "").replace("NDC", " ").split():
        juvenile = token.startswith("K")
        code = token[1:] if juvenile else token
        if not code.isdigit():
            continue
        language = form = None
        if len(code) == 3 and code[0] == "9":
            language = NDC_LANGUAGE.get(code[:2])
            form = NDC_FORM.get(code[2])
        results.append({"code": code, "juvenile": juvenile, "language": language, "form": form})
    return results


def parse_first_publication_year(raw: str) -> int | None:
    """初出欄の自由文から発表年（西暦）を推定する。無理はしない（不明はNone）.

    「1934（昭和9）年」のような併記は西暦を優先し、元号のみ（「昭和9年」）は換算する。
    """
    text = raw or ""
    m = _WESTERN_YEAR.search(text)
    if m:
        return int(m.group(1))
    m = _ERA_YEAR.search(text)
    if m:
        return _ERA_NAMES[m.group(1)] + int(m.group(2))
    return None


def decade(year: int | None) -> str:
    return f"{year // 10 * 10}s" if year is not None else "unknown"


def year_from_date(raw: str) -> int | None:
    head = (raw or "")[:4]
    return int(head) if head.isdigit() else None


def aggregate(rows: list[dict]) -> dict:
    """works.jsonl の meta 群から era/言語/形式の分布を集計する（作品単位）."""
    death = Counter()
    first_pub = Counter()
    language = Counter()
    form = Counter()
    non_literature = Counter()
    juvenile = 0
    total = 0
    for meta in rows:
        total += 1
        death[decade(year_from_date(meta.get("没年月日", "")))] += 1
        first_pub[decade(parse_first_publication_year(meta.get("初出", "")))] += 1
        codes = parse_ndc(meta.get("分類番号", ""))
        if any(c["juvenile"] for c in codes):
            juvenile += 1
        seen_lang: set[str] = set()
        seen_form: set[str] = set()
        for c in codes:
            if c["language"] is None:
                non_literature[c["code"]] += 1
            else:
                seen_lang.add(c["language"])
                if c["form"]:
                    seen_form.add(c["form"])
        if not codes:
            language["unknown"] += 1
        for value in seen_lang or ([] if codes else []):
            language[value] += 1
        for value in seen_form:
            form[value] += 1
    return {
        "total_works": total,
        "author_death_decade": dict(death),
        "first_publication_decade": dict(first_pub),
        "language": dict(language),
        "form": dict(form),
        "non_literature_codes": dict(non_literature),
        "juvenile_works": juvenile,
    }


def render_report(stats: dict, corpus_path: str) -> str:
    def table(counter: dict, title: str, note: str = "") -> list[str]:
        lines = [f"\n### {title}\n"]
        if note:
            lines.append(note + "\n")
        lines.append("| 値 | 作品数 | 比率 |")
        lines.append("|---|---|---|")
        total = stats["total_works"]
        for key, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| {key} | {count} | {count / total:.1%} |")
        return lines

    lines = [
        f"# コーパス属性被覆（台帳直接計算） {datetime.now():%Y-%m-%d}",
        "",
        f"- 台帳: `{corpus_path}`（作品単位 {stats['total_works']} 件）",
        "- 方式: 青空文庫マスター書誌からの直接計算（PLAN_CHANGELOG 0.7.19 問2）。",
        "  クラスタリング・埋め込み・LLM注釈を一切経由しない真値である。",
        "  主題・視点軸は本レポートの対象外（層化サンプリング注釈で別途測る）。",
    ]
    lines += table(
        stats["author_death_decade"],
        "era（著者没年の年代）",
        "PD作品の性質上ほぼ全件で存在する下界的代理。",
    )
    lines += table(
        stats["first_publication_decade"],
        "era（初出年の年代）",
        "初出欄からパースできた発表年。unknown は欄が空か年が読めない作品（欠測は欠測として報告）。",
    )
    lines += table(stats["language"], "言語圏（NDC 9xx の2桁目）")
    lines += table(stats["form"], "形式（NDC 9xx の3桁目）")
    lines.append(f"\n- 児童書（NDC K）: {stats['juvenile_works']} 件")
    non_lit = Counter(stats["non_literature_codes"])
    lines.append(
        f"- 文学外NDC: 全{sum(non_lit.values())}件・{len(non_lit)}分類。"
        f"上位: {dict(non_lit.most_common(12))}"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="corpus/aozora/works.jsonl")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    metas = []
    with open(args.corpus, encoding="utf-8") as f:
        for line in f:
            metas.append(json.loads(line)["meta"])
    stats = aggregate(metas)

    out = Path(args.out or f"reports/CORPUS_COVERAGE_METADATA_{datetime.now():%Y%m%d}.md")
    out.write_text(render_report(stats, args.corpus), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
