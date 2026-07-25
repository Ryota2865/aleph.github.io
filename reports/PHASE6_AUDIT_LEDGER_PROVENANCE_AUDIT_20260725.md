# ALEPH Phase 6 R-5 formal audit ledger provenance — 独立正式監査

## Identity 実測（開始＝終了で不変）

| 項目 | 開始 | 終了 | 候補記載 |
|---|---|---|---|
| branch | `codex/phase6-r5-audit-ledger-provenance` | 同左 | ✓一致 |
| HEAD | `8af11d7c…0b61d28` | 同左 | ✓一致 |
| staged tree (`git write-tree`) | `d18330b7…1e80838e` | 同左 | ✓一致 |
| staged files | 9 | 9 | ✓一致 |
| unstaged/untracked | 0 | 0 | ✓一致 |
| `git diff --cached --check` / `--check` | clean (rc=0) | clean (rc=0) | ✓ |

故障注入・旧実装RED再現は `/tmp/r5audit` のみで実施。リポジトリは read-only を維持し、tree hash は監査前後で不変。

## tests-green（客観シグナル、formal verdictとは分離）

すべて Observed evidence（自分で実行）:
- `bash scripts/doctor.sh` → `failures=0 warnings=1`（warnはローカル変更ありの想定内）
- focused `tests/test_repository_snapshot.py` → **28 passed**（施工記録一致）
- full `-m 'not local'` → **433 passed, 1 deselected**（施工記録一致）
- `compileall aleph scripts` → rc=0 PASS
- `audit_repository_snapshot.py --format report` → 下記current-state
- `git diff --cached --check` / `git diff --check` → clean

tests-green は「壊れていない」ことを示すのみで、formal verdict はこれと独立に契約充足で判定した。

## 中心契約の検証（Observed evidence）

生産差分は `formal_audits` provenance tuple 先頭への **1項目追加のみ**（`git diff --cached` 実測）:
```
-  "formal_audits": ("audits/", "reports/*AUDIT*.md"),
+  "formal_audits": ("config/formal-audits.json", "audits/", "reports/*AUDIT*.md"),
```
コード変更は `repository_snapshot.py`＋`test_repository_snapshot.py` の2ファイルのみ、他7ファイルは doc（stat実測）。契約8のproduction差分＝1項目追加を確認。

独立故障注入スクリプト（`/tmp` の base HEAD 旧実装 vs live候補、fixture）で **26/26 PASS**:

| 契約 | 検証 | 結果 |
|---|---|---|
| 1 | provenance が権威ledger＋artifact集合の両方を列挙 | ✓ |
| 2/3 | serialized順序 = `config/formal-audits.json` → `audits/` → `reports/*AUDIT*.md`、ledger先頭 | ✓ `.provenance` と `to_dict()["provenance"]` 両面 |
| 4 | artifact sources保持・ledger重複登録なし（count=1、末尾2要素保持） | ✓ |
| 5 | ledger missing/空file/空json/malformed で例外なし・provenance三入力維持 | ✓ 両面 |
| 6 | assurance provenance が base↔候補で不変、ledger/artifact/CHANGELOG/Git stateを列挙 | ✓ |
| — | RED再現: base HEAD旧実装は `["audits/","reports/*AUDIT*.md"]` のみを返し権威ledgerを隠す | ✓ 両面 |
| — | ledger存在fixtureで entry が sequence=1 / target_changelog=0.7.20 / candidate_tree / ledger=registered をledgerから取得、かつprovenanceにもledgerが出現 | ✓ |

契約7（artifact inventory・ledger validation・verdict・currency・tree binding・closure allowlist）は、生産差分が静的provenance宣言への1項目追加に限定され、`_formal_audits` の検証ロジックに一切手が入っていないことから不変（diff実測）。

**Inference**: provenance は runtime非依存の静的宣言であり、`_formal_audits` は degraded ledger でも常に `config/formal-audits.json` を読みにいく。よって「moduleが読む宣言入力を正直に示す」（契約5・designs §2.3）は構造的に成立している。

## current-state 表示（Observed evidence）

`audit_repository_snapshot.py --format report` 実測:
- latest recorded formal audit: **PASS** ✓
- formal audit path: **reports/PHASE6_BUDGET_SNAPSHOT_ISOLATION_AUDIT_20260725.md** ✓
- formal audit currency: **NEEDS_AUDIT** ✓
- formal audit tree state: **INDEX** ✓

指定4項目すべて一致。

## スコープ規律（契約8）

CHANGELOG 0.7.20-34・designs §5 とも R-6〜R-9・R-2残置P3・R-4監査P3 を明示的に非目標として除外。差分にこれらの混入なし（コード変更2ファイルの実測で確認）。doc群（PLAN.md §版表記、CHANGELOG、PROGRESS、README×2、next-designer-execution-plan、新規designs）は施工記録と数値・契約が整合。

## Findings（P0〜P3）

- **P0 / P1 / P2**: なし。
- **P3**: なし（実質的な指摘なし）。provenance を静的宣言とする設計は契約5を満たす honest な選択であり、指摘対象ではない。

## Uncertainty

- 施工記録どおり、新作・local inference・有償API call・provider cost照合は未実行であり、本監査でも実施していない（read-only／self-contained のため妥当）。当該領域への影響は差分上存在しない。
- doctor の `git worktree: has local changes` warn は staged 変更の存在による想定内で、identity不変性に影響しない。

## 結論

8つの中心契約すべてを Observed evidence で確認、独立RED→GREEN故障注入 26/26 PASS、degraded ledger 全系で例外なし・provenance三入力維持、assurance provenance不変、current-state表示一致、identity監査前後不変。tests-green と formal verdict を分離しても、契約充足は独立に成立している。指摘（P0〜P3）なし。

**R-5 は formal 完了としてよい。** Codex施工に必要な独立Claude Code監査PASSの要件を、本監査が満たす。

VERDICT: PASS
