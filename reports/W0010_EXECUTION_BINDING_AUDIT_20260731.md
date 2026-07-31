監査を完了しました。VERDICT: PASSです。read-onlyで実施し、故障注入は`/tmp`のlinked worktree内のみ、有償provider pathは未実行です。以下が結果です。

---

# w0010「アーカイブ認識論の出口封鎖」execution binding 独立正式監査

## 監査対象と方法

- **Candidate**: branch `codex/w0010-archive-exit-preregistration` → commit `2cdddcbe` / tree `9d3682d8`(監査開始・終了ともに不変を実測)
- **Parent = 凍結prereg**: `aaade529`(tag `preregistration/w0010-archive-epistemology-exit-closure-20260731`、lightweight tag→同commit)
- **手法**: 本checkoutは別branch `codex/phase6-r9`(HEAD `3e04808`)のまま一切触れず、`/tmp/w0010-cand`(候補)と`/tmp/w0010-base`(base)に隔離linked worktreeを作成。各worktreeは独自`.venv`でeditable `aleph`を候補/baseパスに固定(`import aleph` の解決先を実測確認済み)。監査後にworktreeは撤去、本checkoutは無変更。

---

## tests-green(施工シグナル ─ formal verdictとは分離)

独立再測定結果:

| 項目 | 実測 | 施工申告 | 判定 |
|---|---|---|---|
| focused(新規2ファイル) | **18 passed** | (PROGRESS: 18) | 一致 |
| full non-local (`-m "not local"`) | **456 passed, 1 skipped, 1 deselected** (6.89s) | 456/1/1 | 一致 |
| compileall (`aleph tests scripts`) | **PASS** (exit 0) | PASS | 一致 |
| base RED再現 | **ValueError再現** | ─ | 一致 |

- **1 skipped の実測理由** = `tests/test_design_invariants.py:144: no secrets in .env`。これは一時worktreeに`.env`が存在しないための**環境差skip**であり、linked worktree固有の欠陥でも候補欠陥でもない(secretsを持たない環境では常にskip)。
- **1 deselected** = `local` marker(RTX 3090要)。
- なお既定`addopts`はm0–m6/localをdeselectするため、素の`pytest`では215 passed/242 deselectedとなる。「full non-local 456」は`-m "not local"`(受入基準m0–m6を含む)を指すことを確認。
- 注:施工申告の「focused: 50 passed」は再現できず(新規2ファイルは18)。より広いfocused部分集合の呼称と思われ、権威ある full 456 が一致するため非blocking(P3-a)。

*正式監査前のgreenは施工シグナルであり実行許可ではない。*

---

## Observed evidence / Inference / Uncertainty

### Observed evidence(一次事実)

