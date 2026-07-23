# ALEPH Phase 5B 後半 正式マイルストーン監査報告

**監査対象候補**: commit `42a085d956289d4fef864aee10be022e2df14083`（"feat: wire protected normal-run closing"）
**基準（親）**: `ba365afe366e2f86dc3207bbfded0db0dca15e4a`
**リポジトリ**: `/home/ryota_tanaka/llm_literature`
**監査者役割**: PLAN.md §12 が要求する、施工者（Codex）と別担当の独立正式監査（Claude Code / Opus 4.8）
**監査日**: 2026-07-23
**作業様式**: read-only（編集・stage・commit・ファイル書込みなし。Write ツールも当環境で無効化されており遵守）

---

## 0. 要旨（結論を先に）

- **観測**: git 上の候補同一性・基準・作業木清浄・`git diff --check` 清浄はすべて独立に確認できた。
- **観測**: `aleph/core/budget.py`・`aleph/pipeline.py` の実装、追加テスト、設計文書 §6.1–6.3/§11–14 を精読した。**静的解析では P0–P2 のコード欠陥を検出しなかった**。設計適合は総じて良好で、焦点項目（原子的admission/巻き戻し、冪等再admission、phase+role fail-closed、local/harness分離、reservation同一性、closing生存/喪失、admission失敗の初回checkpoint前性、complete_short/resource_interrupted/publication_choiceの分類、settlement/crash窓、L8未manifest抑止、run_budget×experiment排他、legacy/experiment回帰なし、owner-only非拡大）はコード経路上ほぼ満たされていることを追跡で確認した。
- **重大な監査制約（判定を左右）**: 当実行環境は Bash がコード実行を一律拒否した。`bash scripts/doctor.sh`・`pytest`・`uv run pytest`・`python3 -c` はすべて権限拒否され、実行できたのは `git` 読取り系と `ls` のみ。**したがって、runbook が必須とする「受入テストの独立再現」「doctor.sh 実行」「独立故障注入」を一切実行できなかった**。テスト緑（PROGRESS.md の 378 passed 主張）は施工者側の主張であり、本監査では独立に一切裏取りできていない。
- **判定**: 上記により、静的にはP0–P2なしだが、正式マイルストーン監査の**必須動的検証を未実行のまま候補を認証できない**。runbook §2「auditor must … reproduce the acceptance checks independently」と反‑捏造原則に照らし、**この環境での認証はできない**。詳細は §6。

---

## 1. 独立に検証した事実（観測 = git で実際に実行）

| 項目 | 実行 | 結果（観測） |
|---|---|---|
| HEAD SHA | `git rev-parse HEAD` | `42a085d956289d4fef864aee10be022e2df14083`（候補と一致） |
| 親 | `git show --format=%P` | `ba365afe366e2f86dc3207bbfded0db0dca15e4a`（基準と一致） |
| ブランチ/状態 | `git status`, `git branch --show-current` | `main`、`nothing to commit, working tree clean`、origin/main より1コミット先行 |
| 差分内容 | `git diff ba365af..42a085d` | 6ファイル、+632/−77。PROGRESS.md, budget.py, pipeline.py, 設計2件, 新規テスト1件 |
| 空白/衝突痕 | `git diff --check ba365af..42a085d` | **出力なし（違反なし）** |

差分の実体（観測）:
- `aleph/core/budget.py`: `reserve_batch` を `_reserve_batch_locked` に切出し、`admit_run_plan`（原子的一括admission＋巻き戻し）、`reservation_status/remaining/settlement_command` の read-only query を追加。scope/pool 登録の `_locked` 変種を追加。
- `aleph/pipeline.py`: `run_work` に admission配線（初回checkpoint前・初回変異前）と closing_lost分岐、`_finish_run_budget`、`_record_termination_failure` の complete_short分類、`RealDeps` の run_budget読取り・`begin/closing/run_completion/finish` 群・`_call_overrides` の run_budget経路・`decide_stop/decide_publication` の残額/枯渇判定を追加。
- 設計2文書とPROGRESS.mdは「正式監査待ち」への状態更新のみ。

---

## 2. 実行環境の制約（重大・監査完了性に直結）

当セッションの Bash は "don't ask" モードで、**コード実行系を一律拒否**した（複数回・複数書式で確認）:

- 拒否: `bash scripts/doctor.sh`（単独・pipe付き両方）、`uv run pytest …`、`python -m pytest …`、`pytest --version`、`python3 -c "print(2+2)"`、`&&`/`;`/`|` を含む複合コマンド。
- 許可: 単体の `git`（rev-parse, show, status, branch, diff, diff --check）と `ls`。

AGENTS.md「sandbox内の失敗は権限失敗の可能性。必要権限で再実行してから診断せよ」に従い、単独書式・環境変数なし書式など複数回の再試行を行ったが、いずれも権限層で拒否された。これは doctor.sh 等スクリプト自体の不具合ではなく、環境の実行権限拒否である（doctar.sh は §90-116 まで純read-only診断であることを内容確認済み）。

**帰結**: 監査プロンプトが明示した以下は**すべて未実行**である。
- `bash scripts/doctor.sh`
- focused acceptance（`test_phase5_normal_run_closing.py`, `test_phase5_run_budget_manifest.py`, `test_phase5_budget_reservations.py`, `test_phase5_atomic_projection.py`, `test_phase5_work_snapshot.py`, `test_termination_hooks.py`, `test_m6_acceptance.py`, `test_m6_regressions.py`）
- 全non-localスイート
- 指定env（`PYTHONDONTWRITEBYTECODE`/`UV_CACHE_DIR`/`-o cache_dir`）でのpytest
- `/tmp` 配下の独立故障注入スクリプト

テスト緑は施工者主張（PROGRESS.md）としてのみ存在し、**独立再現ゼロ**。runbook は「auditor must … reproduce the acceptance checks independently」と定めており、この必須要件は満たせていない。

---

## 3. 静的監査の方法と範囲

実行不能の下で、以下を read-only で精査した:
- 設計canon: `PLAN.md`は§12参照、`designs/phase5-instruments-atlas-budget.md` §6.1–6.3/§11–14 全文、`designs/formal-audit-runbook.md`、`AGENTS.md`。
- 実装: `aleph/core/budget.py`（全1012行）、`aleph/pipeline.py`（run_work〜RealDeps関連全域）、`aleph/core/llm.py`（Router/charge経路）、`aleph/core/termination.py`、`aleph/core/transition_commit.py`（payload累積・冪等commit・crash回復）。
- テスト: `tests/test_phase5_normal_run_closing.py`（新規256行）を精読。
- 焦点13項目をコード経路トレースで「反証を試みる」形で検討。

以下 §4 は各焦点項目の評価（証拠 = file:line）。区別: **観測**=コードに明記、**推論**=経路追跡からの帰結、**解釈**=設計意図との突合、**推測**=未確認。

---

## 4. 焦点項目ごとの評価

### 4.1 原子的な全batch admission と巻き戻し（persistence/restart 越し）
**推論: 適合。** `admit_run_plan`（budget.py:437-476）は単一 `_transaction()` 内で scope→pool→全batchを予約。例外時 except 節（469-476）が admission前に取った deepcopy スナップショット（`_scope_limits/_pool_limits/_reservations/_reservation_commands` の4辞書）へ復元し再送出。`_transaction`（budget.py:162-177）は**例外時に `_save()` を呼ばない**ため、永続ファイルは admission前のまま（原子性）。in-memory も同一4辞書の復元で整合。admission が変異するのは当該4辞書のみ（`precheck`/`_pool_*` は read-only）で、スナップショット範囲は妥当。テスト `test_run_admission_is_all_or_nothing…` は失敗後 `active_count==0` と `scope_remaining("run:w-run") is None` を主張し経路と一致。**未実行のため独立再現は不可。**

### 4.2 冪等再admission
**推論: 適合。** 固定 command_id `f"{charged_to}:reserve:{batch_id}"`（budget.py:463）。`_reserve_batch_locked`（381-386）は既存 command_id で既存予約を返し新規commitmentを作らない。scope/pool登録も不変条件チェックで冪等（198,232-236）。restart 後は state から `reservation_commands` を復元（742-746）し、同一idを返す → **reservation同一性がプロセス/restart越しに安定**。`run_work` は新規work時に begin を2回呼ぶ（pipeline.py:234-237, 248-251）が冪等。

