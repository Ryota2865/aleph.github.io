# ALEPH Phase 5B 後半 正式マイルストーン再監査報告

**再監査対象候補（修復後・不変同定）**: commit `db8567c78a90459f1cd99ac49bf80074624265bd`（"fix: separate closing recovery from admission"）
**元候補（FAIL 記録の対象）**: `42a085d956289d4fef864aee10be022e2df14083`（"feat: wire protected normal-run closing"）
**基準（親）**: `ba365afe366e2f86dc3207bbfded0db0dca15e4a`
**リポジトリ**: `/home/ryota_tanaka/llm_literature`
**役割**: PLAN.md §12 が要求する、施工者（Codex）と別担当の独立正式監査（Claude Code / Opus 4.8）による、失敗スコープの read-only 再監査
**再監査日**: 2026-07-23
**作業様式**: read-only（リポジトリ/work/state/report の編集・stage・commit・書込みなし。`/tmp` のみをキャッシュと独立故障注入に使用。provider 呼出し・Atlas 再構築なし）
**先行監査記録**: `reports/PHASE5B_NORMAL_RUN_CLOSING_AUDIT_20260723_FAIL.md`（元候補 42a085d に対する FAIL。runbook §3 に従い候補差分内に保全されており、本再監査ではこれを prior-audit record として扱い、独立に再検証した）

---

## 0. 要旨（結論を先に）

- 本再監査は、先行 FAIL の**主要ブロッカー（所見6.1＝必須動的検証が環境により未実行）を完全に解消**した。当環境では Bash が実行可能であり、`doctor.sh`・焦点8テスト・全 non-local スイート・README スナップショット整合・`git diff --check`・**独立 /tmp 故障注入**をすべて実際に実行した。
- **git 同定**: HEAD=`db8567c…`（修復候補）、親=`42a085d…`（元候補）、その親=`ba365af…`（基準）。作業木清浄、`git diff --check` 清浄をいずれも独立に確認。
- **動的検証（すべて実行・観測）**: doctor.sh 0 failures／焦点8ファイル 47 passed／全 non-local 379 passed（local 1件のみ deselected）／README スナップショット 2 passed／独立故障注入 19/19＋許容誤差境界 1/1。
- **先行 FAIL の核心所見6.3（回復時 settlement が admission 経路と結合）は解消**。修復は `Budget.load_run_plan_reservations`（admission/reconciliation ゲート非経由の再水和）を新設し、`RealDeps.finish_run_budget` の回復経路をこれに切替えた。設計 §6.2「事前admissionと事後settlement/recoveryは別seam」に正確に対応する。独立故障注入で**反証（＝欠陥の再現）を試み、再現しないこと**を確認した。
- **先行 P3 の再評価**: 6.3 解消（P2余地も消滅）、6.4（許容誤差不一致）解消、6.2/6.5/6.6 は非ブロッキングの残存リスクとして存続（うち6.5は本候補由来でない既存性質）。
- **新規 P0–P2 なし**。新規 P3 なし。
- **判定**: 静的・動的双方で焦点契約への適合を確認し、ブロッキング所見は残存しない。**VERDICT: PASS**（残存 P3 を明示保持）。

---

## 1. 独立に検証した事実（観測＝実際に実行）

| 項目 | 実行コマンド | 結果（観測） |
|---|---|---|
| HEAD SHA | `git rev-parse HEAD` | `db8567c78a90459f1cd99ac49bf80074624265bd`（修復候補と一致） |
| 修復候補の親 | `git show --format=%P db8567c` | `42a085d…`（元候補） |
| 元候補の親 | `git show --format=%P 42a085d` | `ba365af…`（基準と一致） |
| 状態 | `git status --porcelain` | 出力なし（作業木清浄） |
| 空白/衝突痕 | `git diff --check ba365af..HEAD` | **出力なし・exit 0（違反なし）** |
| 差分規模 | `git diff --stat ba365af..HEAD` | 9ファイル +890/−80（budget.py, pipeline.py, テスト, README×2, PROGRESS, 設計2, 保全FAIL） |
| doctor | `bash scripts/doctor.sh` | `SUMMARY failures=0 warnings=0`（exit 0） |

FAIL 証拠の保全（runbook §3）: `reports/PHASE5B_NORMAL_RUN_CLOSING_AUDIT_20260723_FAIL.md` が差分に新規追加として含まれ、見出しから `VERDICT: FAIL` まで無改変で保存されていることを確認した。

---

## 2. 実行した動的検証（先行 FAIL 6.1 の解消）

すべて `PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/aleph-claude-reaudit-uv-cache`、pytest は `-o cache_dir=/tmp/aleph-claude-reaudit-pytest-cache`、`TMPDIR=/tmp` で実行。

