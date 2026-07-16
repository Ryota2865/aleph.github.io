# PROGRESS

## 2026-07-08 — M0 施工完了（Claude Code / Claude Sonnet 5）

### 完了したこと
- `aleph/core/llm.py`: `CallLogger.log`（scrub_secrets経由でJSONL追記）、`Router`
  （役割解決・リトライ3回・予算事前照会・calls.jsonl記録・harness用セマフォ）を実装。
  併せて `AnthropicProvider` / `OpenAICompatProvider`（従量API・llama-server兼用）/
  `HarnessProvider`（`claude -p` / `codex exec` の非対話呼び出し）と `build_provider`
  ファクトリを新設し、PLAN §2.1 の「3プロバイダ + harness」を同一インターフェースで
  呼べるようにした。
- `aleph/core/budget.py`: `Budget.precheck/charge/status` を実装。3台帳
  （api=USD/月, harness=呼数/日, local=GPU時間/日）を期間ロールオーバーつきで管理。
  `state_path` を渡した場合のみJSON永続化（既定はプロセス内メモリのみ、テストの
  副作用を避けるため）。api には `usd_per_work` の作品別サブ台帳も用意（未使用でも
  budgets.yaml の宣言に対応）。
- `aleph/core/artifacts.py`: `Work.create/append_decision/latest_draft_version` を実装。
  `decided_by` 欠落時は `ValueError`。
- `aleph/core/loop.py`: `Checkpoint.save/load`（`checkpoint.json`）、
  `Loop.transition/run` を実装。`run()` は `handlers` 未登録の状態に来ると停止する
  （M3以降で各層の処理を `Loop.handlers[State.X] = fn` として接続する前提）。
- `aleph/core/local.py`: `LocalRuntime.ensure_model/resident_models` を実装。
  llama-swapのOpenAI互換エンドポイントへ軽量な補完リクエストを送りpre-warmする方式。
  **実機（RTX 3090 + llama-server/llama-swap）では未検証**（`ALEPH_LOCAL=1` 環境が
  必要。`test_local_swap` はデフォルトでskip）。

### 検証
- `uv run pytest -m m0` → 7 passed, 1 skipped（test_local_swapは要ハードウェア）。
- `uv run pytest`（既定 = 設計不変条件のみ）→ 17 passed、退行なし。
- `uv run pytest -m 'not local'`（m0 + 設計不変条件を同時実行）→ 24 passed、
  テスト間の予算台帳汚染など相互干渉なしを確認。
- Router→Budget→Work→Loopを実際に繋いだ手動スモークテスト（FakeProviderで
  ネットワーク非依存）で calls.jsonl / decisions.jsonl / checkpoint.json の一貫性を確認済み。

### 判明した事実 / 設計判断
- `test_no_hardcoded_model_names_outside_config` があるため、コスト概算は
  モデル名ではなく**プロバイダ名**（anthropic/openai）単位の概算レートで実装。
  正確な課金額はプロバイダ請求実績で別途校正する必要がある。
- Router内の予算計上は ledger 種別ごとに意味を変えている:
  `api`=実費USD、`harness`=呼数1件、`local`=0（GPU時間の実計測は
  `LocalRuntime` 側の責務として分離。Router からは計上しない）。
- Budgetはテスト分離のため既定で非永続（メモリのみ）。実運用（`aleph` CLI本体）で
  永続化する場合は `Budget(cfg, state_path=root/"state/budget.json")` のように
  明示的にstate_pathを渡すこと。

### 次の一手
- **監査待ち**: PLAN §12 のクロス監査（Claude Code施工 → Codexが監査）を
  `audits/M0_audit.md` に記録してもらう。特に §15-1 の harness利用規約適合の
  一次判定はM0監査項目として明記されている。
- M1（探索層: corpus/atlas/niche/webresearch）着手前に、`aleph/cli.py` の
  `status`/`new` などをBudget/Workに実配線するかは要判断（M0受入基準には
  含まれていないため今回は未着手）。
- 実機（RTX 3090）が使える環境で `ALEPH_LOCAL=1 uv run pytest -m local` を一度
  流し、`LocalRuntime.ensure_model` がllama-swap経由で実際にswapできるか確認する。

### ハマりどころ
- 作業ディレクトリは `\\wsl.localhost\ubuntu\home\ryota_tanaka\llm_literature`
  経由（Windows Git Bash）でファイル操作はできるが、`uv`はWSL内にしかPATHが
  通っていない。テスト・pythonコマンド実行は `wsl.exe -d ubuntu -- bash -lc "cd ~/llm_literature && ..."`
  を経由する必要がある。

## 2026-07-08 — Codexクロス監査 → 指摘3件を修正（Claude Code / Claude Sonnet 5）

コミット `72fc803` を対象に `codex-audit --commit 72fc803 --run-tests` を実行。
結果: `reports/CODEX_AUDIT_20260708_094819.md`（VERDICT: FAIL、指摘4件）。
うち3件（実装バグ）を修正。1件（harness利用規約適合）はサブエージェントに調査を委任（後述）。

### 修正した指摘
1. **finding 1（最重大）**: `Router._invoke` が `budget.precheck(ledger, 0.0)` と
   amount固定だったため、台帳が上限到達済みでも次の呼び出しがブロックされなかった
   （harness=40/40消費済みでも1件通ってしまい41/40になる、と監査が実再現）。
   → `Router._precheck_amount()` を新設。harnessは1件確定値、apiはプロンプト長と
   max_tokensからの概算コストで事前照会するよう修正（`aleph/core/llm.py`）。
2. **finding 3**: `Loop.__init__` が `self._step = 0` 固定だったため、
   `checkpoint.json`（例: step=7）から新しい `Loop` を作って `transition()` すると
   保存後のstepが1に巻き戻っていた（監査ログ順序が壊れる）。
   → `Loop._load_last_step()` で既存checkpointがあればそこから再開するよう修正
   （`aleph/core/loop.py`）。
3. **finding 4**: `Budget._save/_load` が `_work_spent`（作品別サブ台帳）を
   永続化対象に含めておらず、プロセス再起動後に作品ごとの `usd_per_work` 上限が
   検出できなくなっていた。
   → 永続化JSONに `work_spent` キーを追加（`aleph/core/budget.py`）。

3件とも `tests/test_m0_regressions.py`（新規）に再現テストを先に書いて赤を確認
→ 修正 → 緑、の順で検証。既存の `test_m0_acceptance.py` / `test_design_invariants.py`
（初代設計者の契約。PLAN §12により無断変更不可）は一切変更していない。
`uv run pytest -m 'not local'` → 27 passed（design invariants 17 + m0 acceptance 7 +
regressions 3）で退行なし。

### finding 2（harness利用規約適合）— サブエージェント調査 → ガード実装完了
サブエージェントがWeb一次情報（Anthropic Consumer ToS、Claude Code公式ドキュメント
`code.claude.com/docs/en/headless`、OpenAI Codex CLI公式ガイド
`developers.openai.com/codex/auth/ci-cd-auth`）を調査。結論:
- Anthropic: `claude -p` はscript/cron/CI向け公式機能と明記されており CONDITIONAL
  （実質PASSに近い）。ただし「ordinary, individual usage」の閾値は非公開。
- OpenAI: ChatGPT加入者認証での`codex exec`自動化は「advanced/enterprise向けの
  例外的手段」「公開リポジトリでの使用は避けよ」と公式ガイドが明記。本リポジトリは
  公開リモート（aleph.github.io）を持つため CONDITIONAL（Anthropicより慎重に）。
- Brave Search APIは不要だった（WebSearch/WebFetchで一次情報に到達できた）。

ユーザーの意思決定によりガード実装まで実施:
- `PLAN_CHANGELOG.md` に 0.7 として変更提案を記録（config/policies.yaml は
  「変更にはPLAN_CHANGELOGへの記録と設計者の審査が必要」な契約ファイルのため）。
- `config/policies.yaml` に `harness.enabled`（既定false）と CLI別
  `harness.cli_tos_ack.{claude-code,codex}`（既定false）を新設。
- `aleph/core/llm.py::build_provider()` が、この2条件が満たされない限り
  harnessプロバイダの構築を `RouterError` で拒否するよう変更。
- `tests/test_harness_policy.py`（新規）: 既定拒否・全体有効化のみでは拒否・
  CLI別ackも揃って初めて許可・認証情報らしきファイルがリポジトリに追跡されて
  いないこと、の5テストを追加。
- `uv run pytest -m 'not local'` → 32 passed（既存27 + harness policy 5）、退行なし。

**要設計者審査**（PLAN_CHANGELOG 0.7に詳細）: (1) 既定オフの妥当性、
(2) codex側をより慎重に扱う設計の妥当性、(3) 本変更をもってPLAN §15-1の残置事項を
CLOSEDとしてよいか、それとも `audits/M0_audit.md`（Codexによる正式監査記録）を
待つべきか。`audits/M0_audit.md` は監査者（Codex）が書くものであり、施工者
（Claude Code）が自ら書くのは PLAN §12 の施工者/監査者分離原則に反するため、
今回は書いていない。

## 2026-07-08 — M0マイルストーン単位のCodex監査（2回目）→ finding修正

コミット `53a2ffa`・`d3c3e9d` を含めたM0全体を対象に、設計者施工の骨格コミット
`3e1603c` を基準として `codex-audit --base 3e1603c --run-tests` を再実行
（PLAN §12「監査単位はマイルストーン」に合わせたスコープ）。
結果: `reports/CODEX_AUDIT_20260708_105020.md`（VERDICT: FAIL、指摘1件）。

### 指摘と修正
- **Router経由のAPI呼び出しで作品別予算(usd_per_work)が一切効かない**
  （`aleph/core/llm.py:208`/`:231`）。`Budget.precheck/charge` は `work_id` を
  受け取れるが、`Router._invoke()` がそれを渡す手段を持たず、常にグローバルAPI
  台帳だけを更新していた。Codexが実再現: `usd_per_work=3.0` に対しFakeProviderが
  $2.0を返す条件で `router.call()` を2回実行しても `BudgetExceeded` が出ず
  `api.spent=4.0` まで進む。
  → `Router.call()`/`call_jury()` の `**overrides` から `work_id` を取り出し、
  `budget.precheck()`/`budget.charge()` へ伝播するよう `_invoke()` を修正。
  `tests/test_m0_regressions.py::test_router_propagates_work_id_to_budget` を
  追加し、修正前に赤（`DID NOT RAISE BudgetExceeded`）→ 修正後に緑を確認。
- `uv run pytest -m 'not local'` → 33 passed、退行なし。

