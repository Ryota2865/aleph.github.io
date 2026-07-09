# PLAN 変更履歴

## 0.7 (2026-07-08) — 施工者提案 → 設計者承認済み（0.7.1参照）
harness利用規約適合ガード（PLAN §15-1の残置項目への対応）。施工者（Claude Code /
Claude Sonnet 5）が config/policies.yaml に `harness:` セクションを追加する。

- 背景: PLAN §15-1「唯一の残置事項」として明記されていたharness（claude-code /
  codex の非対話CLI自動実行）の規約適合について、Codexクロス監査
  （commit 72fc803 → `reports/CODEX_AUDIT_20260708_094819.md`）が「M0監査項目が
  未対応」と指摘。サブエージェントにWeb一次情報調査を依頼した結果:
  - Anthropic: Claude Code公式ドキュメント（code.claude.com/docs/en/headless）が
    `claude -p` をスクリプト/cron/CI向け公式機能と明記。ただし「ordinary,
    individual usage」の閾値は非公開。→ 判定: CONDITIONAL（実質PASSに近い）。
  - OpenAI: Codex CLI公式ガイド（developers.openai.com/codex/auth/ci-cd-auth）が
    ChatGPT加入者認証での自動化を「advanced/enterprise向けの例外的手段」と位置づけ、
    「公開・OSSリポジトリでの使用は避けよ」と明記。本リポジトリは公開リモート
    （aleph.github.io）を持つため要注意。→ 判定: CONDITIONAL（Anthropicより慎重に）。
- 変更内容: `config/policies.yaml` に `harness.enabled`（既定 `false`）と
  CLI別 `harness.cli_tos_ack.{claude-code,codex}`（既定 `false`）を新設。
  `aleph/core/llm.py::build_provider()` は、この2条件が満たされない限り harness
  プロバイダの構築を拒否する（`RouterError`）。つまり harness 経由の呼び出しは
  **人間が規約を確認し明示的に有効化するまで既定で無効**になる。
- 審査事項（設計権限者へ）: (1) 既定オフというデフォルトの妥当性、(2) codex側に
  より慎重な扱い（cli別フラグ分離）を設けたことの妥当性、(3) PLAN §15-1の
  「残置事項」を本変更をもってCLOSEDとしてよいか、それとも `audits/M0_audit.md`
  への正式記録（Codexによる監査）を待つべきか。
- 未確定のまま残す事項: 「ordinary, individual usage」の定量閾値がAnthropic非公開
  であるため、コード側のレート制御（budgets.yaml: harness.calls_per_day=40,
  concurrent=1）を規約適合の実効的根拠とする、という前提は施工者の判断であり、
  設計者による追認が望ましい。

## 0.7.1 (2026-07-09) — 設計者審査結果（Claude Fable 5、初代設計者）

0.7の審査事項3点への回答。審査にあたり、施工された `config/policies.yaml` の
`harness:` セクション、`aleph/core/llm.py::build_provider()` のガード、
`tests/test_harness_policy.py` の5テスト、サブエージェントの一次情報調査記録
（PROGRESS.md 2026-07-08）、`audits/M0_audit.md` を確認した。

1. **既定オフの妥当性 — 承認。** これは§15-1の作業前提（控えめなレート・人間の
   起動を起点とするバッチ実行）の**コードによる強制化**であり、自律判断ポリシーの
   緩和ではなく強化である。§12.1がオーナー承認を要求する3類型（未解決の緊張の
   緩和・不変条件テストの弱体化・人間エスカレーション条件の緩和)のいずれにも
   該当せず、設計権限の範囲内で承認できる。
2. **CLI別の慎重度差 — 承認、条件付き。** OpenAI公式ガイドの「公開リポジトリでの
   使用を避けよ」という一次情報に基づく差別化は妥当。条件として明確化する:
   **ALEPHランタイムからの codex harness 呼び出し（critic_harness役）は、本リポジトリ
   が公開リモートを持つ限り ack=false を維持することを推奨既定とする**。批評役は
   ローカル陪審（時分割）で代替する。なお開発ワークフローとしての codex-audit /
   codex-implement はリポジトリ外（~/bin）の人間起動ツールであり、ALEPHランタイム
   のharness規律の対象外（あれは開発者の道具であって作品制作システムの一部ではない）。
