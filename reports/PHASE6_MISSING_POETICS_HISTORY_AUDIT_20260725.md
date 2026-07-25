# ALEPH Phase 6 R-8 正式監査レポート

## Identity(開始=終了、不変確認)

| 項目 | 実測値 | 判定 |
|---|---|---|
| branch | `codex/phase6-r8-missing-poetics-history` | 一致 |
| HEAD | `3e484fa5e01a90c35d4c823cafc1f5fdebeedace` | 一致 |
| staged tree | `57d95d4ca9ebf2d82eec301026a943e96e82d7d5` | 一致 |
| staged files | 9 | 一致 |
| unstaged/untracked | 0（WSL権威側） | 一致 |
| diff checks | clean | 一致 |

Windows Git Bash経由のmode-bit表示はUNC/SMB計測artifactで、WSL native候補には存在しない。故障注入は`/tmp`のみで実施し候補は不変。

## tests-green

- doctor: failures=0, warnings=1
- focused: **31 passed**
- full non-local: **436 passed, 1 deselected**
- compileall: PASS
- diff checks: clean
- current-state: PASS / `reports/PHASE6_CHANGELOG_VERSION_ORDER_AUDIT_20260725.md` / NEEDS_AUDIT / INDEX

tests-greenとformal verdictは分離した。

## 独立故障注入

| scenario | old | candidate |
|---|---|---|
| poetics dirあり・history欠落 | v0、warningなし（RED） | v0、missing warning一件（GREEN） |
| 空history | v0、missing warningなし | 同一 |
| 有効1行 | v1 | 同一 |
| 有効3行＋空行 | v3 | 同一 |
| malformed JSON | UNKNOWN＋malformed | 同一 |
| JSON非object | UNKNOWN＋malformed | 同一 |
| poetics dir欠落 | UNKNOWN＋dir warning | 同一、history warningなし |

warningは厳密に`poetics/history.jsonl is missing; poetics defaults to v0`で一件。snapshot後もhistoryは作成されず、`to_dict()`とsnapshot値は一致した。production差分は欠落判定とwarning追加の2行だけで、canonical `current_version()`を維持する。

READMEのpoetics v1、作品、予算、期限は不変。R-9および残置P3の混入なし。新作、local inference、有償API、provider cost照合は未実行。

## Findings / Uncertainty

P0/P1/P2/P3なし。local系未実行とstaged候補によるdoctor warningはscope上妥当。

## 判定

RED→GREEN、6シナリオ回帰なし、契約10項目、identity不変を独立確認した。R-8をformal完了として問題ない。

VERDICT: PASS
