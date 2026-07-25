# ALEPH Phase 6 R-4 budget snapshot isolation — 独立正式監査

## 0. 監査規律とidentity不変

**監査方式**: read-only。候補は一切変更せず、故障注入・旧実装RED再現はすべて `/tmp/r4audit/` 配下で実施。base HEAD旧実装は `git show HEAD:…` で抽出し、候補は working tree==index の実モジュール import で検証。

| 項目 | 開始時実測 | 終了時実測 | 不変 |
|---|---|---|---|
| branch | codex/phase6-r4-budget-snapshot-copy | 同左 | ✓ |
| HEAD | d882c368b892bd86a91ecddf11ee6a4a440b3f13 | 同左 | ✓ |
| git write-tree | ab0901a821716cb57da231df97706015fe0e4164 | 同左 | ✓ |
| staged files | 9 | 9 | ✓ |
| unstaged/untracked | 0（全INDEX） | 0（全INDEX） | ✓ |
| diff --cached --check | rc=0 clean | rc=0 clean | ✓ |
| diff --check | rc=0 clean | rc=0 clean | ✓ |

候補identity不変を確認。監査による副作用なし。

## 1. tests-green（施工シグナルの独立再実行 — formal verdictとは別評価）

| コマンド | 結果 |
|---|---|
| `bash scripts/doctor.sh` | failures=0 warnings=1（worktree has local changes=候補stagingのため正常）|
| `pytest tests/test_repository_snapshot.py -q` | **27 passed** |
| `pytest -m 'not local' -q` | **432 passed, 1 deselected** |
| `python -m compileall -q aleph scripts` | PASS |
| `audit_repository_snapshot.py --format report` | 下記§4で照合 |
| `git diff --cached --check` / `git diff --check` | clean |

施工記録（focused 27 / full 432,1 deselected / compileall / diff clean）と完全一致。**これはtests-greenであり、正式判定そのものではない。**

## 2. 独立故障注入（Observed evidence）

差分ハーネス `/tmp/r4audit/differential.py` で base HEAD（`self.budget`）と候補（`deepcopy(self.budget)`）を同一fixtureで対比:

| 検証 | base HEAD (RED) | 候補 (GREEN) |
|---|---|---|
| baseline: payload値 == snapshot.budget値 == 1.25 | True | True |
| `ledgers.api.spent` 変更 → snapshotへ逆流 | **99.0へ逆流** | 1.25不変 |
| `ledger_status.api.spent` 変更 → 逆流 | **99.0へ逆流** | 1.25不変 |
| `work_spent.w9100` 変更 → 逆流 | **99.0へ逆流** | 1.25不変 |
| 第一payload変更後の第二 `to_dict()` | 汚染される | 非汚染（1.25） |
| 空budget（`{}`）: 例外 | なし | なし |
| 空budget: 返却keys（9キー）| old==cand で同一 | shape不変・leakなし |

- **base HEAD RED再現**: 施工記録「1.25→99.0」の逆流を三面すべてで独立再現。
- **候補GREEN**: 三面すべて逆流せず、第二 `to_dict()` も非汚染。
- **見かけ上の分離でないことの排除**: 変更前payload値と `snapshot.budget` 値が共に1.25で同値 → 単なる値欠落による偽の分離ではなく、実データ経由の真の detach。
- **空budgetの健全性**: 例外を起こさず、返却shape（`api_cap, api_spent, ledger_status, ledgers, period_key, publish_cap, publish_count, usd_per_work, work_spent`）が旧実装と同一。

## 3. 契約・スコープ照合（Observed evidence）

- **修繕局所性（監査項目5）**: production差分は `repository_snapshot.py:34` の1行 `self.budget` → `deepcopy(self.budget)` のみ（`git diff --cached -- aleph/` で他の追加・変更行ゼロを実測）。呼出し側adapterへの責務分散なし。serialization seam一箇所に限定。
- **値・shape・算出・provenance不変（監査項目4）**: `_budget()` メソッド無変更、provenance dict無変更。deepcopyは値と入れ子構造を同型保存（§2で実測）。
- **回帰なし（監査項目6）**: `assurance`/`design_state` は既にdeepcopy済み。deepcopy追加は防御的複製のみで算出値を変えない。assurance・design_state・formal audit・deadline・works・予算上限・予約・charge/reconciliation・生成経路は432 non-local testsでgreen。
- **混入なし（監査項目8）**: 変更コードは budget deepcopy 1行のみ。R-5〜R-9、R-2残置P3の混入なし（設計非目標と一致）。
- **staged 9ファイル**: code(1) + test(1) + 設計doc + PLAN_CHANGELOG 0.7.20-33 + PROGRESS + README×2 markers + exec-plan status + PLAN版。stray無し。

## 4. current-state正直表示（監査項目7 — Observed evidence）

`audit_repository_snapshot.py` 実出力:
- latest formal audit = **PASS** ✓
- path = **reports/PHASE6_AUDIT_STRICT_VERDICT_AUDIT_20260725.md** ✓
- currency = **NEEDS_AUDIT** ✓
- tree state = **INDEX** ✓
- unexpected paths = R-4候補4ファイル（PLAN.md, repository_snapshot.py, 設計doc, tests）

README markers（両言語）は CURRENT→**NEEDS_AUDIT** へ更新済みで、未監査R-4 tree が R-3 closure を逸脱する事実を正直に反映。PLAN版は 0.7.20-32→0.7.20-33 に整合更新（design-state staleと矛盾しない）。changelog 0.7.20-33 は「Codex施工のため正式完了は独立Claude Code監査PASSを要する」と明記し、formal完了を**先取り主張していない**。

## 5. Findings（P0–P3）

- **P0 / P1 / P2**: なし。
- **P3-1（残置・非ブロッキング, Inference）**: `to_dict()` は `experiments`/`active_jobs`/`deadlines`/`formal_audits` に対し依然 `dict(item)` の浅いコピー。現状これらの item は平坦なため入れ子逆流は存在せず、他seam修繕はR-4の明示的非目標。残置リスク記録のみ。
- **P3-2（Uncertainty）**: runtimeのcharge/reconciliation・provider cost照合・local inference・有償APIは規約により未実行。当該経路の回帰不在の確度は 432 non-local tests に依拠する（施工記録どおり）。

## 6. 区分の明示

- **Observed evidence**: §0〜§4のすべて（identity実測、テスト実出力、RED/GREEN差分注入、audit script出力、diff実測）。
- **Inference**: deepcopyが全入れ子で値・shapeを保存すること（三面＋空budgetで実測裏付けあり）。P3-1のseam判断。
- **Uncertainty**: P3-2（未実行の有償・runtime経路）。

## 7. 正式完了判定

R-4は受入条件（分離契約・三面逆流不在・focused/全non-local/compileall/diff green・監査前 PASS/NEEDS_AUDIT 表示・canon不変）をすべて満たす。tests-greenと本正式判定は分離して評価した。P0〜P2の指摘なし。**R-4をformal完了として承認してよい**（残置P3-1/P3-2は非ブロッキングの残余リスクとして記録）。

VERDICT: PASS