3. **§15-1の残置事項 — CLOSED とする。** 根拠: (i) 一次情報調査が記録済み、
   (ii) コードによるガードが施工・テスト済み、(iii) `audits/M0_audit.md` の正式
   監査記録が存在。存置する運用条件: (a) `cli_tos_ack` の変更はオーナーのみが行う、
   (b) budgets.yaml のレート制御（40回/日・並行1）を規約適合の実効的根拠として維持
   し、緩和には設計者審査を要する、(c) 無人常駐デーモン化しない。
- 施工者判断（レート制御を実効根拠とする前提）を**追認**する。
- 本審査をもって、旧§15の未決事項はすべて解決済みとなる。

## 0.7.2 (2026-07-09) — M1設計の具体化（設計者: Claude Fable 5）

M1（探索層）施工開始にあたっての設計決定。いずれも初代設計者の権限内。

1. **ベクタDBの差し替え**: PLAN §1.1 は Qdrant/Chroma を指定していたが、現在の
   コーパス規模（1.7万文書・数十万チャンク）では専用DBは過剰であり、
   **numpy float32 memmap + JSONL メタデータ + scikit-learn** のプレーン索引を
   `state/atlas/`（git管理外）に置く方式に変更する。根拠: §1.1自身の原則
   「成果物はすべてプレーンテキスト」「DBは索引にすぎない」に、依存が軽く
   ファイルが直接監査できるこの方式のほうがむしろ適合する。HDBSCAN は
   `sklearn.cluster.HDBSCAN` で充足（hdbscanパッケージ不要）。数百万チャンク
   規模に達したら Qdrant へ移行する（Atlas クラス境界で吸収し、上位層は不変）。
2. **LLMResponse への reasoning フィールド追加**: ローカルの gemma-4 / Qwen3.6 は
   思考モデルとして応答し `reasoning_content` に出力を入れる（2026-07-09実測）。
   `LLMResponse.reasoning: str | None = None` を追加し、OpenAICompatProvider が
   これを保存する。既存フィールドの意味・既存テストは不変。
3. **M1受入テストの新設**: `tests/test_m1_acceptance.py`（マーカー `m1`、既定実行
   から除外）を設計者が施工する。ロジック契約（チャンク・索引・密度・三分類・
   Web照合除外・レポート形式）は偽埋め込み/偽scoutで高速に固定し、
   「1万文書以上・上位20件レポート」の実ランは CLI `aleph explore` の実行と
   Codex監査で検証する（M0における test_local_swap と同じ二層方式）。
4. **チャンク方針**: 段落境界を尊重、目安2000字、作品あたり最大30チャンク
   （冒頭偏重を避け作品全体から均等抽出）。全文はPDのみなのでチャンク本文を
   索引に保存してよい（§4.1・§11に適合）。

## 0.7.3 (2026-07-09) — M2設計の具体化（設計者: Claude Fable 5）

1. **logprobs技法の実装形**: llama-server(llama-swap経由)は生成トークンの
   logprobs/top_logprobs を返すことを実機確認済み。一方 `llama-perplexity`
   バイナリは未ビルドで、既存テキストのプロンプト側logprobs取得は不安定。
   よってM2の技法は**生成時logprobs**を一次素材とする:
   (a) 反クリシェ生成 = 高温度で複数候補を生成し、平均logprob最低（=最も
   意外）かつscout整合性審査を通る候補を選抜。最高確率候補（=クリシェ）は
   провенансとして記録。(b) perplexity設計 = 節ごとの生成logprob曲線を目標
   カーブと比較しながら執筆・改稿。(c) トークン層の詩学 = tokenizer境界の
   構造を素材化。真のプロンプト側PPLは将来 `llama-perplexity` ビルドで精密化。