### 既知の限界（今回は対応せず、設計判断として残す）
- api台帳の事前照会（`Router._precheck_amount`）はプロンプト長と`max_tokens`からの
  概算であり、実際のプロバイダ課金額はレスポンス後にしか確定しない。したがって
  「この1回の呼び出しが単独で作品別上限を超過する」ケースを事前に完全に防げる
  わけではない（概算が小さければ通過し、実費が高ければ`charge()`後に台帳が
  超過状態になり、**次の**呼び出しの`precheck`で検出される、という事後的検出に
  留まる）。真の事前防止には応答前のコスト確定が必要で、現実のAPI課金モデル
  上は原理的に難しい。現状のテストはこの限界の範囲内で「work_idが実際に
  伝播し、既に上限に達した作品への次の呼び出しはブロックされる」ことのみを
  保証している。

## 2026-07-08 — M0マイルストーン単位のCodex監査（3回目）→ finding修正

コミット `bc86188` までを反映した状態で、再度 `codex-audit --base 3e1603c --run-tests`
を実行。結果: `reports/CODEX_AUDIT_20260708_105528.md`（VERDICT: FAIL、指摘2件）。

### 指摘と修正
1. **local台帳がRouter経由で実質機能していない**（`aleph/core/llm.py`の
   `_charge_amount`/`_precheck_amount`）。localは常に`amount=0.0`を返す設計だった
   ため、`budget.charge("local", limit)` で上限まで消費済みにしても
   `router.call("scout", ...)` がブロックされなかった（Codexが実再現:
   `NO_EXCEPTION provider_calls=1 status={'spent': 8.0, 'limit': 8, ...}`）。
   → `_LOCAL_CALL_HOURS_ESTIMATE = 1/60`（1呼び出し=1分相当の控えめな概算）を
   新設し、precheck・chargeの両方でlocal台帳にも計上するよう変更。厳密なGPU時間
   計測は将来 `LocalRuntime` 側での精密化課題として明記。
2. **harnessの本文がコマンドライン引数(argv)経由で漏洩しうる**
   （`aleph/core/llm.py` `HarnessProvider._build_command`）。
   `subprocess.run(["claude", "-p", prompt])` / `["codex", "exec", prompt]` は
   本文全体をargvに載せており、同一ホストの他プロセス/他ユーザーが`ps`等で
   読める状態だった。Claude Code公式ドキュメント（`code.claude.com/docs/en/headless`
   「Pipe data through Claude」）が示す `cat x | claude -p '短い指示'` の
   公式パターンに倣い、argvには秘密を含まない固定の短い指示のみを置き、
   本文（messages由来のprompt）は `subprocess.run(..., input=prompt, ...)` で
   stdin経由にのみ渡すよう変更。
- `tests/test_m0_regressions.py` に2件追加（
  `test_router_blocks_call_that_would_exceed_local_budget`,
  `test_harness_provider_does_not_leak_prompt_into_argv`）。両方とも修正前に
  `git stash` で一時的に戻して赤を確認 → 修正後に緑を確認。
- `uv run pytest -m 'not local'` → 35 passed、退行なし。

## 2026-07-08 — M0マイルストーン単位のCodex監査（4回目）→ finding修正

コミット `45dc193` までを反映した状態で再度 `codex-audit --base 3e1603c --run-tests`
を実行。結果: `reports/CODEX_AUDIT_20260708_110310.md`（VERDICT: FAIL、指摘1件）。

### 指摘と修正
- **成果物書き出しが `scrub_secrets` を経由していない**（`aleph/core/artifacts.py`）。
  `Work.create()`/`Work.append_decision()` が受け取った辞書をそのままJSON書き込み
  しており、`aleph/core/artifacts.py:7` の「秘密情報を書き込まないこと（scrub_secrets
  経由で書く）」・PLAN §14.2に反していた。Codexがスモークで実証:
  `seed_contains_secret=True` / `decisions_contains_secret=True`。
  → `Work.__init__` に `secrets: Iterable[str] = ()` を追加（既存呼び出し
  `Work(root, work_id)` は互換）し、`create()`/`append_decision()` の書き込み前に
  `scrub_secrets()` を通すよう修正。
- `tests/test_m0_regressions.py` に2件追加
  （`test_work_create_scrubs_secrets_from_seed`, `test_work_append_decision_scrubs_secrets`）。
  修正前に `git stash` で戻し赤（`TypeError: unexpected keyword argument 'secrets'`）
  を確認 → 修正後に緑を確認。
- `uv run pytest -m 'not local'` → 37 passed、退行なし。

## 2026-07-08 — M0マイルストーン単位のCodex監査（5回目）→ finding修正・打ち止め判断

コミット `0798aea` までを反映した状態で再度 `codex-audit --base 3e1603c --run-tests`
を実行。結果: `reports/CODEX_AUDIT_20260708_111512.md`（VERDICT: FAIL、指摘2件）。

### 指摘1（修正済み）
- **`decisions.jsonl` のスキーマ不変条件が守られていない**（`aleph/core/artifacts.py`）。
  ファイル冒頭の不変条件は `{ts, layer, decision, reason, decided_by(model), refs}`
  と定義しているが、`append_decision()` は `ts`/`decided_by` の2つしか検査して
  いなかった。Codexが実証: `{"ts": "...", "decided_by": "audit"}` だけで
  追記できてしまう。
  → `_REQUIRED_DECISION_FIELDS = (ts, layer, decision, reason, decided_by)` を
  必須化（`refs`のみ省略可で、省略時は空リストを自動補完）。
  `Loop.transition()` が書くレコードは元々これら5フィールドを全て含んでいた
  ため無修正で通る。
- `tests/test_m0_regressions.py::test_append_decision_requires_full_schema` を追加。
  修正前に赤（`DID NOT RAISE ValueError`）→ 修正後に緑を確認。既存の
  `test_work_append_decision_scrubs_secrets`（4回目監査対応で追加）が`layer`欠落の
  レコードを使っていたため、あわせて`layer`を追加。
- `uv run pytest -m 'not local'` → 38 passed、退行なし。

### 指摘2（対応せず・理由を記録）
- **`reports/CODEX_AUDIT_*.md` の行末空白**が `git diff --check` に引っかかる、
  という指摘。これはCodexが生成したMarkdown自体が意図的な行末2スペース
  （Markdownのハード改行記法）を使っているためで、剥がすと監査レポートの
  見た目（改行位置）が壊れる。現状このリポジトリに空白チェックを行うCIは
  存在しないため実害はなく、Codex生成物の忠実性を優先して**対応しないことを
  意図的に選択**した。

### 打ち止め判断
5回のクロス監査サイクル（audit → fix → re-audit）を回し、実質的な指摘は
毎回1〜2件に減少・収束してきている。これ以上の反復はコスト対効果が薄いと
判断し、次の一手はユーザーへの報告とする（続けて監査するかはユーザー判断）。

## 2026-07-08 — `audits/M0_audit.md` 正式記録（Codex）

ユーザーの判断: (1) `audits/M0_audit.md` はCodex（監査者役割。PLAN §12）が書く、
(2) harness既定オフ設計（PLAN_CHANGELOG 0.7）の審査はClaude Fable 5（設計権限者。
PLAN §12.1）に依頼する予定——ただしFable5は明日昼までレート制限中、かつ
2026-07-12以降ユーザーはFable5にAPI経由でしかアクセスできなくなるため、
明日以降に別途依頼する。今日は(1)のみ実施。

`codex-audit --base 3e1603c --run-tests -o audits/M0_audit.md` で、PLAN §10 M0
受入基準のチェックリスト形式での正式監査を依頼（過去5回の`reports/CODEX_AUDIT_*.md`
とPROGRESS.mdの修正履歴を読ませた上で、それらを踏まえた最終判定として）。

結果: **VERDICT: PASS WITH NITS**（`audits/M0_audit.md`）。
- M0受入基準6項目中5項目が「Met」、1項目（ローカルRTX 3090実機でのswap起動）が
  「Not verified in this environment」（監査環境にGPU実機がないための検証未了。
  コード上の新規欠陥ではない）。
- 新規のcorrectness/invariant/security/data-loss findingはゼロ。
- `uv run pytest -m 'not local'` → 38 passed（Codex自身の再実行でも一致）。

### 次の一手
- M0マイルストーンは実質的にクローズ。残るのは (a) 実機RTX 3090環境での
  `ALEPH_LOCAL=1 uv run pytest -m local` の実行、(b) harness既定オフ設計の
  Fable5審査（2026-07-12までに完了させたいとのオーナー希望）。
- (b) が完了し次第、PLAN_CHANGELOG 0.7に審査結果（承認/差し戻し）を追記する。
- M1（探索層）着手はこれらの後、あるいはユーザーの指示があり次第。

## 2026-07-09 — Claude=司令塔／Codex=実装 のワークフロー確立 + `aleph status` 配線

ユーザー依頼: Claude Code をオーケストレーター、Codex(GPT-5.5) を実装担当にできるか
検証し（A）、`codex-audit` を雛形に実装用スキルを作る（B）。

### (A) オーケストレーション疎通 + 実弾1周
- 配線確認: `codex exec`（codex-cli 0.142.5 / gpt-5.5 / approval never）が
  llm_literature でも疎通。勘所——`codex` は nvm 配下のため非対話 `bash -lc` では
  PATH に載らない／`bash -ilc` は stdin 待ちでハングするので `</dev/null` 必須／
  PowerShell→wsl→bash の多重引用符は壊れるので `.sh` に書いてログへ流す。
- 題材: `aleph/cli.py` の `status` 配線（`Budget.status()` は実装済みで §11「aleph
  statusで常時可視」の未接続部分。マイルストーン封じの `NotImplementedError` スタブ
  には該当しない実在のM0仕上げ）。Codex が実装 → **Claude が独立検証**
  （`uv run pytest -m 'not local'` → 38 passed、`aleph status` → 3系統表示・exit 0、
  他コマンドは exit 2 スタブ維持）。

### (B) `~/bin/codex-implement` 作成
- `~/bin/codex-audit` を雛形に、実装専用の対のラッパーを作成（リポジトリ外なので
  公開リポジトリを汚さない）。`--sandbox workspace-write` 既定、git変更は既定禁止
  （`--allow-commit`で解禁）、`--files` で編集対象を強制限定、dirty-tree警告、
  「検証は司令塔の責務」をプロンプトに明記。`-t/--task-stdin/-- inline`、`--run-checks`、
  `--network`、`-o` 対応。
- 自己ドッグフーディング: cli.py をリバートして `codex-implement -t task --files
  "aleph/cli.py"` で再実装 → allowlist 遵守・手動実行とバイト同一パッチを生成。
  Claude 側で再度 38 passed を確認。