1. Candidate diff は parent `aaade52` に対し **11ファイル / +419−10** のみ。変更集合: `PLAN.md`, `PLAN_CHANGELOG.md`, `PROGRESS.md`, `README.md`, `README.en.md`, `aleph/pipeline.py`, `designs/next-designer-execution-plan.md`, `designs/w0010-archive-epistemology-execution-binding.md`, `designs/w0010-run-budget-v2.json`, `tests/test_phase5_normal_run_closing.py`, `tests/test_w0010_execution_binding.py`。**`works/`・`config/`・`poetics`・provider stateは皆無。**
2. 凍結manifest `designs/w0010-archive-epistemology-exit-closure-preregistration.json` のSHA-256は base・candidate 双方で `340c5756…b070`(**diffに不在=bytes不変**)。`run_budget-v2.json`全batchの`input_manifest_hash`が同SHAへ束縛。`works/w0010`不在。
3. `aleph/pipeline.py:613-631`: 旧`raise ValueError("run_budget and experiment budget routing cannot be combined")`を削除し、experiment scope登録を `self._run_budget_plan is None and …` でガード。`_experiment_id`/`_experiment_arm` は provenance として保持。
4. `aleph/pipeline.py:1030` 前後(run_budget予約経路): call record に `experiment_id`, `arm = _experiment_arm if _experiment_id else "normal-run"`, `charged_to = run_budget_plan.charged_to`, `reservation_id` を同時記録。
5. base worktree で候補testを実行 → `pipeline.py:617` で `ValueError: run_budget and experiment budget routing cannot be combined`(**provider callより前=RED再現**)。同testは候補でgreen。
6. `tests/test_phase5_normal_run_closing.py` の新規test: `experiment_id == id`, `arm == "main"`, `charged_to == "run:w-run"`, `reservation_id == closing予約.id`, `scope_remaining("experiment:…") is None`, `scope_remaining("run:w-run") is not None` を assert しgreen。
7. `charged_to = f"run:{work_id}"`(budget.py:1074)。
8. **axis導出の実測**(`/tmp`故障注入): 実manifest→`closing_reserve=2.8608`、per-slot `title 0.8224 / publication-intent 1.1392 / shelf-comparison 0.8992 / final-projection 0.0`。axisレート改変→**REJECT**(derived≠declared batch)、declared pool改竄→**REJECT**(pool overflow)。`ClosingSlot.max_amount = fsum(unit_ceiling×usd_per_unit)`(budget.py:157)、external slotは`max_amount`フィールド自体を許容しない(fieldset厳格一致)。
9. 算術: `72000×1e-5+2048×5e-5=0.8224`, `32000×1e-5+16384×5e-5=1.1392`, `8000×1e-5+16384×5e-5=0.8992`, 合計 `2.8608`。pools `3.5+2.6392+2.8608=9.0`(=`cap_amount`)、held_out `1.8+0.8392=2.6392`。
10. snapshot audit(候補で実行): `head_tree=9d3682d8`, `state=HEAD`, 最新記録formal audit=**PASS**(w0009 `d4bc98b`), `currency=NEEDS_AUDIT`。w0010ファイル群は`unexpected_paths`=前回監査以降の新規作業として現れ、これがNEEDS_AUDITの根拠。README `0.7.20-41 / NEEDS_AUDIT` と整合。
11. `config/budgets.yaml` はdiff不在(unchanged)。現行 `usd_per_month: 71.0`(7月)、`usd_per_work: 9.0`。設計§5は`$45`を2026-08-01反映の**前提gate**と明記。
12. `tests/` に旧raiseを期待する孤児testなし(本checkoutの`pipeline.py:617`hitはphase6別branchのコードで候補とは無関係)。
13. 既存experiment-only経路のtest(`test_phase3_experiment_evaluation`, `test_w0008/w0009_runner`, `budget_cap_usd`系)は456green内で通過。
14. `decide_stop`/`decide_publication`(pipeline.py:1367-,1400-)は`_protected_run_remaining()`を優先し、run_budget時はexperiment ledgerを予算権威に用いない。

### Inference(合理的推論)

- **Check #7**: L7 closing被覆は「予算包絡」として構造的に完全 ─ manifest `closing_slots`が題名/公開意図/棚比較/最終射影の4 slot、`from_manifest`が「closing batchの`expected_slots` ≡ closing slot id集合」を厳格強制(`seen != expected`でraise)、testが確認。実行時の provider call と slot の1:1対応は、gate通過後の有償ランで admission/charge時に検証される性質(現段階では包絡として健全)。
- **Check #8**: `$2.8608`は宣言値ではなく axis から導出され、宣言 pool/batch値は導出値に対し二重照合されるため、宣言側の齟齬は必ずrejectされる。「never trust a caller-supplied USD total」の設計意図が実効。
- **Check #10/#11**: player `$3.5`/held-out `$2.6392`は設計§4・changelog項3で「実行上限であり支出目標・全生成slot購入保証ではない」と明示、closingとの差異も言明。詩学v1・frontier Author・固定実験介入・house-style provisional維持はchangelog項4に記載され、対応ファイルに変更なし。

### Uncertainty(不確実性)

