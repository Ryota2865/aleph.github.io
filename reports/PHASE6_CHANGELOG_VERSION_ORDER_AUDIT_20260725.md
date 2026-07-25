# ALEPH Phase 6 R-7 — CHANGELOG version-order 正式監査報告

## 1. Identity 実測(開始 = 終了、不変)

| 項目 | 開始 | 終了 | 候補宣言 | 一致 |
|---|---|---|---|---|
| branch | `codex/phase6-r7-changelog-order` | 同 | 同 | ✓ |
| HEAD | `c11950c0412de4ec73694222c2b963bdea971489` | 同 | 同 | ✓ |
| write-tree | `57250a822ff8f095200df0e07c486a9cad1e7557` | 同 | staged tree 同値 | ✓ |
| staged files | 9 | 9 | 9 | ✓ |
| unstaged/untracked | 0 | 0 | 0 | ✓ |
| `diff --cached --check` | rc=0 clean | rc=0 clean | clean | ✓ |
| `diff --check` | rc=0 clean | rc=0 clean | clean | ✓ |

故障注入・旧実装 RED 再現はすべて `/tmp/audit_r7/` 内で実施。候補ツリーは一切変更していません。

## 2. tests-green(客観シグナル — verdict とは分離)

| コマンド | 結果 | 施工記録 | 一致 |
|---|---|---|---|
| `bash scripts/doctor.sh` | failures=0, warnings=1(staged 変更ゆえ想定内) | — | ✓ |
| focused `test_repository_snapshot.py` | 30 passed | 30 passed | ✓ |
| full `-m 'not local'` | 435 passed, 1 deselected | 同 | ✓ |
| `compileall aleph scripts` | PASS | PASS | ✓ |
| `git diff --cached/--check` | clean | clean | ✓ |
| `audit_repository_snapshot.py --format report` | PASS / path一致 / **NEEDS_AUDIT** / tree state **INDEX** | — | ✓ |

current-state 表示(実測):latest formal audit=**PASS** / path=`reports/PHASE6_MISSING_PUBLISH_CAP_AUDIT_20260725.md` / currency=**NEEDS_AUDIT** / tree state=**INDEX**。

## 3. Observed evidence(独立検証)

Production差分は `_design_state` 内のCHANGELOG heading収集・版順選択ブロックのみ。旧実装の物理先頭一致から、fence追跡・全heading収集・数値tuple最大へ変更された。

`/tmp/audit_r7/verify.py` 20/20 check PASS:

- 物理先頭 `0.7.20-35` が後方 `0.8.1` を隠す旧REDを再現し、新実装は`0.8.1`を選択。
- 4エントリ全24順列でlatest=`0.10.0`。
- `0.9.0`より`0.10.0`を選ぶ数値順を確認。
- backtickとtilde fence内の偽版を無視。
- blockquote見出しを無視し、fence終了後の正規見出しは再び候補。
- titleなし、hyphenated版、次series、見出し0件で回帰なし。
- PLAN宣言不一致で正しいstale warning、一致でstaleなし。

実repositoryはdeclared=latest=`0.7.20-36`、latest_change=「Phase 6 CHANGELOG版順の明示化」、stale=[]。契約1–10を充足し、R-8〜R-9等の非目標は混入していない。

## 4. Inference

README日英の`CURRENT→NEEDS_AUDIT`は新CHANGELOG追加に対する正しい未監査表示。中心変更は選択規則に限定され、title、stale、UNKNOWNの既存面を保持する。

## 5. Uncertainty(P3・非ブロッキング)

- 版キーは数値を平坦化するため、理論上 `1-2` と `1.2` が同順になる。
- 未閉fenceは後続headingを飲み込む。実CHANGELOGはfence 0件。
- CommonMarkの3空白以内インデントfenceは未認識。

いずれも宣言済み非目標であり、P0/P1/P2は検出されなかった。

## 6. 結論

identity不変、中心契約1–10、RED→GREEN、順序不変、数値順、fence/blockquote除外、回帰なし、current-state一致を独立確認した。

**R-7 は formal 完了として承認してよい。**

VERDICT: PASS