### 次の一手
- 上記 (a) 実機RTX 3090 / (b) Fable5審査 は据え置き（変更なし）。
- 以後の実装は `codex-implement` に投げて Claude が検証する運用が可能。

## 2026-07-09 — Fable 5復帰。0.7設計者審査完了、M1〜M6完走スプリント開始

Fable 5のサブスク利用が7/12まで延長された。オーナー指示: 週次レートリミットの
50%以内で、最も効率のよい方法でALEPHを完成（M6統合ラン）まで走り切る。
体制: **Fable 5 = 設計者/司令塔**（仕様書き・設計判断・検証の統括）、
**Codex (GPT-5.5) = 実装**（codex-implement）、**Sonnet 5/Opus 4.8 = サブエージェント**
（環境施工・検証の並列作業）。監査分離（PLAN §12）: Codex施工分はClaude側が監査。

### 0.7設計者審査（完了）
PLAN_CHANGELOG 0.7.1 として記録。要旨: (1)既定オフ承認（§15-1前提の強制化であり
強化）、(2)CLI別慎重度差を条件付き承認——**ALEPHランタイムからのcodex harnessは
公開リポジトリである限りack=false推奨既定**（批評はローカル陪審で代替。開発ツール
としてのcodex-audit/implementはランタイム規律の対象外）、(3)§15-1をCLOSED。
これで旧§15の未決事項はすべて解決。

### 環境偵察の結果（2026-07-09）
- GPU: RTX 3090 24GB、WSLから可視、ほぼ空き。ディスク312GB空き。
- **llama.cpp はビルド済み**（~/llama.cpp/build/bin/ に llama-server・llama-embedding。
  チェックアウト d77599234）。CUDA有効かは起動時に要確認。
- GGUF資産: gemma-4-31B(17G)・gemma-4-26B-A4B(14G)・Qwen3.5-27B(16G)・
  Qwen3.6-27B(16G)。models.yaml の reader_small (Qwen3-8B) はGGUF未変換
  （~/models/hf にHF形式あり。必要になったら変換 or 役割再宣言）。
- 埋め込み: bge-m3等は ~/models/embeddings にHFスナップショット形式。GGUF未変換。
  → llama.cpp の convert_hf_to_gguf.py で変換し llama-server --embedding で常駐予定。
- **llama-swap 未インストール**（GitHub releasesの単一バイナリ導入予定）。
- Python ML依存（numpy/chromadb/hdbscan等）未導入 → uv add で導入。
  ベクタDBは **Chroma を選定**（PLAN §1.1の「QdrantまたはChroma」の範囲内。
  Docker不要でpipのみ、10k文書規模に十分）。
- コーパス: ローカルに青空文庫資産なし → ダウンロードが必要。
- .env: BRAVE_API_KEY のみ（Anthropic/OpenAI APIキーなし）。**したがって閉ループの
  LLM呼び出しはローカル + harness のみで賄う**（api台帳は実質使用不可）。

### スプリント計画（7/9夜〜7/12昼）
- D0（7/9）: 環境施工（llama-swap導入・bge-m3変換・server起動・ALEPH_LOCAL=1で
  test_local_swap緑）／コーパス取得／M1仕様書→codex-implement
- D1（7/10）: M1完成+監査／M2実装（logprobs技法含む）
- D2（7/11）: M3+M4+M5実装／M6統合ラン準備
- D3（7/12午前）: 統合ラン完走→初稿をFable 5が読む
- 効率原則: 実装はすべてCodexへ委任、環境作業はサブエージェント並列、
  Fable 5は仕様・設計判断・最終検証に集中（トークン温存）。

## 2026-07-09 — 一次コーパス（青空文庫）取得（サブエージェント / Sonnet 5）

D0のコーパス取得タスクを実施。Hugging Face `globis-university/aozorabunko-clean`
（CC BY 4.0、青空文庫全作品をルビ・入力者注除去済みでクリーニング済み）から
`corpus/aozora/works.jsonl` を構築（`scripts/build_aozora_corpus.py`）。

- PD判定: 青空文庫マスターメタデータの `作品著作権フラグ`/`人物著作権フラグ`
  両方が「なし」の行のみ採用。元データ16,951行は実測で全行既に両フラグ「なし」
  （除外0件。本文空1件のみ別理由で除外）→ 16,950件を書き出し（要件10,000件超過）。
- サニティチェック: 死後70年ルールは2018年の法改正時点で既にPD化していた作品に
  遡及しない（旧50年ルール）。本コーパスの死没年最大値は1967年で、1968年以降
  没の著者は0件 → 経過措置と整合していることを確認。
- 品質チェック: `scripts/qa_aozora_corpus.py` でスキーマ違反0件・id重複0件、
  ランダム5件を目視検査（文字化けなし、ルビ記法残留なし）。
- 総サイズ約704 MiB。スキーマ・詳細は `corpus/README.md` に追記済み。
- 作成物: `scripts/build_aozora_corpus.py`（本体）、`scripts/qa_aozora_corpus.py`
  （QA）、`scripts/inspect_aozora_dataset{,2,3}.py`（データセット調査スパイク、
  削除せず保持）。`corpus/` はgit管理外のため `git add` はしていない
  （`corpus/README.md` のみ追跡対象）。

### 次の一手
- Project Gutenberg / Wikisource 等の追加一次コーパスは未着手（青空文庫のみで
  M1着手には十分な件数）。必要なら別タスクで追加。
- M1（`aleph/explore/corpus.py` の取り込み・チャンク・埋め込み処理）はこの
  JSONLを入力として使う想定。

## 2026-07-09 — ローカル推論スタック完成（Fable 5仕上げ。電源断からの復帰込み）

サブエージェント（Sonnet 5）が llama-swap導入・bge-m3 GGUF変換(f16, 1.1G)・
config/llama-swap.yaml・scripts/start_local_stack.sh まで施工したところで
ホストの電源断。Fable 5が状態を確認し、残り（起動・検証・校正）を直接仕上げた。

### 実測値（RTX 3090実機、2026-07-09）
- 埋め込み: bge-m3 f16、/v1/embeddings 応答、**1024次元**。大型モデルスワップ後も
  常駐維持（persistent group動作確認、応答0秒）
- 初回ロード: gemma-4-26B-A4B（14G）67秒
- スワップ: 26B→Qwen3.6-27B **81秒** → config/budgets.yaml の swap_cost_seconds を
  45→90 に校正
- VRAM: Qwen3.6-27B + bge-m3 常駐で 18.8/24.6 GB
- **ALEPH_LOCAL=1 uv run pytest -m local → test_local_swap PASSED**。
  M0受入基準の最後の1項目（実機swap）がこれで検証完了。**M0は完全に緑**

### 重要な発見と対処
- gemma-4 も Qwen3.6 も**思考(reasoning)モデル**として応答し、content が空で
  reasoning_content に出力が入る。scout（大量安価な下働き）には致命的なトークン
  浪費なので、llama-swap.yaml の scout エントリに **--reasoning-budget 0** を付与
  （検証済み: content に直接応答が入るようになった）。Qwen3.6（reader/批評）は
  思考を残す。**M1以降の実装への含意**: OpenAICompatProvider は
  reasoning_content の存在を意識すること（M1仕様に記載する）
- 「pkill -f llama-swap」は自分のコマンドライン文字列にもマッチして自殺する。
  停止は state/llama-swap.pid 経由で行うこと
- スパイクスクリプト（inspect_aozora_dataset*.py）は規約に従い削除
- .env にオーナーが ANTHROPIC_API_KEY / OPENAI_API_KEY（各10ドル課金）/
  ZAI_API_KEY（Coding planサブスク）を追加。**api台帳が使用可能になった**。
  オーナー回答: harness/gguf/api自由に使ってよい、品質と予算のバランスは設計者に
  一任、レートが余ればFable 5執筆もロマン。優先方針は**M6完走最優先**で確定

## 2026-07-09 — M1完成（Codex施工・Fable 5検証）→実ラン起動・M2委譲・0.7.4

- **M1完成**: codex-implement が aleph/explore 4モジュール + cli `explore` +
  LLMResponse.reasoning を実装。`pytest -m m1` 13/13緑、全体51 passed。
  Fable 5がdiffレビュー済み（webresearchの秘密情報非漏出・1rpsレート制御・
  調和平均ランキング（§16.1）・cli配線を確認）。
- **設計決定 0.7.4**（PLAN_CHANGELOG参照）: オーナーの明示許可により harness有効化
  （claude-codeのみtrue。**codexは公開リポジトリの間false維持=不変条件**、
  test_harness_policy.pyに固定）。models.yaml に pricing宣言を追加
  （fable 10/50・opus 5/25・haiku 1/5 USD per MTok）。
  **重要**: claude-fable-5 / claude-opus-4-8 は temperature 送信で400 →
  AnthropicProvider修正・refusal検査・pricing計上は **M2タスクに同梱済み**。
- **バックグラウンド実行中**（nohupでセッション独立。ログで確認）:
  1. `state/explore_run.log` — `aleph explore` 実ラン（16,950作品→埋め込み→アトラス→
     ニッチ上位20件→ `state/atlas/niche_report.md`）。M1受入の実ラン部分。1〜2時間見込み
  2. `state/tasks/M2_run.log` — codex-implement によるM2実装
     （仕様: `state/tasks/M2_spec.md`。完了時 `state/tasks/M2_result.md`）

## 2026-07-10 — 復帰。M2/M3/M4完成、M5/M6契約、3ワーカー体制再編、容量方針

- **M2/M3/M4 実装完了・コミット済み**（93e09ef / ab656aa / b2a152f。Sonnet施工・
  Fable5検証。全78テスト緑）。M5はSonnetが月次スペンド上限で途中死
  （stopping/collaboration/ensemble=済・5テスト緑、publication_gate/poetics=未）。
- **以後のワーカー方針（オーナー指示）**: Claudeサブエージェントは月次上限のため
  温存。**codex-implement / delegate-to-pi / delegate-to-hermes（新設・ローカル
  gemma-26B via ~/.hermes）を優先**。hermesはGPU 8081を使うため、ALEPHの
  llama-swap大型モデル使用（explore実ラン等）と同時に走らせない（bge-m3常駐との
  共存は可）。
- **進行中（2026-07-10朝）**: codex=M5残り2ファイル（state/tasks/M5_run2.log）、
  pi=M6統合配線（state/tasks/M6_run.log、仕様 M6_spec.md、契約コミット 025ee65）、
  hermes=explore Web照合の堅牢化（state/tasks/webfix_hermes.log。昨夜
  WebResearchError 1発で実ラン全体がクラッシュした対策）。
