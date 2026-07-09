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
