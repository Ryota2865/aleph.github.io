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

### 次の一手
- 4回のクロス監査サイクル（audit → fix → re-audit）を経て、指摘は全て解消。
  次はさらにもう一度 `codex-audit` を実行してPASS判定を得るか、PLAN §12の
  正式な合否記録（`audits/M0_audit.md`）をCodex側に依頼するかの判断。