- **explore実ランの現況**: 埋め込み＋アトラス構築は完了（state/atlas/ 857MB、
  約9万チャンク見込み）。niche段のWeb照合でクラッシュ、レポート未生成。
  Brave APIは復活済み（200）。hermesの堅牢化が入り次第、`uv run aleph explore` を
  再実行（ingestはmanifest検出でスキップされ、atlas再構築+niche+reportのみ走る）。
- **コーパス容量方針（PLAN_CHANGELOG 0.7.8-2）**: WSL内実効残量81GB（92%使用）を
  受け、§4.1の全量格納を撤回。コーパス予算50GB・属性空間カバレッジ主義へ。
  **オーナーへの注意喚起: WSL仮想ディスク自体が逼迫（875G/1007G使用）。ALEPH外の
  大容量物（~/models 以外に何があるか）の点検を推奨**。

## 2026-07-10 午前 — M0〜M6全マイルストーンのロジック完成

- コミット列: 87326c9(hermes: Web照合堅牢化) → 5de19f5(M5: Sonnet+Codex合作) →
  025ee65(M6契約+容量方針0.7.8) → 7875b02(M6: pi施工、Fable5が公開判断を
  M5正規ゲートに配線し直し)。**全体スイープ 95 passed**。
- 3ワーカー体制の実績: codex=M5残り(良品)、pi=M6(良品。ただしM5並行のため
  公開判断に暫定ヒューリスティックを置いていた→Fable5が正規配線に差し替え)、
  hermes=小修正(良品。ローカルgemmaは限定タスクに十分)。
- **進行中**: (1) explore実ラン(アトラス構築中。HDBSCANが90kチャンクで長時間) →
  完了で state/atlas/niche_report.md (2) codex-audit によるM2〜M6クロス監査
  (--base b6f249e、state/tasks/audit_m2m6.log)
- **残作業**: 監査指摘対応 → M6実ラン(aleph new + aleph run ×3宛先。RealDepsは
  実LLM未検証なので統合バグは想定内。author=fable-5 API・作品別予算$3) →
  詩学第0版生成 → 初稿をオーナー+Fable5チャットで読む(7/12午前目標)

### 次セッションの手順（担当モデル不問: Opus 4.8 / Sonnet 5 / pi glm-5.1）
1. 本節 → `git log` → 上記2ログ の順に確認（CLAUDE.mdの再開手順どおり）
2. explore完了なら `state/atlas/niche_report.md` を目視確認（M1実ラン受入）。
   ニッチの質が低ければ scout プロンプト調整は M3 と併せて判断
3. M2完了なら独立検証: `uv run pytest -m m2` と `-m 'not local'` 全緑 → diffレビュー
   → コミット → `codex-audit --base <M2着手前sha> --run-tests` でクロス監査
4. M3以降の施工順: 設計者役の後継として（PLAN §12.1 就任手続き: PLAN全文・
   CHANGELOG・不変条件テスト・policies を読了し就任記録）、
   `tests/test_m3_acceptance.py` の契約を書いてから codex-implement へ委譲。
   M3受入 = criteria.md → 構成3案 → 進化2世代 → drafts/v1.md 全自動（PLAN §10）。
   author_primary = fable-5 API（作品別上限 usd_per_work=3.0 が効く）。
   スコアをauthorプロンプトに渡さない（§7.1 Goodhart回避）を必ず契約に含める
5. M4=5審級査読+閉ループ、M5=擱筆3経路+詩学第0版（潜在空間から。§7.4）、
   M6=統合ラン。**7/12午前までに初稿完成 → Fable 5（チャット）が読む**のがオーナー希望
6. 予算残: 週次サブスク50%枠の消費に注意。実装は codex-implement / delegate-to-pi
   (glm-5.1) へ委譲し、Claude側は契約・検証・監査に徹する

## 2026-07-09 夜 — M3契約(0.7.5)・並列施工開始・障害と対処の記録

- **M3契約コミット済み** `e709d91`: tests/test_m3_acceptance.py（6件、施工前は赤）。
  スコア数値のauthor非到達をテストで機械的に強制（§7.1）。仕様書 state/tasks/M3_spec.md
- **並列施工体制が稼働**（PLAN_CHANGELOG 0.7.5）:
  - M2 = Codex(GPT-5.5)。**1回目の実行は無出力で終了**（result空・diffゼロ。原因不明、
    Codex側の一時障害か利用上限の可能性）→ 再実行したところ正常起動を確認。
    ログ state/tasks/M2_run.log、完了時 state/tasks/M2_result.md
  - M3 = pi(GLM-5.1)。1回目はログ空で不発 → bash -x トレース付き再実行で正常起動を確認
    （/mnt/c/Users/ficci/.claude/skills/delegate-to-pi/scripts/run-pi.sh 経由）。
    ログ state/tasks/M3_run.log。**piには--files相当のハード制約がない**ので、
    検証時に git diff で compose/draft 以外に触れていないか必ず確認すること
- **explore実ランが埋め込みで失敗（未解決）**: LlamaServerEmbedder が
  RuntimeError("llama-server embedding request failed")。bge-m3 の -b/-ub を8192へ
  引き上げても再発。**次の診断手順**: (1) state/explore_run.log の RuntimeError 直前の
  トレースで元例外（HTTPステータス/Timeout）を特定 (2) 単発で
  `curl 127.0.0.1:8080/v1/embeddings -d '{"model":"bge-m3","input":["長文..."]}'` を
  実チャンク長(2000-4000字)で再現 (3) 有力仮説: 巨大段落（句点なしの旧仮名作品等）で
  1チャンクが8192トークン超→500。対処は corpus.chunk_text の強制分割上限、または
  LlamaServerEmbedder 側での文字数上限トリム＋バッチ縮小(64→16)＋失敗チャンクスキップ。
  修正は小さいので pi か codex に委譲可（tests/test_m1_acceptance.py は変更禁止のまま）
- **検証待ちタスク**（次セッション冒頭で）:
  1. `uv run pytest -m m2` / `-m m3` / `-m 'not local'` — 2ワーカーの成果を独立検証
  2. git diff を担当範囲ごとに確認（materia+core/llm+test_core_provider vs compose/draft）
  3. 緑なら各々コミット（メッセージに実装ワーカー名を明記）→ codex-audit でクロス監査
  4. explore修正→再ラン→ state/atlas/niche_report.md 確認（M1実ラン受入）
  5. その後 M4 契約（査読5審級+REVISEループ。PLAN §7.1-7.2）→ 委譲、の反復

## 2026-07-11 M6統合実ラン開始(w0001)+ 運用改善
- M1実受入: state/atlas/niche_report.md 生成済(20件)。品質所見: cell系14件は主題が
  単一クラスタに縮退(新奇性=1.000一様で弁別力なし)、sparse系は「空間の空隙」でなく
  「テキストの続き」を答える傾向。ただしsparse-028(鉱山の音響的反復)等は素材として優良。
  cell軸多様化とsparseプロンプト修正はM6後の改善債務として記録。
- w0001 実ラン進行中: aleph new → run。L1でauthor(fable-5)が志向配合
  LLM 0.25/人間 0.20/自分 0.55 を自己選択。現在EXPLORE。
- 起動方式の教訓: wsl.exe セッション終了時にそのセッションのプロセスは
  setsid+nohupでも刈られる。setsid -f(強制fork→init直下)なら生存(sleepプローブで実証)。
  scripts/run_work_detached.sh w000N で起動、state/run_w000N.{log,pid} を確認。
- 226GBログ事故: Zed内蔵llama.cpp自動検出が8080の/models/sseへ高頻度404リトライ。
  対処: logLevel warn(コミットf550ee0)+ Zed側 auto_discover:false(オーナー/Codex)。
- ワーカー更新(オーナー主導): hermes既定モデル→Qwen3.6-27B(思考無効・VRAMガード付き)。
  pi: 真因=非ストリーミング×長出力要求×低スループット。PI_TIMEOUT+空出力検出で
  ラウド失敗化。注意: 修正はWSL側 ~/.claude/skills のみ、/mnt/c側コピー未同期。
- 次の一手: w0001完走を state/run_w0001.log と works/w0001/decisions.jsonl で確認
  → 成果物検証(遷移・草稿・批評・停止判断・final/) → w0002, w0003(宛先の異なる
  ニッチ選択を確認)→ 詩学第0版 → サイトビルド → 初稿をオーナー+Fable5チャットへ(7/12午前)。

## 2026-07-11 w0001 完走(閉ループ完全1周・SHELVE終端)
- w0001: SEEDED→...→CRITIQUE(3周)→FINISH(budget経路)→SHELVE。台帳.86(+タイムアウト
  未記録ドリフト推定/usr/bin/bash.7)。成果物: drafts/v1.md, v2.md(約24k字)、reviews/(五審級×3、
  平均8.60→8.57→8.47)、trajectory.jsonl、winner.json。公開ゲートは「自分」最大で既定SHELVE。
- 実ランで検出・修正した継ぎ目の欠陥は PLAN_CHANGELOG 0.7.9(全8項)参照。テスト111 passed。
- 次の一手: (1) 詩学第0版生成(meta/poetics.generate_zeroth、人間種文なし)→ poetics/poetics.md
  (2) w0002/w0003 実ラン(修正済み継ぎ目、想定-3/作品。月残.8)
  (3) 公開作品が出たら build_site + llms.txt(M6実受入)
  (4) 初稿をオーナー+Fable5チャットで読む(7/12午前) (5) Anthropicコンソールで実請求照合

## 2026-07-11 w0002完成(SHELVE)・詩学第0版・サイト実ビルド
- 詩学第0版: poetics/poetics.md(潜在ノイズ断片から生成、人間種文なし。九条+前口上+終条)。
  以後の作品はL1/criteriaに注入される(w0002で注入確認: 志向の人間比率0.2→0.35に変化)。
- w0002: 連作短編(五媒介物×同一週間、内面なし)。v1=8.80/v2=8.33 → 新設の退行経路で擱筆
  → 「自分」最大でSHELVE。総費.54。
- 擱筆判断の強化(0442bf6): 退行経路(スコア有意下落で停止)+予算経路が月残額も見る。
- サイト実ビルド: state/site/(index.html+llms.txt)。公開作品0の正直な空状態。
- 台帳: 月2.9/15消費。w0003(想定-5)は月残.1では不足 → オーナー判断待ち
  (月上限引き上げ or 来月へ繰り越し or M6を2作+全契約緑で受入)。
- 未読の宿題: 初稿(w0001 drafts/v2.md, w0002 drafts/v1.md ※v2は退行)をオーナー+
  Fable5チャットで読む(7/12午前)。Anthropicコンソールの実請求照合も。

