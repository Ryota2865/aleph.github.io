# ALEPH Phase 6 R-9 正式監査レポート — audit path 分類排他

## Identity

branch `codex/phase6-r9-audit-ledger-path-disjoint`、HEAD
`a4f177bce58b0c3b2ebc3fd0b194067143872fc5`、staged tree
`8474e45f0f161254ea5e5ed3c63d482405a71762`、staged 9件、
unstaged/untracked 0、diff checks cleanを開始・終了時に実測し、不変を確認した。
故障注入は`/tmp`だけで実施した。

## tests-green

- doctor: failures=0、warnings=1（staged候補）
- focused: **32 passed**
- full non-local: **437 passed, 1 deselected**
- compileall: PASS
- current-state: PASS / `reports/PHASE6_MISSING_POETICS_HISTORY_AUDIT_20260725.md` /
  NEEDS_AUDIT / INDEX

tests-greenとformal verdictは分離した。

## Observed evidence

production差分は、legacy/entry path集合のsorted intersectionをwarningへ出して
`ledger_valid=False`にする処理と、entry validityへ`path not in legacy_paths`を加える処理だけ。

独立故障注入:

- legacy＋sequence 99の同一PASS pathは、旧実装でPASS/registered/無警告、
  候補でUNKNOWN/legacy/固有warning。
- overlapがsequence最大で別registered PASSがあってもfallbackせずUNKNOWN。
- PASS/FAIL/UNKNOWN terminalのoverlapは全てUNKNOWN。
- 3 overlap×entries全6順列でUNKNOWN、warningはsorted path順で不変。
- legacy-only、registered-only、disjoint mixedは旧実装と同値。
- duplicate sequence、missing artifact、valid/invalid supersedes、missing legacyの既存validationに回帰なし。

実repository ledgerはlegacy 23、entries 13、intersection空で、overlap warning増加なし。
中心契約10項を充足した。

## Inference / Uncertainty

`ledger_valid`無効化とentry rejectionの二重ガードによりfalse GREEN経路はない。
固有warningと汎用invalid-entry warningの併発は既存fail-closed経路であり欠陥ではない。
新作、local inference、有償API、provider cost照合はscope外として未実行。

## Findings

P0 / P1 / P2 / P3: なし。

## 判定

RED→GREEN、非overlap同値、既存validation無回帰、実ledger無影響、identity不変を独立確認した。
R-9をformal完了として認めてよい。

VERDICT: PASS
