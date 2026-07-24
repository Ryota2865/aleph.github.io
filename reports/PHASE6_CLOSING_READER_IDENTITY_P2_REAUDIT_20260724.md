# ALEPH Phase 6 P2 focused 再監査

初回FAILを発行した同一のClaude Code監査担当として、修繕候補をread-onlyで再監査した。

## 1. 候補identityとread-only確認

| 項目 | 監査時実測 | 供給値 | 一致 |
|---|---|---|---|
| `git rev-parse HEAD` | `216a9b5c1d65b31b48d593fffbf374f961b0b69c` | 同 | ✓ |
| `git write-tree`（開始時／終了時） | `b93a518c7cd27720456358d63b4a4026b1980b33`（両測定で不変） | 同 | ✓ |
| unstaged/untracked | 0件（`--untracked-files=all`） | なし | ✓ |
| `git diff --check` | pass | pass | ✓ |
| 初回FAIL artifact | `reports/PHASE6_CLOSING_READER_IDENTITY_AUDIT_20260724_FAIL.md` に**逐語保存**（冒頭から `VERDICT: FAIL` の最終行まで、P3-1〜P3-8を含め改変なし） | — | ✓ |

read-only遵守: リポジトリの編集・staging・commit・レポート書込みを行っていない。注入testは `/tmp/aleph_reaudit_probe.py`、pre-repair比較は `git archive` で `/tmp/aleph-reaudit-red/pre` へ展開したコピー上のみ。network・有償API・推論・server起動なし。

## 2. focused diffとコマンド結果

tree間差分は11ファイル・+324/-8。実装変更は `aleph/core/budget.py`（+34/-3）と `aleph/pipeline.py`（1行）のみで、**tokenizer scopeは4ファイルとも byte-identical**（`git diff --stat` が空）。残りはtest 2件、初回FAIL artifact、PLAN_CHANGELOG 0.7.20-25、PROGRESS、設計状態、README derived marker。

```
bash scripts/doctor.sh                    → failures=0 warnings=1 (worktree has local changes)
pytest -q <focused 7 files>               → 69 passed
pytest -q -m 'not local'                  → 410 passed, 1 deselected
python -m compileall -q aleph scripts/... → OK
git diff --check                          → clean
```

**observable REDの独立検証（施工者報告の追認）** — 元tree `14772732…` を `/tmp` へ展開し、修繕treeの回帰testだけを重ねて実行した（`import aleph` が展開側を指すことを `aleph.__file__` と `RunBudgetPlan` に `manifest_hash` が無いことで確認済み）:

```
5 failed, 9 deselected
  test_checkpoint_cannot_bypass_v2_gate[{}]                        FAILED
  test_checkpoint_cannot_bypass_v2_gate[not json at all]           FAILED
  test_repricing_same_closing_amount_conflicts_with_admitted_identity  FAILED
  test_v1_plan_cannot_rehydrate_v2_admission                       FAILED
  test_budget_admission_rejects_v1_even_without_pipeline           FAILED
```

4つの監査由来経路＋防御深化1件がすべて修繕前コードで真に失敗する。回帰testは症状に後付けされたものではない。

README derived markerも独立に再計算した。`RepositoryReader.snapshot()` の実測は `formal_audits count: 24`、日本語markerは staged README と完全一致、初回artifactは `PHASE6_…_FAIL.md -> FAIL` と正しく分類される。定義（`audits/*.md` 3件 + `reports/*AUDIT*.md` 21件）どおりの機械的更新であり、`test_repository_snapshot.py` もgreen。

## 3. P2-1 の閉鎖評価 — **閉鎖**

`aleph/pipeline.py:608` は `version < 2 and not work.checkpoint.exists()` から `version != 2` へ変わり、checkpointを一切参照しない。`aleph/core/budget.py:499-503` に `Budget.admit_run_plan` 側の独立gateが追加された。

独立注入（`/tmp/aleph_reaudit_probe.py`）:

| 経路 | 結果 |
|---|---|
| R1: checkpoint = 不在 / `""` / `{}` / `not json at all` / `[]` / `{"state":"PUBLISH","step":99}` / `{"state":"INTENT","step":1,"payload":{}}` | **7形すべて拒否** |
| R2: 初回admission後に `recover()` が実体化した**本物の**checkpoint + seedのv1差し替え（初回FAILのC1そのもの） | **拒否** |
| R3: `RealDeps` を通さない `Budget.admit_run_plan(v1 plan)` | **拒否** |
| R4: v1の履歴解釈用parse | 維持（`closing_reserve=None`、`phase5-run-budget-v1`）|

checkpoint述語への依存が消えたため、初回FAILで指摘した「偽造でも正常運用でも到達する抜け道」はいずれの経路からも再現しない。`PLAN_CHANGELOG` 0.7.20-24 の「legacy互換を新規runの抜け道にしない」という主張が実装と一致した。