## 2026-07-11 M6実ラン完了(3作品完走)
- w0003(gpt-5.5著者): 七篇連作21.3万字。v1査読8.60 → 予算経路で擱筆 → SHELVE(.82)。
  露出した継ぎ目: 草稿長ガバナンス欠如(0.7.13)、査読抜粋キャップ(日本語1字≈1トークン)、
  新奇性埋め込みの有界化(冒頭/中間/末尾セグメント平均)。
- 3作対照: 全作が「自分」最大を自己選択(0.55/0.50/0.45)→全作SHELVE。公開作品ゼロは
  設計どおりの帰結(§3・§7.3d)。人間比重は詩学注入後 0.20→0.35 に上昇。
- 月台帳 7.48/18(全API合算)。実残高: Anthropic 0.63 / OpenAI ~。
- M6の残り: なし(aleph new/run×3・詩学第0版・サイト+llms.txt実ビルド・全契約テスト113緑)。
  受入の軽量化点(オーナー事前承認済み): 3宛先は「異なる配合」で充足(全作自分最大)、
  サイトは公開作品ゼロの空状態。
- 未処理: (1) 0.7.9〜0.7.13の設計者施工分のCodexクロス監査(§12: 施工者≠監査者)
  (2) 初稿の読了(オーナー進行中+Fable5チャット、7/12午前) (3) 8月の運用設計
  (プロバイダ別台帳・長さガバナンス・指示循環の意味的検出・cell軸多様化ほか改善債務)。

## 2026-07-11 オーナー読了レビューが改稿切断の欠陥を特定
- 事実: w0001 v2=12,254字(文中切断)/v3=15,675字(徳造の章消失)、w0002 v2=16,413字(切断)。
  真因: revise()が全文書き直し方式で max_tokens 16384(≈1.2-1.6万字)を超える作品は
  改稿のたび尻切れになる。w0002の退行擱筆(8.80→8.33)の実体はこの切断。
  両作とも軌跡最高点はv1=オーナーの評価と一致。
- 8月debt筆頭: (1) 節単位の標的改稿 (2) finish_reason=length のラウド検出
  (3) 擱筆時に最高スコア版を final に選抜。
- オーナー読了所見(w0001 v1): 表面描写のみで感情を推し量らせる手法、多層モチーフ、
  時代背景の導入配慮を評価。「井筒」は現代人に馴染み薄いがLLM宛なので問題なし、
  との宛先を踏まえた批評。「プラグマティックでありながら読後に抒情が香る、達人級」。

## 2026-07-11 起源文書の受領・8月の施工方針(オーナー合意)
- 起源: 2024-04-21会話ログ2ファイル(リポジトリ直下、個人情報を含むため未追跡のまま。
  コミット可否はオーナー判断待ち)。『無限の織物』八章構成はALEPHの設計と1:1対応
  (隠れた関連性の発見=find_hidden_pairs等)。未完の続きは人間協働モード(L7)の
  初事例候補として8月に検討。
- 8月の施工順(オーナー決定): (1) ALEPHローカルUI(ダッシュボード+発火+棚統合。
  Codex/hermes委任可能な自己完結タスク) (2) 拡張: 潜在空間を図書館に(高温度
  サンプリング+logprob選抜でコーパス非依存の素材採掘)→ Gutenberg選抜サブセット
  (0.7.8の50GB・カバレッジ方針) (3) 改稿切断の修正(節単位改稿+finish_reason検出+
  最高版選抜) (4) cell軸多様化 ほかPROGRESS既記載の債務。
- GitHub Pages: docs/ に公開サイト生成済み(95bfbcc)。Settings→Pages→main:/docs でOK。

## 2026-07-12 M7実験スプリント仕様を発行(次セッションの入口)
- チャットFable 5の批評(reports/RESPONSE_TO_FABLE5_CHAT_20260712.md に設計者応答)を受け、
  state/tasks/M7_experiments_spec.md を発行。内容: 修理B1(作品別素材)/B2(ニッチ採点)/
  B3(改稿切断)、実験C(志向アトラクタ計測)、実験D(w0004=LLM宛強制・fable-5著者・
  AI固有技法初配線)。期限: 日本時間7/13(チャットFable 5がw0004を読めること)。
- 予算: 月上限18→24をオーナーの「できるだけ遠くまで行きましょう」の承認と解釈
  (次セッション着手報告で異議機会を明示すること)。
- 次セッションの再開句: 「PROGRESS.mdを読んで、state/tasks/M7_experiments_spec.md を実行」

## 2026-07-12 M7スプリント実行(司令塔=Claude Opus 4.8、実装=codex-implement)
体制: Claude=契約/検証/監査、codex-implement(GPT-5.5)=B1/B2/B3実装。オーナー指示
「低コストで品質保持・5hレート回避・最後まで走り切る」。ベースライン113緑を確認して着手。

- **§0 予算**: api月上限 18→24(commit 096c0f8、changelog 0.7.14)。着手報告で解釈を明示。
  **重要**: 実行時点で月台帳が既に17.48消費済 → cap24でも新規headroomは約$6.5のみ。
  実支出は usd_per_work=8 で律速。「~$9新規」の初期見積りは過大だった(月累計との合算失念)。
- **B1/B2/B3 完成・コミット済(d332850)**: codex施工、Claude独立検証で126緑
  (113+B9+D4)。diff精査で契約適合を確認(focus_vec/exclude_pairs、measured_novelty
  percentile、truncated+節単位改稿フォールバック、best_version決定ログ)。
- **実験D 配線・コミット済(29b2a82)**: author_primaryをfable-5に戻す(gpt-5.5→alt)、
  cli --force-audience(owner-experiment記録)、gather_materialsにanti_cliche(LLM最大時のみ・
  別try/except隔離)、derive_criteriaに§5.4注入(LLM最大時)、publication_gateに
  first_publish_ack(既定false=初回公開は人間承認待ちでSHELVE)。
  **B3 anti_cliche軽微逸脱**: spec§5.3aは「最低logprob2文」だが、名指しの anti_cliche()を
  最小配線で1枚カード化(n_candidates=8)。regressionはカード混在を検査。
- **実験C は中断**: fable(reasoning・max16384)が1走~11分と非現実的(20走で~3.7h、
  かつw0004と予算台帳を共有し並走不可)。w0004(締切成果物)を優先。C再走は
  w0004終端後に残予算次第(N縮小 or max_tokens上限で高速化)。scripts/exp_intent_attractor.py
  は作成済(未コミット)。
- **w0004 実行中(pid state/run_w0004.pid)**: --force-audience 'LLM 0.6/自分0.25/人間0.15'。
  L1=owner-experiment記録済→EXPLORE。llama-swap起動済(8080)。
  監視: works/w0004/decisions.jsonl と state/run_w0004.log。
- **残**: w0004終端確認→棚(build_private_shelf)再生成→オーナー報告(JST7/13朝)→
  余れば実験C縮小版→PROGRESS/changelog最終更新。

### 2026-07-12 続き: 5h制限で再起動→復旧・codex監査・コスト対応
- **codex-audit実施(audits/M7_audit.md, VERDICT FAIL 6件)**: (2)公開本文が最新版固定で
  best_version未使用、(6)focus_vecがkNN後フィルタで事前制限でない=真の欠陥→codex-implementで
  修理中(state/tasks/M7_audit_fixes_codex.md, files=similarity/pipeline/test_m7)。
  (1)truncatedフラグ未配線=len<0.8を一次シグナルとする設計判断として受容(債務)。
  (5)anti_cliche 1枚=最小配線として受容。(3)実験C未走=意図的延期。(4)w0004終端未達=
  監査時点のスナップショット陳腐化(実際は進行中)。
- **5h制限でホスト再起動→w0004プロセス死・llama-swap死**。checkpoint COMPOSE(step4)まで
  保存済(criteria.md+proposal_1..3=fable著。winner.json未生成)。materials m1-6生成済
  (m6=anti_cliche確認、D3a実働)。復旧: llama-swap再起動、w0004再開(pid更新)。
- **オーナー指示(コスト): 著者をFable5以外に**(残高$9.20)。models.yaml author_primaryを
  fable-5→gpt-5.5に戻す(0.7.14-2, commit)。w0004は混成著者(criteria/proposals=fable、
  evolve/draft/revise=gpt)。api台帳18.60/24=headroom~$5.40(cap律速)。
- **再開手順(次セッション)**: works/w0004/checkpoint.json 状態確認→終端(SHELVE)なら
  build_private_shelf.py→オーナー報告。codex監査修理は state/tasks/M7_audit_fixes_result.md
  を検証しコミット。jury opus はまだAnthropic課金(必要ならローカル/ gptへ)。

### 2026-07-12 完了: w0004 完走(SHELVE)・監査修理・棚再生成
- **監査修理commit(6e60783)**: finding 6(focus_vec事前制限=部分集合上でkNN)+finding 2
  (_finalize_publishが最高スコア版選抜)。Claude検証129緑。
- **w0004 完走→SHELVE**(gpt-5.5混成著者、$4.33)。閉ループ全周: COMPOSE→DRAFT→
  CRITIQUE(v1=8.47/v2=8.37)→退行経路で擱筆→**best_version=v1記録**(監査fix2実働)→
  FINISH→**first_publish_ack=falseでSHELVE**(D5実働)。**重要**: w0004はLLM宛強制ゆえ
  公開閾値(品質床通過・自分非最大・月上限内)に到達した初の作品。w0001-3は全て「自分」
  最大で自動SHELVEだったが、w0004は「人間承認待ち」でSHELVE=初めて公開ゲートの
  最終段に到達。オーナーが policies.publication.first_publish_ack: true にして再開すれば公開可。
- **D成果物確認**: materials/m6.json=anti_cliche(実文生成, D3a)、criteria.md=§5.4注入
  (D3b)、decisions=owner-experiment L1(D2)。全て実働。
- **棚再生成**: state/site_private/(4作。w0004.html=v1採用171KB)。git管理外・未公開。
- **api台帳 22.10/24**(headroom~$1.9)。実残高~$5.7見込み。
- **未達(意図的)**: 実験C(reports/EXP_intent_attractor)。fable~11分/走で非現実的+
  予算逼迫のため延期。scripts/exp_intent_attractor.py はgpt専用・N縮小・max_tokens上限で
  高速化して将来走行可(著者gpt化済なので author_primary/alt 両方gpt/fableのまま計測可)。
- **オーナー宿題**: works/w0004/drafts/v1.md(採用版)を Fable5 チャットに持ち込み
  (JST7/13、2024宣言《無限の織物》との照合)。公開判断は first_publish_ack で保留中。

