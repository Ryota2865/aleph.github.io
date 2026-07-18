"""L8 LLM宛アーカイブ（PLAN §8）— llms.txt索引。想定読者モデル世代をメタデータに記録。

形式（llms.txt）: 先頭 "# " 見出し、以降 各作品のリスト行。
final/meta.json のある作品のみを載せる。

施工: M6。正典は `tests/test_m6_acceptance.py`。
"""
from __future__ import annotations

import json
from pathlib import Path

from aleph.publish.status import is_published


def build_llms_txt(*, works_root: Path, out_dir: Path) -> Path:
    """out_dir/llms.txt を生成し、その Path を返す（PLAN §8）.

    形式:
      # ALEPH works

      - [<work_id>] <title> — intended readers: <intended_reader_models 結合>
    final/meta.json のある作品のみ。
    """
    works_root = Path(works_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# ALEPH works", ""]
    for meta_path in sorted(Path(works_root).glob("*/final/meta.json")):
        work_id = meta_path.parent.parent.name
        if not is_published(meta_path.parent.parent):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        title = meta.get("title", work_id)
        readers = meta.get("intended_reader_models", [])
        if isinstance(readers, list):
            readers_str = ", ".join(str(r) for r in readers)
        else:
            readers_str = str(readers)
        lines.append(f"- [{work_id}] {title} — intended readers: {readers_str}")

    path = out_dir / "llms.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