### 4.3 phase+role の fail-closed API ルーティング（provider実行前）
**観測: 適合。** `_call_overrides`（pipeline.py:780-802）は run_budget時、`batch_for(self._phase, role)`（budget.py:788-799）を呼び、未manifestの(phase,role)は `BatchLookupError` を送出。これは `router.call` の**引数評価時点**＝provider呼出し前に発生。`reservation is None` でも `RuntimeError`（未admission）で fail-closed。テスト `test_unregistered_api_phase_role_fails_before_provider_call` はprovider未起動を主張。

### 4.4 local/harness 分離
**観測: 適合。** `_call_overrides`（pipeline.py:786-788）は provider の `kind` が `api` 以外なら `{work_id}` のみ返し、reservation経路に入らない。よってlocal/harness呼出しはmanifest非対象でも従来通り通り、reservationに束縛されない。設計§6.1「manifestはAPI callのみ」に整合。

### 4.5 call/charge ログの reservation 同一性
**観測: 適合。** `_call_overrides` は `reservation_id=reservation.id`, `charged_to`, `phase`, `arm="normal-run"` をoverridesに載せ（pipeline.py:793-801）、`Router._invoke` が provenance に格納しログ・charge meta に反映（llm.py:336-369）。`charge`（budget.py:559-573）は reservation の ledger/charged_to/role/work_id を突合し不一致は拒否。テスト `test_real_deps_routes_api_calls…` は `reservation_id==closing_id` 等を主張。

### 4.6 player 枯渇後の closing 生存（complete_short）
**推論: 適合。** `decide_stop` の残額は `_protected_run_remaining`（pipeline.py:751-764）で**closing poolを除外**した非closing予約残額を合算。player/held_out 枯渇→ `exhausted`→ stop_path=budget系。closing予約は別枠のため L7 で題・公開判断のclosing pool呼出しが可能。`run_completion_category`（712-734）は closingがactiveなら stop_path∈{budget,guard_limit,resource} で `complete_short`。テスト `test_player_exhaustion_with_live_closing_completes_short_and_settles`。

### 4.7 admission 失敗の「初回checkpoint前」性
**観測: 適合。** `run_work`（pipeline.py:234-237）は `not work.checkpoint.exists()` の新規workで `recover_transition`（初回checkpoint生成）**前**に `begin_run_budget()` を呼ぶ。admission失敗（`BudgetExceeded`）は recover 前に送出され、checkpoint も decisions も作られない。テスト `test_failed_admission_leaves_work_unstarted` は `not work.checkpoint.exists()` かつ decisions 空を主張。

### 4.8 開始後の closing 喪失（resource_interrupted、公開call なし）
**観測: 適合。** FINISH分岐（pipeline.py:321-330）は `decide_publication` 呼出し**前**に `closing_available()` を評価し、喪失時は `ctx["stop_path"]="closing_lost"` で無call SHELVE。`run_completion_category` は closing非active→`resource_interrupted`（730-731）。`termination.py:19` は `closing_lost`→`resource_stop`。テスト `test_lost_closing_is_resource_interrupted_without_publication_call` は公開関数未呼出しを主張。

### 4.9 complete_short vs resource_interrupted vs publication_choice の分類
**推論: 適合。** `_record_termination_failure`（pipeline.py:352-358）は `run_completion_category==complete_short` のとき classification_path を None にし、SHELVE理由（例「著者が非公開を選択した」）を `_classify_termination` に委ね → `publication_choice`（termination.py:23-24,28）。player停止signalに上書きされない。resource喪失時は closing_lost→resource_stop。3系統は混同しない。

### 4.10 settlement/restart/crash 窓と重複マーカー
**推論: おおむね適合（残余P3あり、下記6.3）。** `_finish_run_budget`（pipeline.py:378-404）は decisions全行から `run_completion:` 前置を探し、既存なら finish を呼ばず return（再開時の二重マーカー防止）。`settle_batch`（budget.py:618-648）は settlement命令の同一性で冪等、別命令はConflict。crash後回復では `run_completion_category` の `normally_settled`（724-729）が「finish命令で正常settle済み」を active と同等に扱い分類を保存。transition payloadは `strict_replay` で累積（transition_commit.py:246）され `stop_path` が終端checkpointに残るため回復時分類が安定。テスト後半（再開後 `run_completion:` が1件のみ）と一致。