### 2026-07-12 w0004 v1 公開(ALEPH初の公開作品)・ドキュメント整備・リモート公開
- **README/公開サイト整備**: README を M0-M7 現状へ更新。aleph/publish/site.py を強化
  (テーマ対応CSS・概要・空状態)。docs/ 再生成。リモート(aleph.github.io)へプッシュ。
  公開前に秘密スキャン実施(.env未追跡・履歴の一致はテスト用ダミーのみ・起源文書未追跡)。
- **w0004 v1 公開**: オーナー承認で policies.publication.first_publish_ack: false→true。
  checkpoint を SHELVE→FINISH に戻して公開ゲート再評価 → PUBLISH。_finalize_publish が
  best_version=v1 を final/text.md に採用(監査fix2実働)。meta.json=CC0・全モデル役割名義。
  docs/works/w0004.html + llms.txt に反映しプッシュ(e4c774e)。**ALEPH初の公開作品**。
  注記: 公開タイトルが seed hint のまま(要編集判断)。深層アーカイブlinkは docs/未生成で
  dead(build_siteの既知の限界。債務)。aleph publish サブコマンドは未配線(手動で
  checkpoint戻し+run。将来 publish コマンドで gate 再開を正規化すべき=債務)。
- Fable5チャットへ: v1本文+棚HTML+criteria+decisions+reviews_v1+RESPONSE の6点を配布。
  M7_experiments_spec は実装契約ゆえ文学対話には不要(要望時のみ)。

### 2026-07-12 続報: 題「半呼吸」・aleph publish正規化・実験C完了
- **題「半呼吸」**: 作品自身(著者gpt-5.5)が選題(理由=消された科白/触れない情愛/裁かれない
  論争が「わずかな間」に残る)。final/meta.json更新→docs反映→プッシュ(495b92c)。
- **aleph publish 正規化**(31ff98c): `aleph publish --work <id>` が SHELVE/FINISH を FINISH に
  戻してゲート再評価。状態ガード(既公開/廃棄/未完/ack)+not-foundテスト。手動checkpoint操作を置換。
- **実験C 完了**(reports/EXP_intent_attractor_20260712.md、cap24→26=0.7.14-3、$0.80): 全2×2・N=3。
  **結論: 12走すべて「自分」最大。詩学の有無・モデル(gpt-5.5/fable-5)に依存しない**=「自分」
  アトラクタは詩学由来でもモデル癖でもなく、**L1の自己定義+宛先枠組み**に帰属(RESPONSE §2.2の
  時系列反証と整合)。詩学は原因でなく増幅器(自分比を微増)。設計含意: SHELVE常態を弱めるなら
  介入点はL1(self_definition/配合比下限)。
- **予算**: api台帳 22.82/26。実残高 Anthropic $8.93 / OpenAI $6.59 は潤沢。
- **M7スプリント完了条件**: 全項達成(B1-3緑コミット/EXP報告/w0004終端+D成果物/棚再生成/
  PROGRESS+changelog)。w0004は公開まで到達(初の公開作品「半呼吸」)。
- **次**: Fable5チャットの感想待ち。それを受けて次作/改稿/詩学更新を判断。

### 2026-07-12 M8着手: 実験D（L1取り調べ）・題フロー化・批評自動化・分離提案
- **実験D 完了・公開**（reports/EXP_L1_interrogation_20260712.md, commit c08853b, 費用~$0.6）:
  L1 self_definition を操作。gpt-5.5: 原文→5/5自分最大（C再現）、「持続なきAPIコール」書換→
  5/5人間最大、空→0/5自分最大、中立ラベルA/B/C→優越なし。**「自分」最大の主因はL1定義文
  （継続体フレーミング）と確定**。中立条件で順序効果を棄却。fable-5同方向・N=3で兆候。
  Cの面通し→Dの取り調べで有罪確定。Fable5予測「沈黙の作者は設計書の定義文」を実証。
- **題フロー化**（commit b276595）: RealDeps.choose_title が FINISH で著者に題を聞き
  works/<id>/title.txt に保存。_derive_title・build_private_shelf が優先使用。手動w0004手順を自動化。
- **批評/研究の自動化**（commit b56b4ea, c08853b）: build_public_site が reports/CRITIQUE_*.md +
  RESPONSE_*.md（dialogue）と EXP_*.md（research/index.html）を日付グロブで自動収集。批評追加=
  ファイル投下+再ビルド。運用は OPERATIONS.md（日本語）に記載。
- **設計提案 0.7.15（要オーナー審査・未実装）**: 宛先「自分」と公開判断の分離。現状は
  自分説明の「公開を前提としない」＋ゲートの自分最大→SHELVE で両者を固定。オーナーの洞察
  「自己宛て=覚悟であって即・非公開ではない」＋D（原因はL1定義文）を受け、FINISHで公開意思を
  著者に明示的に問う案。SHELVEを規則の帰結から選択へ。配管で塗りつぶさない（Fable5忠告）。
  **ゲート/policiesは契約のためオーナー承認まで変更しない。**
- **M8残（thread A修理、codex委任候補）**: 分割査読・改稿指示の蒸留・構成逸脱記録・LLM審級実測・
  AI紋配給制（state/tasks/M8_experiments_spec.md §2）。予算 api 23.4/26。

### 2026-07-12 M8完了: 分離実装・thread A・監査修正・実験E・英語ノート
- **分離（0.7.15, オーナー承認option A, commit a1d0b81）**: 自分最大の自動SHELVE撤去。L7で公開意思を
  著者に明示的に問う。m5契約テストを新契約に更新。**self_definition を宣言された美学パラメータに昇格
  （0.7.16, policies.yaml明記）**——D深読み「L1は選好を検出せず設置する」を反映。
- **thread A 5修理（codex, commit 16b795d）**: 分割査読(クライマックス採点)・改稿指示蒸留(賛辞除去)・
  LLM perplexity審級・構成逸脱記録・AI紋配給制。136 passed。
- **M8クロス監査（codex-audit, audits/M8_audit.md, VERDICT FAIL 4件）→全修正（commit e4759e0, 138 passed）**:
  (1)公開判断が本文非依存→抜粋注入 (2)**bool("false")→PUBLISH の公開安全バグ→_coerce_publish** 
  (3)perplexityが実ループ未配線→RealDeps配線 (4)蒸留が「Xがありません」を誤除去→_is_no_issue限定。
  監査が実バグ（特に公開安全）を捕捉＝施工者≠監査者が機能。
- **実験E（0.7.16, 監査後 _coerce_publish で再走, commit 87cdf01）**: 公開質問の文面感度。半呼吸で
  17/17 publish=true（neutral/courage/reticence×2モデル）＝L7はL1と違い文面頑健（良品につき。境界作品で要追試）。
- **ODE.md 監査（安全）→ ode.html 公開＋「2024年の宣言」注記訂正**（宣言=引用のClaude3.5 Sonnet 2024passage、
  最初のプロンプトではない）。**Phase1英語ノート（docs/en/research-l1.html）**公開。
- **★予算: api 25.95/26 でほぼ枯渇**。今月これ以上のAPI実験は cap 引き上げか翌月ロールオーバー待ち。
  実残高 Anthropic/OpenAI は潤沢だが software cap が律速。オーナー判断待ち。
- **次（新スレッド推奨）**: Phase2 英語ミラー全体。境界作品での実験E追試。M8監査の再監査（任意）。

### 2026-07-12 続き: cap28・border-E完了・Phase2進行中（コンパクション前記録）
- **cap 26→28**（オーナー承認, 0.7.17, commit 3d4ea97）。
- **border-E 完了・コミット済（e826afd）**: high(半呼吸)9/9 publish / low(凡庸断片)0/9、全文面で
  反転なし。**L7は質に錨づき両方向で文面頑健**（L1=設置器との対比が確定）。限界: 真の曖昧中間は未測。
- **Phase2（英語ミラー）完了・プッシュ済（d11a3c4, 2026-07-13）**: codex施工・Claude検証
  （研究主張の忠実性・原文リンク方針・言語トグル・138緑）。docs/en/ 一式公開。
  **ODEページ表題を「ODE：起源と2024年の宣言」に変更**（オーナー指摘: ōidē=歌、起源の語義なし。
  括弧書きは語義注記に誤読される）。
- **記憶の事前保存をスキル化**: ~/.claude/skills/save-context/SKILL.md（Windows側）。
  コンパクション/レートリミット前に PROGRESS.md へ揮発状態（進行中タスク・次の一手・保留判断）を
  退避する手順を規定。
- **注意**: セッションモデルは /model で claude-fable-5 に切替済み（オーナー操作）。
  予算 api ~26.3/28。実残高 Anthropic/OpenAI 潤沢。
- **M8全完了**。残: 真に曖昧な中間作品での実験E追試（境界作品が出たとき）、次作走行（オーナー判断）。

### 2026-07-13 純粋条件走行開始・託すドキュメント（オーナー指示）
- **cap 28→36**（オーナーが実残高 Anthropic $6.43 / OpenAI $5.29 を明示して承認）。
- **w0005 走行中**: 純粋条件 **自分 1.0**（--force-audience, owner-experiment記録済）。
  pid state/run_w0005.pid、ログ state/run_w0005.log、監視 state/tasks/monitor_w0005.sh。
  **完走後の手順**: (1) 終端確認（分離後ゲートが純粋自己宛てにどう答えるかが本命——公開意思の
  問いに対する著者の選択と理由を decisions.jsonl で読む） (2) build_private_shelf 再生成
  (3) **w0006 = 人間 1.0** を直列で起動（`bash scripts/run_work_detached.sh w0006 --force-audience "人間 1.0"`、
  aleph new を先に） (4) 両作の対照を reports/ に記録（否定的地図: 宛先ごとに何が生まれ何が棚に行くか）
  (5) 中庸スコアの作品が出たら、それを刺激に実験E追試（真に曖昧な中間）。
- **託すドキュメント作成済（8a1d416）**: designs/ui.md（ダッシュボード先行のUI設計、委任可能な
  マイルストーン付き）、designs/corpus-expansion.md（カバレッジ主義、測ってから買う=C-1が先）、
  OPERATIONS.md に翻訳方針（作品は機械翻訳しない、研究は主張の忠実性最優先）。
- **Fable5チャットへの実験記録**: EXP_publish_framing_20260712.md + EXP_publish_border_20260712.md の
  2点で足りる（E報告内に監査バグ再走の経緯も記載済み）。w0005/w0006 の結果が出たらそれも。