- **doctor.sh**: `failures=0 warnings=0 network=0`。WSL/git/uv/GPU/port すべて PASS。
- **焦点8ファイル**（`test_phase5_normal_run_closing`, `test_phase5_run_budget_manifest`, `test_phase5_budget_reservations`, `test_phase5_atomic_projection`, `test_phase5_work_snapshot`, `test_termination_hooks`, `test_m6_acceptance`, `test_m6_regressions`）: **47 passed, 34 deselected**（exit 0）。
- **全 non-local**（`-m "not local and not network"`）: **379 passed, 1 deselected**（exit 0）。deselected の1件は `tests/test_m0_acceptance.py::test_local_swap`（local マーカー）で、正当に除外。本呼出しは既定 addopts の m0–m6 除外を上書きするため、m0–m6 受入も含めた完全 non-local を実走している。
- **README スナップショット整合**: 2 passed（`RepositorySnapshot` 由来マーカーが README.md / README.en.md と一致）。
- 補足: 初回焦点実行時に pytest の global-capture teardown で `FileNotFoundError`（tmpfile truncate）が一度発生したが、これはテスト teardown の TMPDIR 起因の一過性で、`TMPDIR=/tmp` 明示で解消し、以後 exit 0 で安定再現。候補コードの不具合ではない。

先行 FAIL は「環境がコード実行を一律拒否したため必須動的検証ゼロ」を唯一のブロッカー（P1）としていた。本再監査ではこれを**すべて実行済みに転換**した。

---

## 3. 修復差分の精査（db8567c − 42a085d）

修復は最小・外科的で、変更は2箇所のみ:

1. **`aleph/core/budget.py`**
   - `load_run_plan_reservations(plan)` を新設（budget.py:479–498）。永続 `_reservation_commands`/`_reservations` を直接読み、`command_id` 欠落→`ValueError("run batch was not admitted")`、manifest hash 不一致→`ReservationConflict`。**`_assert_reconciled`・`precheck`・admission を一切呼ばない**（read-only 再水和）。
   - 許容誤差の統一: `_AMOUNT_EPSILON = 1e-9` を定義（budget.py:30）。`_register_pool_limits_locked` の pool 超過判定を旧 `1e-12`→`_AMOUNT_EPSILON`（budget.py:233）、`RunBudgetPlan.from_manifest` の cap 整合判定を `_AMOUNT_EPSILON`（budget.py:881）。
2. **`aleph/pipeline.py`**
   - `RealDeps.finish_run_budget` の回復分岐を、旧 `self.begin_run_budget()`（→`admit_run_plan`→`_assert_reconciled`）から `self.router.budget.load_run_plan_reservations(self._run_budget_plan)` に切替（pipeline.py:737–744）。コメントで「Terminal recovery must not pass through admission」を明記。

この変更は設計 §6.2（budget.py 契約）「事前admissionと事後settlement/recoveryは別seamにする…現行`charge()`の`precheck()`送出経路を、回復注入と実行後settlementに再利用してはならない」に対する**構造的に正しい対応**である。回復経路が admission ゲート（`_assert_reconciled`）から分離された。

---

## 4. 先行所見6.3 の再現/反証（独立故障注入）

先行 FAIL 6.3 が P2 余地ありとした経路を、`/tmp` 独立スクリプト（`/tmp/aleph_inject.py`、既存テストに依存しない自作 fixture）で反証した。fresh `Budget`/`Router`/`RealDeps` を用い、以下19項目すべて PASS（観測）:

**A. 非closing（player）完了超過→unreconciled→fresh 回復**
- A1: player 予約超過 charge が `billing_status=="unreconciled"`、大域 unreconciled フラグ立つ。
- A2: **回復（`finish_run_budget`）は例外を出さない**（＝admission 非経由の別seam）。旧経路なら `BudgetUnreconciled` で阻害されていた。
- A3: 分類は **`complete_short`（closing 生存を正直に反映）**。
- A4: **unreconciled 証拠は保存**され、`admit_run_plan` は依然 `BudgetUnreconciled('… player-overage')` を送出。
- A5: 超過した player 予約は `unreconciled` のまま（settle されず証拠保存）。
- A6/A6b: 他の active 予約（closing, held_out）は冪等に `settled`。

**B. closing 完了超過→resource_interrupted**（リポジトリテストと独立に再現）
- B1: closing 喪失→`resource_interrupted`（正直な分類）。

**C. 再水和の拒否**
- C1: 未 admit の予約→`ValueError("run batch was not admitted: player-author")`。
- C2: manifest hash 改竄→`ReservationConflict("admitted run batch identity mismatch: closing-author")`。

