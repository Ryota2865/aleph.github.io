# ALEPH

[English](README.en.md)

LLMによる文学表現のための自律制作システム。文学的な生態系の空き地（vacant niche）を探し、そこに棲む作品を作る。

- **設計図（正典）**: [PLAN.md](PLAN.md) — 全アーキテクチャ・判断ポリシー・マイルストーン
- **変更履歴**: [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md)
- **ライセンス**: [LICENSES.md](LICENSES.md) — コード=MIT / 作品・制作記録=CC0 / 文書=CC-BY 4.0

## 状態

<!-- repository-snapshot:start -->
- 作品記録: 9作（w0009まで）、終端到達: 9作。
- 公開作品: 5作 — w0004「半呼吸」、w0005「床の硬さ」、w0006「灯のうしろ」、w0007「折り目」、w0008「暗い側」
- formal audit artifact: 17件。tests greenとformal audit判定は分離して表示する。
<!-- repository-snapshot:end -->

M0〜M8（探索・素材・構成・執筆・査読・擱筆・公開の閉ループ、実験スプリント、
公開判断の分離と測定器修理）と、採用済み解釈・replay計画のPhase 1〜4を
実装・正式独立監査PASS済み。設計者（Claude Fable 5）が契約
（受入テスト）を書き、施工エージェント
（Claude Code / Codex / pi / hermes）がクロス監査体制で実装する（PLAN §10・§12）。

- **統合ラン実績**: w0001〜w0009 を実LLMで完走。w0001〜w0003・w0009 は SHELVE、w0004〜w0008
  は PUBLISH。w0009はL2時代属性介入のbudget経路終端。w0005/w0006では
  改稿指示の蒸留後、改稿版が初稿を大きく上回った。
- **M7/M8 スプリント（2026-07）**: 素材の作品別生成、ニッチ採点の実測化、改稿切断の修理、
  §5.4 AI固有技法の実配線、宛先と公開判断の分離、分割査読・改稿指示蒸留・測定器監査を完了。
  詳細は [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md) 0.7.14〜0.7.17 と
  [PROGRESS.md](PROGRESS.md) を参照。
- **公開サイト**: `docs/`（GitHub Pages）。公開5作品に加え、制作過程、批評と応答、研究、
  詩学、日本語・英語ミラーを収載する。Settings → Pages → `main` / `/docs` で配信。
  正規生成器は `scripts/build_public_site.py`、画面設計は
  [designs/public-site.md](designs/public-site.md)。`aleph/publish/site.py`の簡易M6出力や
  `scripts/build_private_shelf.py`の非公開棚とは分離している。

## 施工者向け

```bash
uv sync --extra dev
uv run pytest -m 'not local'   # 設計不変条件 + 全マイルストーン受入（常に緑であること）
uv run pytest -m m0            # 個別マイルストーンの受入基準（m0..m6 を指定可）

# 探索→アトラス→ニッチ（要 llama-server / bge-m3。scripts/start_local_stack.sh）
uv run python -m aleph.cli explore
# 作品の作成と閉ループ実行
uv run python -m aleph.cli new --hint "..."
uv run python -m aleph.cli run --work w0001
uv run python -m aleph.cli status   # 予算3系統の残高
```

- 設計上の不変条件は `tests/test_design_invariants.py` に固定されている。
  これを赤にする変更は設計変更であり、PLAN_CHANGELOG への記録と設計者の審査が必要。
- 受入テストを弱める変更（assert削除・skip追加）は監査で不合格（PLAN §12）。
- 秘密情報は `.env` のみ。コード・設定・ログへの平文混入はテストが検出する。

## 公開（二層構造、PLAN §8）

- 表層: 読者向けサイト（final作品 + 制作ノート）
- 深層: `works/` の全制作記録（欠陥稿・査読・決定ログ・SHELVEの墓場）— 機械可読アーカイブ

署名は関与モデルの役割つき列記。単一の「作者」を偽装しない。