2. **技法レジストリ**: `ai_native.TECHNIQUES` は辞書ベースのレジストリとし、
   §11のプラグイン要件（entry point化）はM6以降の拡張とする。
3. **非文学母材フィクスチャ**: M2受入の「3種の非文学母材」は
   `tests/fixtures/nonliterary/` に小型自作テキスト（RFC様式・法令様式・
   コミットログ様式）を置いて検証し、実運用母材はM3以降の実ランで取得。
4. **受入テスト**: `tests/test_m2_acceptance.py`（マーカー `m2`、既定除外）を
   設計者が施工。「上位50対・非自明7/10」の質的判定はM1同様、実ラン+監査
   （PLAN §12）で行う。

## 0.7.4 (2026-07-09) — ルーティング確定・harness有効化（設計者: Claude Fable 5）

オーナーが .env に ANTHROPIC_API_KEY / OPENAI_API_KEY（各$10課金）/ ZAI_API_KEY を
追加し、「harness、ggufも自由に使ってください。品質と予算のバランスは設計者に一任」
と明示的に許可した（2026-07-09）。これを受けた設計決定:

1. **harness有効化**: `config/policies.yaml` の `harness.enabled: true`、
   `cli_tos_ack.claude-code: true` に変更。0.7の設計（人間の明示的有効化まで拒否）
   の発動条件——オーナーの明示的許可——が満たされたため。**codex は 0.7.1 の
   条件（公開リポジトリではack=false推奨既定）に従い false のまま**。
2. **作者役の一次ルーティング**: `author_primary` = anthropic API `claude-fable-5`
   （$10/$50 per MTok。1呼び出し≈$0.15、$10予算で約60呼、usd_per_work=3.0の
   作品別上限が効く）。設計者自身が初代作者を務めることになるが、これは
   施工者/監査者分離（§12）とは別軸であり、PLAN §3 の author 役の宣言変更に
   すぎない。予算逼迫時は author_harness（claude-code CLI）→ author_local
   （gemma-4-31B）の順でフォールバック（§14.1 の優先順位の範囲内）。
3. **AnthropicProvider の修正が必要（施工課題）**: claude-fable-5 / claude-opus-4-8
   はAPI仕様上 `temperature` パラメータを受け付けない（400）。AnthropicProvider は
   temperature を送信しないよう修正する。思考は常時オン（パラメータ不要）。
   `stop_reason: "refusal"` の検査を追加する。
4. **コスト計上の精密化（施工課題）**: models.yaml の役割宣言に任意の
   `pricing: {input_per_mtok, output_per_mtok}` を追加し、宣言があれば実 usage から
   正確な cost_usd を計上する（モデル名のコード直書き禁止の不変条件を保ちながら
   モデル別価格を実現する唯一の経路）。宣言がない場合は既存のプロバイダ概算に
   フォールバック。

## 0.7.5 (2026-07-09) — M3契約と並列施工体制（設計者: Claude Fable 5）

1. **M3受入テスト** `tests/test_m3_acceptance.py`（m3マーカー、既定除外）を設計者が
   施工。固定する契約: 基準の作品ごと導出と宛先・詩学の注入（§6.1・§3・§7.4）、
   構成3案の必須フィールド、進化2世代の系譜記録、**authorプロンプトへの数値スコア
   混入禁止**（§7.1 Goodhart回避の機械的強制）、階層文脈執筆（要約+直前全文+現在位置）、
   意図的断絶の平滑化スキップ（§6.2）、ニッチ→drafts/v1.mdの全自動パイプラインと
   L4/L5決定記録。実LLMでの短編生成はM6統合ランで検証（二層方式）。
2. **並列施工体制**: 実装ワーカー2系統を並列運用する——M2=Codex(GPT-5.5)、
   M3=pi coding agent(GLM-5.1、delegate-to-piスキル)。ファイル集合は互いに素
   （materia+core/llm vs compose+draft）。検証・監査は従来どおりClaude側が握る
   （PLAN §12の施工/監査分離は維持: 各ワーカーの成果物は別ワーカーまたはClaudeが監査）。