**D. 原子的 admission 巻き戻しの永続整合**
- D1: 途中 batch で `BudgetExceeded`。D2: **`budget.json` が巻き戻し後 byte 完全一致**。D3: `active_count` 不変。D4: `scope_remaining("run:w-run") is None`。D5: `reservation_commands` に予約リーク無し。

**E. 冪等再 admission**
- E1: 2回 admit で `active_count` 3 のまま不増加。E2: 予約 id が同一。

**F. 終端 marker のクラッシュ窓冪等性**
- F1: `_finish_run_budget` を同一 decisions ログ上で2回呼んでも `run_completion:` マーカーは **1件のみ**（重複マーカー無し）。

**許容誤差整合（6.4 検証）**: pool 合計が cap を 5e-10（1e-9 以内）超える manifest が、`from_manifest` と `admit_run_plan` の双方で一貫して受理される（旧 1e-12 登録なら admission で `ValueError` 拒否され得た不整合が解消）。

**結論**: 先行6.3 の欠陥は**再現しない**。回復は admission を経ず、正直に分類し、他 active 予約を冪等 settle し、unreconciled 証拠を保存し、欠落/不一致再水和を拒否し、虚偽の完了 projection を作らない（設計 §13.14 適合）。

---

## 5. 焦点契約の追跡評価（コード経路＋テスト＋注入）

区別: **観測**＝コード/実行に明記、**推論**＝経路追跡からの帰結。

- **原子 admission/巻き戻し（persistence 越し）**: 観測。`admit_run_plan`（budget.py:437–）は単一 `_transaction` 内で4辞書 deepcopy スナップショット、例外時に復元し再送出。`_transaction` は例外時 `_save()` を呼ばず永続不変。注入 D で byte 一致を実測。
- **回復は admission と別seam**: 観測（§3・§4）。修復の核心。注入 A2/A4 で実証。
- **rehydration 拒否（欠落/manifest不一致）**: 観測。注入 C1/C2。
- **冪等再 admission／予約同一性**: 観測。注入 E。restart 越しの id 安定は `_reservation_commands` 復元（budget.py:_load）に依拠。
- **phase+role fail-closed（provider 実行前）**: 観測。`_call_overrides`（pipeline.py:784–）は run_budget 時 `batch_for(phase, role)` を `router.call` 引数評価時点で呼び、未 manifest は `BatchLookupError`。テスト `test_unregistered_api_phase_role_fails_before_provider_call` が provider 未起動を主張し 47 passed に含む。
- **local/harness 分離**: 観測。`_call_overrides` は provider kind≠api で `{work_id}` のみ返し reservation 経路に入らない（pipeline.py:786–789）。
- **call/charge の reservation 同一性**: 観測。overrides に `reservation_id/charged_to/phase/arm="normal-run"` を載せ、`charge()`（budget.py:585–594）が ledger/charged_to/role/work_id を突合し不一致拒否。
- **player 枯渇後の closing 生存 complete_short**: 観測。`_protected_run_remaining` が closing pool を除外して残額合算（pipeline.py）、`run_completion_category` が closing active＋stop_path∈{budget,guard_limit,resource}→`complete_short`。テスト `test_player_exhaustion_with_live_closing_completes_short_and_settles`。
- **開始後の closing 喪失（resource_interrupted・公開call無）**: 観測。FINISH 分岐が `decide_publication` 前に `closing_available()` を評価、喪失で無call SHELVE＋`stop_path="closing_lost"`。`termination.py` が `closing_lost`→`resource_stop`。テスト `test_lost_closing_is_resource_interrupted_without_publication_call`＋注入 B1。
- **complete_short / resource_interrupted / publication_choice の非混同**: 観測。`_record_termination_failure` は `complete_short` 時 classification_path=None とし、SHELVE 理由（例「著者が非公開を選択」）を `publication_choice` に委ね、player 停止 signal に上書きされない。テスト `failure_category:publication_choice` を主張。
- **admission 失敗の初回checkpoint前性**: 観測。`run_work` は新規work（checkpoint 不在）で `recover_transition` 前に `begin_run_budget()` を呼ぶ。テスト `test_failed_admission_leaves_work_unstarted`（checkpoint 不在・decisions 空）を実走確認。
- **L8 未 manifest 抑止**: 観測。run_budget 時 `reflect_poetics` は provider call なしで `applied:False`＋L8延期理由。テスト `test_protected_run_defers_unmanifested_l8_reflection_without_call`。
- **run_budget × experiment 排他**: 観測。RealDeps 初期化で両立時 `ValueError("run_budget and experiment budget routing cannot be combined")`。
- **legacy/通常run・experiment 非回帰／owner-only 非拡大**: 推論＋観測。plan=None 経路は従来完全保存。pool 語彙は `player/held_out/closing` のみで owner pool・owner-only 起動/残額照会の新 surface は追加なし。全 non-local 379 passed が回帰なしを裏付け。

