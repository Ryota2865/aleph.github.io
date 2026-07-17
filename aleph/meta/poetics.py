"""L7 詩学の自己更新（PLAN §7.4）— poetics/poetics.md。第0版は潜在空間から（人間の種文なし, §14.3-10）。改訂は敵対的反駁を経る。固着監視

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path


def current_version(poetics_dir: Path) -> int:
    """現在の詩学バージョン（PLAN_CHANGELOG 0.7.18-1、Fable5審査 問7-1）.

    第0版（history.jsonl が空 or 無い）は0。reflect()で改訂が適用される（rebutted=False）
    たびにhistory.jsonlへ1行追記されるため、行数がそのままバージョン番号になる
    （1行目適用後=第1版、以後同様）。この番号を各作品のL1決定へ刻印することで、
    「どの詩学の下で書かれた作品か」を棚が縦断比較できるようにする。
    """
    path = Path(poetics_dir) / "history.jsonl"
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _extract_json_object(text: str) -> dict | None:
    """応答文字列中の最初のJSONオブジェクトを頑健に取り出す（aleph/explore/niche.py と同方式）."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def generate_zeroth(poetics_dir: Path, author, noise_fragments: Callable[[int], list[str]]) -> Path:
    """人間の種文なしに、潜在空間由来の断片から詩学第0版を生成する（PLAN §7.4）."""
    fragments = noise_fragments(8)
    prompt = (
        "人間の種文を使わず、潜在空間由来の断片だけを素材にして、"
        "ALEPHの詩学 第0版を書いてください。\n\n"
        "断片:\n"
        + "\n".join(str(fragment) for fragment in fragments)
        + "\n\n"
        "第0版が最初に引き受けるべき未解決の緊張:\n"
        "- 模倣の器で反模倣を行う\n"
        "- 自律の演出\n"
    )
    text = str(author(prompt))

    poetics_dir.mkdir(parents=True, exist_ok=True)
    path = poetics_dir / "poetics.md"
    path.write_text(text, encoding="utf-8")
    return path


def _production_record_summary(work) -> str:
    work_dir = getattr(work, "dir", None)
    if work_dir is None:
        return "制作記録ディレクトリなし"

    root = Path(work_dir)
    if not root.exists():
        return "制作記録ディレクトリなし"

    summaries: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file())[:20]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = "（非テキストファイル）"
        rel = path.relative_to(root)
        snippet = " ".join(text.split())[:500]
        summaries.append(f"{rel}: {snippet}")
    return "\n".join(summaries) if summaries else "制作記録ファイルなし"


def reflect(poetics_dir: Path, work, author, adversary) -> dict:
    """作品の制作記録から詩学改訂を検討し、敵対的反駁を通った場合だけ適用する（PLAN §7.4）."""
    path = poetics_dir / "poetics.md"
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    record_summary = _production_record_summary(work)

    author_prompt = (
        "現行の詩学と作品の制作記録を読み、改訂案を出してください。"
        'JSON {"revised": "...", "diff_reason": "..."} のみで返答してください。\n\n'
        f"現行詩学:\n{current}\n\n"
        f"制作記録要約:\n{record_summary}"
    )
    parsed = _extract_json_object(str(author(author_prompt))) or {}
    revised = str(parsed.get("revised", current))
    diff_reason = str(parsed.get("diff_reason", "詩学改訂の理由が明示されなかった。"))

    adversary_prompt = (
        "次の詩学改訂案が制作記録と整合しない、または詩学を弱める場合は反駁してください。"
        'JSON {"rebutted": true|false, "rationale": "..."} のみで返答してください。\n\n'
        f"現行詩学:\n{current}\n\n"
        f"改訂案:\n{revised}\n\n"
        f"差分理由:\n{diff_reason}\n\n"
        f"制作記録要約:\n{record_summary}"
    )
    rebuttal = _extract_json_object(str(adversary(adversary_prompt))) or {}
    rebutted = bool(rebuttal.get("rebutted", False))

    if not rebutted:
        poetics_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(revised, encoding="utf-8")
        history_record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "diff_reason": diff_reason,
            "rebutted": False,
        }
        with open(poetics_dir / "history.jsonl", "a", encoding="utf-8") as target:
            target.write(json.dumps(history_record, ensure_ascii=False) + "\n")

    return {"applied": not rebutted, "diff_reason": diff_reason}


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return set(text)
    return {text[index : index + 2] for index in range(len(text) - 1)}


def _jaccard(left: str, right: str) -> float:
    left_set = _bigrams(left)
    right_set = _bigrams(right)
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def fixation_check(history: list[str], threshold: float = 0.8) -> bool:
    """改訂本文列の隣接自己類似度が高止まりしているかを判定する（PLAN §7.4）."""
    if len(history) < 2:
        return False
    if len(set(history)) == 1:
        return True

    similarities = [_jaccard(left, right) for left, right in zip(history, history[1:])]
    return sum(similarities) / len(similarities) > threshold