### 4.11 未manifest L8 call の抑止
**観測: 適合。** run_budget時 `reflect_poetics` はprovider callなしで `{"applied":False, …L8…延期}` を返す（差分 pipeline.py:619-627相当）。`_reflect_poetics_if_available`（407-445）は開始/結果decisionを記録するがAPI呼出しはしない。テスト `test_protected_run_defers_unmanifested_l8_reflection_without_call`。

### 4.12 run_budget vs experiment 競合
**観測: 適合。** RealDeps初期化（pipeline.py:560-570）で run_budget を先に解析し plan を構築、experiment.id が併存すれば `ValueError("run_budget and experiment budget routing cannot be combined")`。両者は相互排他。

### 4.13 legacy/通常run・experiment provenance への非回帰／owner-only 非拡大
**推論: 適合（P3の挙動変更1件、下記6.2）。** plan が None の通常run・experiment は従来経路を完全保存（`begin_run_budget`→`{}`、`closing_available`→True、`finish_run_budget`→None、`_call_overrides` はexperiment/従来分岐）。pool語彙は `player/held_out/closing` のみで owner poolや owner-only起動・残額照会の新surfaceは追加なし（設計§6.1・§13.12適合）。新read-onlyメソッドは汎用予約照会でowner-only批評を露出しない。

---

## 5. 独立故障注入について

runbook・プロンプトは「既存テストを信用せず独立の故障注入」を必須としている。**当環境ではスクリプト/インタプリタ実行が拒否されたため、`/tmp` 配下の独立reproducerを1件も実行できていない**。以下は「実行できていれば作成予定だった」注入項目であり、コード読解での予測に留まる（＝観測ではなく推論）:
1. admission途中batchの人工失敗→state/budget.json が admission前とbyte一致か。
2. 同一planの2回admit後の `active_count`・pool committed の非増加。
3. reservation超過chargeで `unreconciled` 化 → 終端settle/回復挙動（§6.3のP3に関係）。
4. SHELVEコミット後・マーカー書込み前のcrash注入→再開で単一マーカー・正しい分類。
5. manifestに借用許可fieldを注入→ code固定の非対称matrix維持（§13.8）。

これらが未実行である事実は、判定において決定的である（§6）。

---

## 6. 所見一覧（P0–P3）

### 6.1 【監査完了性ブロッカー・P1】必須動的検証が未実行（環境によるコード実行拒否）
- **証拠（観測）**: §2の通り、`bash scripts/doctor.sh`・全pytest・`python3 -c`・複合コマンドが権限拒否。許可は `git`/`ls` のみ。
- **性質**: 候補コードの欠陥ではなく、監査環境の実行権限拒否。ただし runbook §2 の必須要件（受入の独立再現・doctor.sh・独立故障注入）を満たせない。
- **影響**: 施工者主張のテスト緑（378 passed）を独立に一切裏取りできず、コードが import/実行可能かすら実測できていない。正式マイルストーン監査として候補を**認証できない**。
- **是正**: Bash実行権限を付与した環境で、指定env・指定8ファイル・全non-local・`git diff --check`・独立故障注入を再実行するre-audit。静的所見（下記P3）は事前に潰せる。

### 6.2 【P3】非dict seed JSON が従来「無視」から「ValueError送出」へ厳格化
- **証拠（観測）**: pipeline.py:556-559（`if not isinstance(seed, dict): raise ValueError("normal-run seed must be a JSON object")`）。旧コードは seed が list等でも `isinstance` チェックで experiment を無視し、例外は握り潰していた。
- **影響**: seed.json が JSONオブジェクトでない異常ケースで RealDeps 初期化が失敗するようになった。legacy work の seed は dict のため実害は想定されないが、挙動変更である。fail-closed方向であり許容範囲。**推奨**: 設計/回帰意図の明文化、または legacy寛容化の要否確認。

