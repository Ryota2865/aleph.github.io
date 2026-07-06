# PLAN 変更履歴

## 0.6 (2026-07-07)
設計権限の継承規定（§12.1新設）。

- 背景: 初代設計者（Claude Fable 5）は2026-07-07（米国時間）以降サブスクリプションから
  利用不能になる見込みのため、設計権限を個体でなく役割として定義し直した。
- 就任手続き（PLAN全文・変更履歴・不変条件テスト・policiesの読了と就任記録）、
  会話履歴に依存しない設計意図の再構築可能性の要求、後継者がオーナー承認なしに
  変更できない3点（未解決の緊張の緩和・不変条件テストの弱体化・人間エスカレーション
  条件の緩和）、施工者/監査者の分離維持を規定。

## 0.5 (2026-07-07)
ライセンス最終確定と、設計者による骨格の施工。

- §14-2 改訂: 作品・制作記録（works/・poetics/）= CC0 1.0 / コード = MIT / 文書 = CC-BY 4.0。
  根拠（純AI生成物の著作権不発生可能性との整合、将来コーパス収載の最大化、コードへのCC非推奨）を明記。
- §12 追記: 設計権限の運用——骨格・契約・受入テストは設計者（Claude Fable 5）施工。
  契約/テストの変更は PLAN_CHANGELOG 経由で設計者審査。受入テストを黙って弱める変更は監査不合格。
- 骨格施工（コミット対象）:
  - pyproject.toml（uv / pytest markers: m0, local。既定実行は不変条件のみ）
  - LICENSE (MIT), LICENSES.md, works/LICENSE (CC0)
  - config/: models.yaml（実在資産＋harnessプロバイダ）, budgets.yaml（3系統・公開規律）,
    policies.yaml（全自律判断ポリシーの宣言）, publish.yaml（二層構造・meta必須フィールド）
  - aleph/: 全9層のパッケージ。core（llm/budget/loop/artifacts/config/local）は
    インターフェース契約＋docstringにPLAN節参照。config.py・vault.pyガード・
    scrub_secrets・状態遷移表は実装済み。他は NotImplementedError スタブ。
  - tests/test_design_invariants.py — 17件、現在緑（設計決定のコード化:
    モデル名直書き禁止、FINISH≠PUBLISH、機会的エッジ、Vault規約、秘密混入検査等）
  - tests/test_m0_acceptance.py — M0受入基準8件、現在赤（施工者の目標）
  - poetics/README.md（第0版への人間種文混入の禁止を明文化）, corpus/README.md, README.md
- 検証: WSL上で `uv run pytest` 17 passed / `pytest -m m0` 7 failed + 1 skipped（設計どおり）。

## 0.4 (2026-07-07)
オーナー第二陣決定（旧§15の全回答）を設計へ反映。

- §7.1: 外部の錨は既定オフ確定——人間協働をモデルが選んだ作品に限りtaste提供。陪審不一致は二段階選抜（完成度の床→不一致優遇）で積極採用。
- §7.3d: 公開上限=月4作・週刊リズム（周期性を公開スケジューラの設計目標に）。長編一括は月1目安。
- §7.4: 詩学第0版は種文なし・潜在空間（ホワイトノイズ的な種）から自己生成。人間の意図を初期条件に混入させないことを生成条件とする。
- §8: 名義=関与モデルの列記。公開範囲の二層構造（表層=読者向けfinal+制作ノート、深層=全制作記録の機械可読アーカイブ）。読者反応を弱い信号として記録。corpus/は索引のみ公開。
- §14.3 新設: 第二陣決定の記録。§15は残置1件（harness規約適合——M0監査項目化、控えめ運用の前提つき）に整理。

## 0.3 (2026-07-07)
原プロンプトの批判的検証と、その設計への反映。オーナー決定事項の取り込み。

- §16 新設「原プロンプトの批判的検証」: 12項目の批判（新奇性の目的関数化不能、空き地仮説の限界、審美判断の循環性、Goodhart、LLM読者の不在、ステートレスな「自分」、直列パイプラインの限界、作品単位の印刷文化性、無限生産の弱点、失敗の廃棄、成長の欠如、未解決の緊張）。
- 批判への応答として本文に新機構を追加:
  - §7.4 詩学の自己更新 `poetics.md`（作品を跨いだ成長。原構想の最大の欠落への応答）
  - §4.3 空きの三分類（不可能型/未着手型/空虚型）・深さの見立て・否定的地図（negative atlas）
  - §7.1 Goodhart対策（スコアは情報であり目的関数でない）・陪審不一致の尊重・ローテーション・外部の錨
  - §2.4 機会的エッジ（DRAFT→EXPLORE/MATERIA の限定再入）
  - §5.4 二重宛先作品・生きているテキスト・AI紋の自覚的操作
  - §7.3d 公開の規律（SHELVEが常態、PUBLISHが例外）
  - §8 想定読者モデル世代の記録・系譜の透明性
  - §3 「自分」= ALEPHという継続体、の定義
- §14 旧・未決事項1〜5をオーナー決定として確定（公開チャネル=aleph.github.io、作品CC0/システムCC-BY、従量API $10/月、Brave Search、llama-swap + pi/hermes harness）。
  - §14.1 サブスクリプション優先ルーティング（第4のプロバイダ種別 harness、3系統の予算計上）
  - §14.2 秘密情報規約。Brave APIキーを `.env` へ移設（git未コミットを確認済み）、`.gitignore` 新設
- §15 未決事項（追補分）7件: 趣味の錨、公開規律の実額、陪審不一致の重み、名義と帰属、詩学の初期値、harness規約適合、公開リポジトリの範囲。
- 本ディレクトリが公開リポジトリ aleph.github.io のクローンである事実を §14 に記載。

## 0.2 (2026-07-07)
実環境情報の反映。

- §2.3 新設「ローカル推論基盤」: RTX 3090 (24GB) 単機、`~/models/` のGGUF Q4資産、llama.cpp `llama-server` 標準、大型モデル排他＋時分割swap、ローカル/APIの役割分担指針。
- §2.1 models.yaml 例を実在モデル（gemma-4-31B / 26B-A4B MoE / Qwen3.6-27B / Qwen3-8B / bge-m3 / Qwen3-Reranker）に差し替え。
- §4.5 新設「知識基盤（Obsidian Vault）との接続」: `~/document/obsidian-vault` を読み取り専用参照。Vault AGENTS.md の規約（raw不変、grail.md不可触、wiki書き込み禁止）を遵守。設計に直接効く既存ページ（ai-fiction-signatures / representation-geometry / model-collapse / local-llm-stack）を施工必読に指定。
- §1.1 埋め込みを bge-m3 主 + Qwen3-Embedding-0.6B 副 + Reranker に変更（multilingual-e5 案を廃止）。LLM抽象から Ollama/vLLM を llama-server に変更。
- M0 受入基準にローカル llama-server の起動・swap を追加。
- 旧§13「未決事項」から local LLM 基盤の項を解決済みとして削除し、§13「環境（確定事項）」を新設。未決事項は§14へ繰り下げ、モデル交換方式（llama-swap か自前か）を追加。

## 0.1 (2026-07-07)
初版。9層アーキテクチャ、M0–M6マイルストーン、クロス監査プロトコル。