---

## 6. 所見一覧（P0–P3）と先行 P3 の再評価

### 解消
- **6.1【先行P1・ブロッカー】必須動的検証未実行** → **解消**。本再監査で doctor.sh・焦点8・全 non-local・README 整合・`git diff --check`・独立故障注入をすべて実走（§2・§4）。
- **6.3【先行P3（厳格解釈でP2余地）】回復時 settlement が admission（`_assert_reconciled`）と結合** → **解消**。`load_run_plan_reservations` 新設で別seam化（§3・§4）。P2 余地も消滅。
- **6.4【先行P3】許容誤差 1e-9 と 1e-12 の不一致** → **解消**。両 cap 整合判定を `_AMOUNT_EPSILON=1e-9` に統一（budget.py:233,881）。pool 溢れ検査（budget.py:1016）も 1e-9 で整合。境界注入で確認。

### 残存（非ブロッキング P3・残存リスクとして明示保持）
- **6.2【P3】非dict seed JSON→`ValueError`（fail-closed 厳格化）**。証拠: pipeline.py:558（`raise ValueError("normal-run seed must be a JSON object")`）。legacy work の seed は dict のため実害想定なく、全 non-local 379 passed で回帰なし。fail-closed 方向で許容。要否は設計明文化で整理可。
- **6.5【P3・本候補由来でない】`_record_termination_failure` は無条件 append**。failure_category 書込み後・SHELVE checkpoint commit 前の crash で再開すると FINISH 分岐が再実行され failure_category が二重付与され得る（append-log-before-checkpoint の既存性質）。本候補は分類計算のみ変更し append 意味を変えていないため**回帰ではない**。なお本候補が追加した `run_completion:` マーカーは dedup ガード（pipeline.py `_finish_run_budget`）で単一化されており、注入 F1 で確認済み。
- **6.6【P3】`admit_run_plan` が毎回全 `_reservations` を deepcopy**（budget.py:443–448）。研究規模では無視可の性能事項。巻き戻しを差分限定にする最適化余地。

### 新規所見
- **新規 P0–P2: なし**。**新規 P3: なし**。修復の2変更はいずれも先行所見の是正であり、静的追跡・19+1件の独立注入・379/47 テストで新たな欠陥を検出しなかった。
- 参考（欠陥ではない設計挙動）: run_budget work が状態破損（budget.json 消失等）で終端再開した場合、`load_run_plan_reservations` は `ValueError("… not admitted")` を fail-loud に送出し、虚偽完了を捏造しない。これは §11/§13.14 の趣旨に沿う正しい fail-closed であり所見としない。

---

## 7. 判定理由

- 先行 FAIL の**唯一のブロッカー（6.1: 環境によるコード実行拒否で必須動的検証ゼロ）**は、本再監査環境で `doctor.sh`（0 failures）・焦点8（47 passed）・全 non-local（379 passed）・README 整合（2 passed）・`git diff --check`（清浄）を**実走**することで解消した。
- 先行の唯一の P2 余地（6.3）は、`load_run_plan_reservations` による admission/回復の別seam化で是正され、独立 /tmp 故障注入19項目＋許容誤差境界で**欠陥の再現を試みて再現しないこと**を実証した。回復は admission 非経由・正直分類・冪等 settle・unreconciled 証拠保存・欠落/不一致拒否・単一マーカーを満たす。
- 6.4 は許容誤差統一で解消。残存 P3（6.2, 6.5, 6.6）はいずれも fail-closed または既存性質・性能事項であり、silent corruption や虚偽完了 projection を生まず、マイルストーンを黙って拡大しない。runbook §3 が許す「明示 P3 を残存リスクとして保持した PASS」に該当する。
- テスト緑は正式判定とは別証拠だが、本再監査ではそれを独立に再現し、加えて既存テストに依存しない独立故障注入で焦点契約を確認した。ブロッキング所見（P0–P2）は残存しない。

したがって修復候補 `db8567c78a90459f1cd99ac49bf80074624265bd` を認証する。

本監査はいかなる意味でも Phase 5C、Atlas 再構築、新規有料実走、Phase 5 全体完了を主張しない。作業様式は全編 read-only で、リポジトリ/work/state/report への書込みは行っていない（`/tmp` のみ使用）。作業木は清浄。

VERDICT: PASS