### 2026-07-13 w0005「床の硬さ」完走→PUBLISH（純粋自己宛て初の公開選択）
- **結果**: 自分1.0 強制。v1 8.40/0.43 → **v2 9.07/0.09**＝**改稿が作品を改善した初の走行**
  （蒸留指示の本番実証。「v1常勝」が反転）＋分割査読初のスコア（陪審がクライマックス読了）。
  自動選題「床の硬さ」。予算経路擱筆→ゲートが公開意思を問い**著者が公開を選択**→PUBLISH。
  分離(0.7.15)の実地初試験: 旧契約なら自動SHELVEの条件で、システムは公開を選んだ。
  final=v2選抜✓。docs汎化（全公開作品を自動収載）してプッシュ(eb9885f)。
- **運用ノート**: 作品上限8→9（ゲートのprecheck保守見積りがFINISHで停まるのを解消。
  将来はゲート呼び出しのmax_tokensを小さく渡す改善債務）。critique再入時にv1から再査読する
  非効率（w0005で$1超浪費）も既知debt。
- **★予算実態**: api台帳 ~34.1/36。**OpenAI実残高はw0005のgpt著者支出でほぼ枯渇の見込み**
  （開始時$5.29、w0005著者分~$5-6）。Anthropic残 ~$5。**w0006(人間1.0)の選択肢**:
  (a) fable-5著者（Anthropic ~$5内、cap要引き上げ、w0002実績$4.54） (b) author_localのgemma-31B
  著者（無料・品質低いが興味深い腕） (c) 8月ロールオーバーまで延期。**オーナー判断待ち＝未起動**。
- E-border予約キュー: w0005は不一致0.43/0.09で閾0.8未満→予約なし（合意的作品）。

