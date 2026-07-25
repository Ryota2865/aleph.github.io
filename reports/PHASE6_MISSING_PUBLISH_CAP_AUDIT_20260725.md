# ALEPH Phase 6 R-6 — publish cap欠落可視化 正式監査報告

独立・read-only監査。故障注入と旧実装RED再現は`/tmp`のみで実施し、終了後に破棄済み。

## Identity不変（実測）

| 項目 | 開始 | 終了 | 宣言値 | 一致 |
|---|---|---|---|---|
| branch | `codex/phase6-r6-missing-publish-cap` | 同left | 同left | ✓ |
| HEAD | `6c2d7ec8de8368…` | 同left | 同left | ✓ |
| staged tree (write-tree) | `5390cb2e0212…` | 同left | 同left | ✓ |
| staged files | 9 | 9 | 9 | ✓ |
| unstaged/untracked | 0 | 0 | 0 | ✓ |
| diff --cached --check / --check | — | 両exit 0 | clean | ✓ |

candidate treeは監査中も不変。production変更を含むstagedファイルのうち `aleph/` 配下は `aleph/core/repository_snapshot.py` の1本のみ。残り8本はdoc/test（PLAN/PLAN_CHANGELOG/PROGRESS/README×2/next-designer/phase6設計/test）。

## tests-green（施工シグナルの再現、formal verdictとは分離）

Observed evidence（実行済み・出力確認済み）:
- `bash scripts/doctor.sh` → `failures=0 warnings=1`（WARNは「git worktree: has local changes」＝施工中で想定内）
- `uv run pytest tests/test_repository_snapshot.py -q` → **29 passed**
- `uv run pytest -m 'not local' -q` → **434 passed, 1 deselected**
- `uv run python -m compileall -q aleph scripts` → exit 0（PASS）
- `git diff --cached --check` / `git diff --check` → 両clean
- `scripts/audit_repository_snapshot.py --format report` の current-state:
  - latest recorded formal audit = **PASS**
  - path = `reports/PHASE6_AUDIT_LEDGER_PROVENANCE_AUDIT_20260725.md`
  - currency = **NEEDS_AUDIT**
  - tree state = **INDEX**

いずれも施工記録および要求されたcurrent-state表示と完全一致。

## 中心契約の検証（独立故障注入）

`/tmp`へold実装(HEAD `6c2d7ec`)とnew実装(候補working tree=staged, unstaged 0で同値)を分離抽出し、空rootへ`budget_config`を注入して`snapshot()`を実測（`today`可変）。

| シナリオ | OLD (RED) | NEW (GREEN) | 判定 |
|---|---|---|---|
| A `publish`セクション欠落 | cap=None, deadlines=(), **warningなし** | cap=None, deadlines=(), missing warning×1 | 契約1,2,3 ✓ |
| B `publish={}` | 同上RED | 同上GREEN | 契約1,2,3 ✓ |
| C `"999"`(str) | notint warning | **同一**(notint warning) | 契約5 ✓ |
| D `999.0`(float) | notint warning | **同一** | 契約5 ✓ |
| E `True`(bool) | notint warning | **同一**（bool=非整数扱い） | 契約5 ✓ |
| F cap=999 @2026-07-31 | UPCOMING / due 2026-08-01 / expired=False | **同一** | 契約6 ✓ |
| G cap=999 @2026-08-01 | EXPIRED / expired=True | **同一** | 契約6 ✓ |
| H cap=4 (通常int) | deadlines=(), warningなし | **同一** | 契約7 ✓ |
| I `max_per_month=None`(key在) | 無警告（missingでもnotintでもない） | **同一** | 境界: key在ならmissing不発 ✓ |
| J config全体不能(budget_config=None) | "repository config is unavailable" のみ | **同一** | 契約: 既存経路不変 ✓ |

**決定的所見（Observed）**: A・B以外の全シナリオでOLDとNEWの出力が**バイト等価**。差分はシナリオA・Bにおける missing warning 1件の追加のみ。

- warning文字列は厳密に `"publish.max_per_month is missing; deadline is unavailable"`。
- production差分は `if "max_per_month" not in publish:` 分岐追加と当該warning appendのみ。値の推測・補完・自動変更なし。deadline生成経路は未改変。
- Inference: section欠落は`budgets.get("publish", {})→{}`経由で空dictと同じmissing判定へ合流する。

## スコープ規律

- 作品・予算値・生成経路・formal audit判定に変更なし。
- R-7〜R-9、R-2残置P3、R-4監査P3の混入なし。
- 新作・local inference・有償API call・provider cost照合は未実施。

## Findings

P0 / P1 / P2 / P3 とも **該当なし**。

## Uncertainty

- fullテストは`-m 'not local'`のためlocal-inference系は未実行。本修繕はconfig面の純関数変更で外部依存なし。
- `git write-tree`監査中に`diff` exit codeが一度0表示となった観測があるが、wrapper起因の表示ノイズで実害なし。

## tests-green と formal verdict の分離

tests-greenとは独立に、故障注入で全中心契約をObserved evidenceとして確認し、identity不変・スコープ規律も充足。

## R-6 formal完了可否

**可**。中心契約9項目すべてが独立故障注入で確認され、P0〜P3なし、identity不変、production差分はmissing key判定＋warning追加に厳密に限定。R-6を正式完了として差し支えない。

VERDICT: PASS