- L7実slot↔manifest slotの1:1対応、および各slotのtoken ceiling妥当性は**有償ラン時にのみ実証**される(設計も§5で読後best-effort照合と明記)。本監査は事前binding段階の整合性までを対象とし、これは想定内。
- `$45`月次capは未反映(2026-08-01 gate)。`$2.8608 < $9 < $45`は自明に成立するが、$45の実適用は本監査の管轄外の前提action。

---

## P0–P3 Findings

- **P0(実行阻却)**: なし
- **P1(重大)**: なし
- **P2(要修正)**: なし
- **P3(助言・非blocking)**:
  - **P3-a**: 施工申告「focused: 50 passed」を再現できず(新規2ファイルは18、PROGRESS.mdも「18件」)。権威あるfull 456が一致するため実害なし。focusedの集合定義/件数ラベルの統一を推奨。
  - **P3-b**: `config/budgets.yaml`のコメント「月上限44が最終防壁」は現行`$71`および設計の`$45`と不整合だが、**本候補が導入したものではなく**(budgets.yamlは意図的に無変更)、既存の陳腐化コメント。次回のbudget調整時に整理を推奨。

いずれも execution binding の正当性・実行安全性に影響しない。

---

## 14項目チェック結果

| # | 項目 | 判定 |
|---|---|---|
| 1 | candidate identity 監査中不変 | ✓ `2cdddcbe`/`9d3682d8` 始終一致 |
| 2 | manifest固定(結果/works/call前)・候補でbytes不変 | ✓ SHA `340c57…` base=candidate、parent=凍結tag、works/w0010不在 |
| 3 | base で experiment+run_budget v2 が RealDeps初期化で拒否(RED再現) | ✓ `pipeline.py:617` ValueError |
| 4 | 候補で run_budget v2 が唯一権威・experiment:*重複登録なし | ✓ `_run_budget_plan is None`ガード、scope None実測 |
| 5 | call record に experiment_id/arm=main/charged_to=run:*/reservation_id 同時 | ✓ test green(`run:w-run`) |
| 6 | experiment-only / protected-run-only 経路に回帰なし | ✓ 456green、孤児testなし |
| 7 | L7 closing が title/publication intent/shelf comparison/final projection を完全被覆 | ✓(構造的包絡、runtime対応はgate後) |
| 8 | `2.8608` が axis から導出・batch/poolと一致 | ✓ 導出実測+故障注入でreject確認 |
| 9 | `$2.8608` が作品cap `$9`・8月hard cap `$45`の内数 | ✓ 2.8608<9<45、pools=9.0 |
| 10 | player/held-out を購入保証/支出目標に偽装せず | ✓ 設計§4・changelog項3で明示 |
| 11 | frontier Author/詩学v1/固定実験介入/house-style provisional 維持 | ✓ changelog項4、該当ファイル無変更 |
| 12 | works/w0010・作品・provider state・budgets.yaml・poetics 無変更 | ✓ diff 11ファイルに一切不在 |
| 13 | README `0.7.20-41`/`NEEDS_AUDIT` が正直 | ✓ snapshot audit で PASS(w0009)/NEEDS_AUDIT/HEAD/tree一致 |
| 14 | 汎用DSL/AIDE²/corpus拡張/隠れ層探索の混入なし | ✓ pipeline seam+境界付き検証済JSON+test+docsに限定 |

---

## 総括

Candidate `2cdddcbe` は、凍結済み結果blind preregistration(`aaade52`/`340c57…`)へ execution binding を単一commitで束縛する最小seamである。予算権威は `run:*` に一本化され experiment identity は provenance として併記、closing reserve `$2.8608` は axis から導出され宣言値に対し二重照合で守られ、既存 experiment-only / protected-run-only 経路は回帰なし。有償ラン・`works/w0010`・作品・config・poetics・provider state はいずれも未変更で、READMEの `NEEDS_AUDIT` 表示も正直。RED(base)→GREEN(候補)を独立fixtureで再現。P0–P2 findingなし、P3は2件とも非blocking。

VERDICT: PASS