**契約変更の確認:** 設計§2は「v1は開始済みrunの回復互換」から「v1は履歴解釈用にparseできるが、checkpointの有無・内容にかかわらずadmissionには使用できない」へ改訂され、PLAN §12が要求するとおり `PLAN_CHANGELOG` 0.7.20-25 に理由付きで記録されている。実害の有無を独立に確認したところ、`works/w0001`〜`w0009` の9作すべてが `run_budget` を**持たない**。したがってこの緊縮によって再開不能になる既存protected runは存在しない。契約を緩めず、既存資産を破壊しない範囲の修繕である。

## 4. P2-2 の閉鎖評価 — **閉鎖**

`RunBudgetPlan.manifest_hash = _canonical_hash(data)`（`budget.py:1114`）が**生manifest全体**（`version` と `closing_slots` を含む）をhashし、`dataclasses.replace` で全 `BatchSpec` へ `run_manifest_hash` と実体のある `protected_definition_version`（`phase6-run-budget-v2` / `phase5-run-budget-v1`）を束縛する。両fieldは `BatchSpec.canonical()`（`budget.py:90,107`）に入るため、予約作成・冪等再admission・restart再水和の三経路が同一のmanifest hash比較を通る。

同額のまま各要素だけを変えた独立注入（R5、すべて `closing_reserve` は 0.6 で不変）:

| 変更 | 再admission | 再水和 |
|---|---|---|
| provider のみ | `ReservationConflict: different manifest` | `ReservationConflict: identity mismatch` |
| model のみ | 同 | 同 |
| pricing_version のみ | 同 | 同 |
| 軸のceiling/単価入替（積は同一） | 同 | 同 |
| 0円追加軸の挿入 | 同 | 同 |
| 単価0のままceiling引上げ | 同 | 同 |
| slot_id を同値で「変更」（真のno-op） | 同一予約を返す（正しい） | — |

初回FAILのC2（provider `fixture`→`openai`、model、価格版、軸配分の全面差し替え）は再現しない。v1 planは admission と再水和の**両方**で拒否される（R6）。

過剰緊縮による正当な運用の破壊も確認した。同一manifestの再admission/再水和は同一予約を返し（R7）、JSONのkey順序変更はidentity中立である（R8、`sort_keys=True`）。

plan identityの完全性検査（`budget.py:501-509`）も独立に破った: 空/短い/大文字hash、`closing_slots` 空、`closing_reserve=None`、いずれか1 batchのdefinition versionが `phase5-run-budget-v1` のまま — **6形すべて** `run plan manifest identity is incomplete or inconsistent` で拒否（R12）。

## 5. 回帰と保持されるP3残置リスク

**回帰なし。** 全non-local 410 passed / 1 deselected（初回405から+5、いずれも新規回帰test）。tokenizer runtime binding は不変（R13: alias一致で `gguf-tokenizer:af98a89…`、不一致で `provider-default:other:unverified`）。金額包絡・pool借用・settle/recoveryのPhase 5不変条件は `test_phase5_budget_reservations.py` / `test_phase5_normal_run_closing.py` を含む focused 69件と全体suiteでgreen。

**初回監査のP3-1〜P3-8を残置リスクとして保持する。** 悪化はない。実測で再確認:

- **P3-1**（巨大 `unit_ceiling` が `ValueError` でなく `OverflowError`）: 再現、未変更。
- **P3-2**（deterministic slotのみのclosing batchが表現不能）: 再現、未変更。
- **P3-3**（`closing_slots` がparse後に未参照 / `run.completion` の `closing_batch` identityが価格付きslotを含まない）: **部分的に改善**。`closing_slots` は `manifest_hash` 経由で全予約identityに入った。実行済みslotの被覆をruntimeで照合しない点は残る。
- **P3-4〜P3-8**（tokenizer: 再hash偽造の受理、`scalars` がlistのときの `TypeError` 逸脱、dirty llama.cpp、split GGUF未検証、単一alias固定）: 該当4ファイルがbyte-identicalのため全項そのまま保持。

**新規の残置リスク（いずれもP3、非blocking）:**

- **P3-9** `budget.py:501` — `admit_run_plan` は `plan.manifest_hash` を与えられたまま信頼し、manifestから再計算しない。手組みの `RunBudgetPlan` に自己整合的な偽hash（`"c"*64`）を持たせると admission が通る（R11）。ただしproduction経路は `pipeline.py:605` の `from_manifest` のみでseedから到達できず、hashが存在しなかった修繕前より厳密に良い。
- **P3-10** `budget.py:1114` — manifest identityがJSONの数値表記に敏感（`1.0` → `1` でhashが変わる）。R9で確認したとおり結果は誤再利用ではなく `ReservationConflict`（fail-closed）だが、seedの整形だけでrunが再開不能になりうる。

**未検証:** 有償provider callを伴う実費経路（範囲外）。tokenizer/GGUFの全面再監査は差分が無いため handoff の指示どおり実施していない（byte-identicalであることのみ確認）。

## 6. 判定

P2-1・P2-2はいずれも根本原因に対して閉鎖されており、修繕は指摘範囲を超えて拡大していない。残るP0–P2はない。P3-1〜P3-10は残置リスクとして明示保存されたい。

VERDICT: PASS