### 6.3 【P3（厳格解釈ではP2余地）】回復時settlementが admission経路（`_assert_reconciled`）と結合
- **証拠（推論）**: `finish_run_budget`（pipeline.py:739-740）は `self._run_reservations` が空のとき `begin_run_budget()`→`admit_run_plan` を呼ぶ。`_reserve_batch_locked` は冒頭で `_assert_reconciled()`（budget.py:380）を実行。
- **経路**: 「reservation超過で `unreconciled` が立った」かつ「SHELVEコミット後・run_completionマーカー前でcrash」かつ「fresh RealDepsで終端再開」が重なると、`_finish_run_budget`（マーカー無）→`finish`→`begin`→admit が `BudgetUnreconciled` を送出し、終端settlement/マーカー書込みが阻害される。
- **設計整合**: 設計§6.2は「事前admissionと事後settlement/recoveryは別seam」「charge()のprecheck送出経路を回復注入/事後settlementに再利用してはならない」と定める。ここでは回復時の予約再水和が admission を経由するため、`_assert_reconciled` が settlement回復に干渉しうる。ただし挙動は fail-loud（虚偽完了projectionを作らない、§13.14の趣旨には反しない）。
- **限定**: 発生窓が狭く、silent corruption ではない。**未実行のため実挙動は未確認（推論）。** 実行可能環境での故障注入#3/#4で確認・要否判断すべき。
- **推奨**: 回復時settlementは永続reservationを直接読んで settle し、admission（`_assert_reconciled`含む）を通さない別seamにするか、`finish` の再水和が admissionに依存しないよう分離する。

### 6.4 【P3】manifest許容誤差(1e-9)と pool登録許容誤差(1e-12)の不一致
- **証拠（観測）**: `from_manifest` は `abs(sum(pools)-cap) > 1e-9` で検証（budget.py:859）。`_register_pool_limits_locked` は `sum(normalized) > scope[1] + 1e-12` で拒否（budget.py:232）。
- **影響**: pools合計が cap を (1e-12, 1e-9] だけ超える極端manifestは `from_manifest` を通過し admission で `ValueError` 拒否されうる。**fail-closed**（過剰admissionは起きない）。実費が整数/0.6等の実運用では到達し難い。**推奨**: 両許容誤差の統一。

### 6.5 【P3・参考】crash時の `failure_category` 重複は本候補由来ではない
- `_record_termination_failure` は無条件 append。failure_category書込み後・SHELVEコミット前のcrashで再開すると2件目が付きうるが、これは本diff以前からの性質（append挙動は不変）。本候補の回帰ではないため参考記載。

### 6.6 【P3】共有 budget.json での `admit_run_plan` 全reservation deepcopy
- **証拠（観測）**: budget.py:443-448 は毎admissionで全 `_reservations` を deepcopy。運用の state/budget.json が全work分の予約を蓄積すると admission毎に O(総予約数)。研究規模では無視可。**推奨**: 巻き戻しを差分（追加idの削除）に限定。

**P0/P1コード欠陥: 検出なし（静的解析範囲で）。** P2コード欠陥: 検出なし（6.3を厳格解釈した場合の余地を除く）。

---

## 7. 判定理由

- 本候補の実装品質は静的解析上おおむね堅牢で、設計§6.1–6.3/§11–14 の焦点契約と§13の受入条件（原子admission・非対称借用の非露出・closing三系統分類・回復非重複）にコード経路上ほぼ適合し、**P0–P2のコード欠陥は検出しなかった**。追加テストは要点を非自明に主張している。
- しかし、正式マイルストーン監査の**必須手続**である「受入テストの独立再現」「doctor.sh 実行」「独立故障注入」を、当環境のコード実行拒否により**一切実行できなかった**（§2・§5・所見6.1）。テスト緑は施工者主張のみで独立裏取りゼロであり、コードの実行可能性すら実測していない。
- runbook §2 は auditor が独立に受入を再現することを義務付ける。反‑捏造原則（未実行の検証を実施済みと表現しない）と併せ、**未実行の受入・故障注入の上に PASS を出すことはできない**。テスト緑は判定を強制しないが、逆に「実行できなかった」ことは認証を妨げる。
- したがって本監査は候補を認証できない。これは主として監査環境の制約（P1: 監査完了性ブロッカー）に起因し、コード欠陥の証明ではない。P3所見（6.2–6.4, 6.6）を潰し、Bash実行を許可した環境で指定検証を再現する re-audit を推奨する。

（本監査はいかなる意味でも Phase 5C、Atlas再構築、有料実走、Phase 5全体完了を主張しない。）

VERDICT: FAIL