## 0.7.6 (2026-07-09) — M4契約（設計者: Claude Fable 5）

`tests/test_m4_acceptance.py`（m4マーカー、既定除外）を設計者が施工。固定する契約:
5審級（技術/基準/新奇性/読者/敵対的）が1報告に揃うこと、**陪審の不一致度の記載を
絶対要件化**（§7.1・§14.3-8）、新奇性査読はアトラス最近傍距離の実測、敵対的査読は
url+理由つきの具体的指摘（M4受入のフィクスチャ検証）、**改稿プロンプトへの数値
スコア混入禁止の機械検査**（§7.1 Goodhart回避。M3と同型の防壁）、REVISEループの
版・スコア軌跡（reviews/trajectory.jsonl）とL6決定記録。陪審ローテーションと
L7による改稿先振り分け（L4/L5）はM5・M6の配線時に検証する。

## 0.7.7 (2026-07-09) — M5契約（設計者: Claude Fable 5）

`tests/test_m5_acceptance.py`（m5マーカー、既定除外）を設計者が施工。固定する契約:
擱筆判断の3経路（収束=スコア改善ε未満+指摘循環／完成宣言=敵対的査読が反駁不能／
過剰彫琢=スコア上昇×新奇性縮小の警報）+予算切れ経路、人間協働の「呼ばない判断も
記録」、公開ゲートの月次上限・棚との比較論述・「自分宛」既定SHELVE（§3・§7.3d・
§14.3-7）、**詩学第0版のAPIが人間種文パラメータを構造的に持たないこと**（inspect
検査。§14.3-10）と§16.12の2つの緊張の注入、リフレクションの敵対的査読ゲートと
差分理由の履歴化、固着検出。実LLMでの詩学生成はM6統合ランで検証。

## 0.7.8 (2026-07-10) — M6契約とコーパス容量方針（設計者: Claude Fable 5）

1. **M6受入テスト** `tests/test_m6_acceptance.py`（m6マーカー、既定除外）を設計者が施工。
   固定する契約: L1志向選択（配合比+候補ごとの理由書+「自分」=継続体の定義注入+
   詩学注入+L1決定記録）、閉ループ配線の完全1周（全遷移でチェックポイント+決定記録、
   final/text.md と meta.json の必須フィールド=credits/license(CC0-1.0)/published_at/
   intended_reader_models）、ゲートSHELVE時の終端、**クラッシュ後のチェックポイント
   再開（完了済み状態を再実行しない）**、静的サイトの二層構造（表層に credits と
   CC0、深層=制作記録へのリンク）、llms.txt 索引（調律先読者モデル世代を含む）。
   配線は新設 `aleph/pipeline.py` に置き、core/loop.py の正典遷移表は不変。
2. **コーパス容量方針（§4.1の修正）**: WSL仮想ディスクの実効残量が81GBと判明
   （ホスト2TBのうちWSL領域は1TB・内92%使用。オーナー報告 2026-07-10）。
   §4.1の「青空文庫全量、Project Gutenberg（多言語）、Wikisource」の**全文全量格納を
   撤回**し、**コーパス総容量予算 50GB**（gitignore領域）を設ける。内訳: 青空文庫全量
   （0.7GB、取得済み）を核とし、Gutenberg/Wikisource は多様性優先の選抜サブセット
   （合計≤40GB、M6完走後の拡張マイルストーンで取得）、二次コーパス（非文学母材）は
   小型キュレーション（≤5GB）。ベクタDB前提は既に0.7.2でプレーン索引に置換済み。
   クラウドストレージは最終手段（オーナー方針）。ニッチ探索の意味での「網羅性」は
   全量ではなく**属性空間のカバレッジ**（言語・年代・ジャンル・形式の直積の充足）で
   測る方針に切り替える。

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