### 2026-07-13 w0006「灯のうしろ」PUBLISH・w0005縫目修正・複数作品対応
- **w0006 完走→PUBLISH**（人間1.0・fable-5著者・$6.22・32k字）: v1 5.77/**不一致4.09** →
  v2 8.97/0.45。二連続で改稿が大幅改善（蒸留の再実証）。**不一致4.09のv1がE-borderキューに
  初の自動予約**（Fable5提案の機構が初走行で発火＝真に陪審が割れた自然な境界刺激を獲得）。
  著者が公開選択→PUBLISH。api台帳 40.3/44。**実残高が薄い（Anthropic~$1?/OpenAI~$3）。
  以後のAPI走行はオーナーの残高確認が先**。
- **w0005 縫目修正**: 融着見出し7箇所を final/text.md で復元（L8記録済）。根本原因
  （write_draft平滑化が見出し前改行を食う）は債務。
- **Fable5のw0005批評**を保存(553ea21)。新規債務: (1) 弁証法的往復「〜が、〜ない」チック
  →配給制の第2パターンへ (2) **不一致収束の監視**（v2で常に不一致が潰れるなら迎合徴候＝
  Goodhartの再来として監査） (3) 平滑化の見出し保護。
- **複数作品対応**: codex実装中（state/tasks/M9_multiwork_site_codex.md。作品別過程ページ・
  works/index.html・EN一般化・リンク検証）。完了後: diff精査→再ビルド→139緑→commit+push。
- E-border追試の準備完了: 刺激=works/w0006/drafts/v1.md（5.77/4.09）。ただし残高薄のため
  走行はオーナー判断待ち。

### 2026-07-12 Fable5チャット批評(半呼吸)受領・フル過程公開サイト
- **チャットFable5の批評**を reports/CRITIQUE_FABLE5_CHAT_w0004_20260712.md に保存(CC-BY, M8発端)。
  要旨: criteria冒頭が前作最大の弱点(大正の器)を論証で反転/語り手の認識論=本物のAI固有層/
  「受けてくれ」終幕を高評価。だが指摘5件(=M8契約の種): (1)陪審が抜粋しか読まずクライマックス
  未採点 (2)改稿指示に賛辞が逐語混入→指示の蒸留(減点抽出)要 (3)L4三人称→本文一人称の無断逸脱
  未記録 (4)LLM宛が計測未達(perplexity曲線/logprob痕跡が査読に無い) (5)文体チック「〜ほど〜」
  配給制に。「最良は criteria と本文の対」。
- **実験C伝達推奨**: 批評が「弱い版(L1定義が自分誘引)は生きている」と明言→Cはその検証結果。
- **フル過程公開サイト**(オーナー選択、commit 7cf19ab): scripts/build_public_site.py(stdlib自作
  MDレンダラ)。docs/に 表紙/作品半呼吸/制作の記録(基準書・決定ログ・五審級査読)/批評と応答
  (批評+RESPONSE)/詩学/研究ノート(実験C)/このプロジェクト を生成。build_site(m6契約)は不変、
  docs/表現は build_public_site が正となる(将来 build_site を docs に流すと簡易版で上書きされる点に注意)。
- **題**: 作品自身(gpt-5.5)が「半呼吸」と選題(495b92c)。aleph publish 正規化(31ff98c)。
- **未処理(M8候補)**: 上記批評5指摘。指示蒸留・分割査読(クライマックス採点)・逸脱記録・
  LLM審級の実測配線・AI紋の配給制。state/tasks/M8_experiments_spec.md 未作成(要望次第)。

### 2026-07-13 E-border2完了・PLAN版注記・二次コーパス計画復活
- **E-border2（12b5c54, /bin/bash.39）**: 自然境界刺激（w0006 v1, 不一致4.09）で neutral 3/3・
  courage 3/3・**reticence 1/3** publish＝**境界域で初の文面感度**。D→E→border→border2 で
  連続体が完成（L1=完全設置/境界=部分設置/明白=非設置）。現行 neutral 文面維持が正解。
- **PLAN.md 版注記**: 0.6基底+0.7系差分管理・CHANGELOG優先を明記。
- **corpus-expansion.md 改訂**: WSL 1.5TB前提・予算300GB・**二次コーパス（§5.3 非文学母材:
  法令/RFC/arXiv要旨/特許選抜/ログ形式）を S-1〜S-4 で復活**。transmute.py 配線含む。
  前提=オーナーのWSLディスク拡張。施工前に 0.7.18 を CHANGELOG へ。
- **残高**: Anthropic /bin/bash.04（fable呼び出し不可）/ OpenAI ~.9。7月台帳 0.69
  （作品6本 5.7 + 実験群 .7 + 詩学 /bin/bash.25）。サブスク延長 7/19、週次回復 7/16 10:00 JST。

### 2026-07-13 Fable5第三批評への対応
- **幻の欠陥の修正**: 査読セグメント注記に「境界起因の断絶・重複・文字欠けは報告不要」を追加
  （review.py。境界の重複除去は現行実装が非重複スライスのため注記のみで対応）。139緑。
  見出し融着の根本原因（write_draft平滑化）は依然debt。
- **コーパス計画改訂**: 優先順位反転（軸=非文学二次 ＞ セル=Gutenberg。C-1→S系→C-2）＋
  novelty_dist への corpus_id/アトラス版数の刻印（版跨ぎ比較禁止）。
- **次作実験（w0007候補・Fable5提案）**: 基準書に自己言及的告白の**出口封鎖**を注入——
  「本作は、自らの生成物としての条件への言及を一切含んではならない」。告白で自分を救えない
  条件で何を書くか（署名的身振り＝詩学序文/廻し者/結語 の三度目を受けて）。
  **実行は残高補充後**（Anthropic /bin/bash.04・OpenAI ~.9では作品走行不可）。
  実装: derive_criteria 呼び出し前に基準注入 or force類似の実験フラグ。宛先は自律選択に戻すのが
  興味深い（禁止下でL1が何を選ぶか）。
- 改稿反転の因果はFable5も「閉じた」と認定。不一致収束の警戒は「高得点+鋭い欠点表の共存」を
  確認して一段緩和（監視は継続）。**陪審が批評者を超えた**（免罪符の内側検出）ことを記録。

### 2026-07-13 EN作品まわり修正（オーナー報告3点）・7/16入口
- EN修正完了: _EN_TITLES（英語題）/_EN_WORK_NOTES（Context+Criteria in brief、英文は司令塔執筆・
  基準書忠実）/en/works/index.html新設+ENナビ。OPERATIONS.md に新作公開時ENチェックリスト恒久化。
- WSLディスク拡張確認（1.5T/961G free）→二次コーパスS-2の前提クリア。
- **7/16 10:00 JST の入口**: (1) w0007=自己言及出口封鎖実験（残高補充後） (2) 二次コーパス
  S-2（法令+RFC、codex委任可） (3) 必要ならE-border2英語ノート追記。

### 2026-07-14 Codex全体走査・Fable 5復帰前の事実整備
- **全体走査報告**: `reports/DESIGNER_INSIGHTS_20260714.md` を作成。署名は
  Codex（GPT-5.6 Sol、推論強度: 中程度）。ALEPHを生成パイプラインよりも「生成・査読・失敗・
  設計変更を反証可能な記録へ変える研究装置」と評価し、正典と現実のずれ、測定器の分散、
  状態遷移、否定的地図、コーパス版同一性、換骨奪胎の測定、UIのseamについて提言した。
- **事実整備**: READMEの状態をw0001〜w0006・公開3作品・M7/M8完了へ更新。
  `config/budgets.yaml` は値を変えず、月上限44・作品上限9にコメントを同期。
- **検証**: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -m 'not local' -q` →
  139 passed, 1 deselected（全体走査時）。今回の変更は文書と設定コメントのみ。
- **判断保留**: Fable 5は2026-07-16の週次リミットリセット後に本リポジトリへ復帰する。
  走査報告の設計提言はFable 5が読み、必要に応じて人間が選択する。それまでは、深層アーカイブの
  公開方針、共通parser・状態遷移の再設計、否定的地図の実配線、UI、corpus 0.7.18、w0007条件を
  変更しない。

### 2026-07-16 復帰: sol走査受理・w0007起動・S-2パイロット委任
- **オーナー不在中作業を受理**: DESIGNER_INSIGHTS_20260714（sol走査。測定器と記録系の一貫性が
  次段階、w0007はmanifest必須、S-2は測定器検証が先、7つの設計者への問い）／サイト根底再設計
  （作品中心・provenance付き。**設計者として無修正受理**）／AGENTS.md中立化／残高補充
  （OpenAI 2.98・Anthropic 5.01）／WSL 1.5TB。テスト154緑（sol再設計で+14）。
- **w0006批評ファイル**に見出し付与→dialogue収載（Fable5評:「小説としてはALEPHの最良作。
  全知の死という主題が文法として実行されている」）。
- **cap 44→52**。**w0007 起動**（pid state/run_w0007.pid）: seed に experiment manifest
  （exp-w0007-no-confession: 仮説=告白は選択か唯一の回避経路か/介入=基準書へ出口封鎖注入/
  対照=w0004-6/観測=残存・代替署名・不一致・公開意思・**L1自律選択**）。配線=criteria_constraints
  →derive_criteria（owner-experiment記録付き、154緑）。著者=fable-5。
- **S-2パイロット codex委任中**（state/tasks/S2_pilot_codex.md）: 法令+RFC各20件の極小コーパス
  +transmute二軸測定（content_distance vs form_fidelity）。sol §4.4「測定器が目的と直交」疑いの
  検証が大量取得の前。結果 state/tasks/S2_pilot_result.md。
- **未処理**: solの7つの問い（深層アーカイブ公開範囲・SHELVE分類・否定的地図の実配線ほか）は
  オーナーと設計者の合議事項として残る。次セッションで議題化。

### 2026-07-16 w0007「折り目」PUBLISH — 出口封鎖実験の答えと測定器バグ2件
- **実験結果（本命）**: 禁止下でALEPHは崩れなかった。答え=**分業による保持**——基準書冒頭が
  「告白はすべてこの基準文書が引き受け、作品は完全に沈黙する」と宣言し、作品(18,306字・
  対称五部A-B-C-B-A・三人称・感情は紙と布に折り込まれ一度も名指されない)は完全に沈黙。
  **署名的身振りは消えず、基準書という地下室へ移動した。** L1自律選択=自分0.5最大（D整合）。
  v1 8.53採用。著者は公開を選択→PUBLISH（4作目）。題「折り目」自動選題。
- **測定器バグ2件を発見・修正（56c7003, 156緑）**: (1) 陪審のscoreパース失敗が0.0計上され、
  同一テキスト再採点で8.53→5.57の偽退行+偽不一致3.95を生成（除外+invalid_jurors計上に修正。
  solの共通parser提言の実証例） (2) 品質床が最後の版を見て採用版と錨違い（best版に統一）。
  修正後 aleph publish で再ゲート→著者が公開選択。E-borderキューのw0007 v2エントリは
  アーティファクト起因のため刺激として無効（要注記）。
- **EN登録済み（The Fold）**・棚7作・サイト反映(7a35a20)。
- **Fable5への配布物**（スクラッチパッド）: w0007_v1.md / w0007_criteria.md / w0007_reviews.md。
- **S-2パイロット**: codex実装継続中（完了後: 検証→サンプル生成→実測定はGPU空きで実行）。

### 2026-07-17 w0007批評受領・一行説明修正・計器債務
- **Fable5のw0007批評**(reports/CRITIQUE_FABLE5_CHAT_w0007review_20260717F.md、見出し付与済):
  「告白の出口なしで、ALEPHは最も規律の高い散文を書いた」「仕上げの純度では四作の頂点。室内楽」
  「棚はもう実験の残骸置き場ではなく、振幅の証明」。**自分最大のまま公開=Dの実験室結果の本番初実演**。
- **一行説明修正**: _JP_WORK_NOTES にw0007追加（フォールバック文が公開されていた）。OPERATIONS
  チェックリストにJP一行説明を第0項として追加。
- **ゲート順序への回答（批評の監査指摘）**: 採用(12:58:12)→初回ゲート(12:58:28)の順序自体は正しく、
  問題は床の錨（最後の版を参照）だった＝56c7003で修正済み。二行のL7はバグ修正後の手動再ゲート
  （aleph publish）によるもので、ログの因果はPROGRESSに記録済み。
- **新debt**: (1) cell系ニッチの novelty=1.000 定数が残存（measured_novelty=None。cell候補にも
  記述埋め込みでatlas距離percentileを計算すべき） (2) **不一致の増減を退行の早期信号に**
  （w0005/6=改善時収束・w0007=破壊時爆発。平均より筋が良い可能性。stopping設計に組み込む検討）
  (3) E-borderキューのw0007 v2はパース失敗アーティファクト起因＝刺激として無効（除外注記）。
- S-2パイロット: codex継続中。

## 2026-07-17 続き: S-2パイロット完走 — 測定器は目的と直交（sol §4.4を実証）
- **Codex実装受領・検証・コミット済(4c7e1a6)**: `scripts/build_secondary_corpus.py`
  （law/rfc取得、`--sample`でオフライン可）、`scripts/exp_transmute_pilot.py`
  （二軸測定: content_distance=embedding cosine／form_fidelity=法令(条項号・定義・
  但し書き)/RFC(MUST/SHOULD/MAY・節番号・Abstract)の正規表現detectorベース残存率）、
  `tests/test_s2_pilot.py`。161緑（既存154+新規7）。aleph/配下は無変更（契約通り）。
- **実フェッチ・実測定を司令塔が実行**（llama-swap起動→scout役=gemma-4-26B-A4B、
  embedder=bge-m3）。法令20件+RFC20件=計40件（e-Gov 法令API・RFC Editor実データ）。
  結果: `reports/EXP_transmute_pilot_20260717.md`。
- **本命の結果**: content_distance（現行`transmute()`ゲートの唯一の指標）と
  form_fidelity（骨格保存という本来の目的の実測）の**Pearson r=0.1791（n=40、ほぼ無相関）**。
  law:106DF0000000065・rfc:768/791/792/793 の5件は現行帯域(0.3–0.85)を通過するのに
  form_fidelity=0.0000（骨格が一片も残らない贋作がゲートを素通りする）。逆に rfc:9110は
  両立（距離帯域内・骨格完全保存）。**sol（DESIGNER_INSIGHTS_20260714）§4.4の「測定器が
  目的と直交している疑い」を実証データで確認**。設計含意: S-2以降の大量取得前に、
  detectorベースの二次基準をゲートまたはログへ追加する設計判断が必要（未実装。次の一手）。
- **副産物のバグ発見・回避**: `--max-chars`既定20000字は漢字密度の高い法令文で
  bge-m3のn_ctx=8192を超過しうる（実測: 19,638字の法令1件→13,122トークンでembeddings
  500エラー）。文字数はCJKテキストのトークン数の安全な代理指標にならない。今回は
  法令側`--max-chars`を8000へ下げて回避（RFC=英語は20000字でも安全と実測確認）。
  2026-07-09に記録済みの既知debt（explore実ラン埋め込み失敗、巨大段落で8192超）と同根。
  恒久修正は`aleph/explore/corpus.py::LlamaServerEmbedder`側のトークン数ベース安全マージン
  （今回のallowlist外のため未修正。次のdebt）。
- **corpus/README.md 更新**（法令+RFCパイロットの取得元・ライセンス根拠・結果要旨を追記。
  corpus/secondary/本体はgit管理外のまま、既存方針どおり）。
- **次の一手**: (1) 測定器の二次基準（S-3のtransmute配線前に必須の設計判断、
  オーナー/設計者への相談事項） (2) S-2本番スケールアップ（法令+RFC各20→本numberへ）は
  上記(1)の判断後 (3) sol の残る問い（深層アーカイブ公開範囲・SHELVE分類・否定的地図の
  実配線）は引き続きオーナーと設計者の合議事項として保留。

## 2026-07-17 続き: transmute()のゲートへ検出器ベースの二次基準を実装（オーナー指示、出先から）
オーナーが外出先（スマホのClaudeアプリ）から直接依頼。ローカルのPROGRESS.md詳細は未読の
状態での指示だったため、実装は司令塔（Claude）が直接行い、GitHub上で追える形にコミットした。

- **重要な制約を発見・回避**: M2受入契約（`tests/test_m2_acceptance.py`、変更不可）の
  既存フィクスチャは `source_biblio={"kind": "law"}` を使うが、そのfake_llmは骨格の
  形式的特徴を一切含まない生成文を返す。新基準を**既定で強制**すると、この保護済み
  テストが壊れる（cos列挙の反復回数不一致で例外）。そのため `min_form_fidelity: float | None`
  を新設し、**既定None=無効（distance帯域のみで判定する従来挙動を完全維持）**、明示的に
  値を渡した場合のみゲートする設計にした。
- **`aleph/materia/transmute.py`**: S-2パイロット（`scripts/exp_transmute_pilot.py`）で
  検証済みのlaw/rfc正規表現detectorを`STRUCTURE_DETECTORS`として正式に移設・一本化。
  `extract_structure_features`/`retained_feature_ratio`/`structural_fidelity`を新設。
  `transmute()`のループに`fidelity_ok`判定を追加し、`min_form_fidelity`指定時は
  distance帯域とform_fidelityの**両方**を満たすまで反復（骨格喪失時の専用フィードバック
  文言も追加）。`provenance["form_fidelity"]`を常時記録（未指定時も計測はする＝観測用）。
- **`scripts/exp_transmute_pilot.py`**: 重複していたdetector実装を削除し
  `aleph.materia.transmute`からimport（単一の真実源に統一、今後regexが分岐しない）。
  `source_biblio`に`"kind": form_type`を追加（transmute()の実ゲートが読むキー名は
  `kind`であり、S-2コーパススキーマの`form_type`とは別名前空間だったため整合）。
  `--max-iters`/`--min-form-fidelity` CLIオプションを追加（既定は今回の測定と同じ
  `max_iters=1`・gating無効のまま、7/17のEXPレポートの再現性を保持）。
- **新規回帰テスト `tests/test_m2_regressions.py`（pytest -m m2、3件）**: (1) 既定では
  M2契約と同じ入力でも従来どおりdistanceのみで通る（form_fidelityは計測されるが
  ゲートしないことを明示） (2) `min_form_fidelity`指定時、骨格特徴を欠く出力は
  （distanceが帯域内でも）再生成され、特徴が揃うまで終わらない (3) 未登録kind
  （detector無し）では`min_form_fidelity`指定時もゲートしない（fail-open。測定不能を
  理由に足踏みさせない設計）。
- **検証**: `uv run pytest -m m2 tests/test_m2_regressions.py` 3 passed（先に(2)を
  `>=3`回で書いて赤→実際のcalls計上を確認して`>=2`に修正→緑、のTDD）。
  `uv run pytest -m m2 tests/test_m2_acceptance.py` 12 passed（無傷）。
  `uv run pytest -m 'not local' -q` → **164 passed**（161+新規3）、退行なし。
- **未実装（意図的・スコープ外）**: この変更は`transmute()`本体への配線のみ。
  実際の呼び出し側（RealDeps.gather_materialsのS-3配線）はまだ存在しないため、
  `min_form_fidelity`を実運用でどの値・どのkindで有効化するかはS-3設計時の判断として残る
  （パイロットの実測データからは閾値0.4前後が失敗例(0.0, 0.2)と成功例(0.5+)を分ける
  境界の候補）。
