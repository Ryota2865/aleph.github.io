# ALEPH

LLMによる文学表現のための自律制作システム。文学的な生態系の空き地（vacant niche）を探し、そこに棲む作品を作る。

- **設計図（正典）**: [PLAN.md](PLAN.md) — 全アーキテクチャ・判断ポリシー・マイルストーン
- **変更履歴**: [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md)
- **ライセンス**: [LICENSES.md](LICENSES.md) — コード=MIT / 作品・制作記録=CC0 / 文書=CC-BY 4.0

## 状態

骨格（インターフェース契約・設定・受入テスト）まで設計者（Claude Fable 5）が施工済み。
M0以降の実装は施工エージェント（Claude Code / Codex）がクロス監査体制で行う（PLAN §10・§12）。

## 施工者向け

```bash
uv sync --extra dev
uv run pytest              # 設計不変条件（常に緑であること）
uv run pytest -m m0        # M0受入基準（これを緑にするのがM0の仕事）
```

- 設計上の不変条件は `tests/test_design_invariants.py` に固定されている。
  これを赤にする変更は設計変更であり、PLAN_CHANGELOG への記録と設計者の審査が必要。
- 受入テストを弱める変更（assert削除・skip追加）は監査で不合格（PLAN §12）。
- 秘密情報は `.env` のみ。コード・設定・ログへの平文混入はテストが検出する。

## 公開（二層構造、PLAN §8）

- 表層: 読者向けサイト（final作品 + 制作ノート）
- 深層: `works/` の全制作記録（欠陥稿・査読・決定ログ・SHELVEの墓場）— 機械可読アーカイブ

署名は関与モデルの役割つき列記。単一の「作者」を偽装しない。
