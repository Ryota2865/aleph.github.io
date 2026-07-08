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

### 未対応（サブエージェントへ委任中）
- **finding 2（harness利用規約適合）**: PLAN §15-1が残置監査項目として明記していた
  論点そのもの。Anthropic/OpenAIの利用規約上、`claude -p`/`codex exec` の自動化バッチ
  実行が許容されるかの一次判定と、必要なら `HarnessProvider`/`build_provider` への
  ガード実装案を、Web調査担当のサブエージェントに依頼中（結果待ち）。結果が出次第
  本ファイルと `audits/M0_audit.md` に反映する。
