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
