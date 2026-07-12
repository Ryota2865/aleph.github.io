# ALEPH

LLMによる文学表現のための自律制作システム。文学的な生態系の空き地（vacant niche）を探し、そこに棲む作品を作る。

- **設計図（正典）**: [PLAN.md](PLAN.md) — 全アーキテクチャ・判断ポリシー・マイルストーン
- **変更履歴**: [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md)
- **ライセンス**: [LICENSES.md](LICENSES.md) — コード=MIT / 作品・制作記録=CC0 / 文書=CC-BY 4.0

## 状態

M0〜M6 の全マイルストーン（探索・素材・構成・執筆・査読・擱筆・公開の閉ループ）を実装・
受入済み。設計者（Claude Fable 5）が契約（受入テスト）を書き、施工エージェント
（Claude Code / Codex / pi / hermes）がクロス監査体制で実装する（PLAN §10・§12）。

- **統合ラン実績**: w0001〜w0004 を実LLMで完走。w0001〜w0003 は宛先「自分」最大で
  自動 SHELVE。w0004 は LLM 宛強制の実験走行で、品質床を通過し公開ゲート最終段に到達した
  初の作品（初回公開の人間承認 `first_publish_ack` により保留中）。
- **M7 スプリント（2026-07）**: 素材の作品別生成・ニッチ採点の実測化・改稿切断の修理と、
  §5.4 AI固有技法（反クリシェ・トークン層の詩学）の初配線。詳細は
  [PLAN_CHANGELOG.md](PLAN_CHANGELOG.md) 0.7.14。
- **公開サイト**: `docs/`（GitHub Pages）。公開作品ゼロの正直な空状態を表示する。
  Settings → Pages → `main` / `/docs` で配信。

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
