# ALEPH Phase 6 R-3 strict terminal verdict — 独立形式監査報告

## 1. Candidate identity(開始=終了で実測、不変)

| 項目 | 期待 | 実測 | 判定 |
|---|---|---|---|
| branch | `codex/phase6-r3-strict-verdict` | 同左 | ✓ |
| HEAD | `3cadc6b…14dbe9` | 同左 | ✓ |
| staged tree (`git write-tree`) | `8580d52…dabb75` | 同左 | ✓ |
| staged files | 9 | 9 | ✓ |
| unstaged/untracked | 0 | 0(`diff --name-only`空) | ✓ |
| `git diff --cached --check` / `--check` | clean | rc=0 / rc=0 | ✓ |

同一性は開始時・終了時とも仕様と完全一致。監査中断条件に該当なし。

## 2. Observed / Inference / Uncertainty の分離

- **Observed(実測):** identity・全コマンド出力・独立故障注入結果・diff本文。
- **Inference(コード読解):** ledger無効化と projection の no-fallback 経路(下記 §4-6/§4-8)。committed test でも裏取り済みだが、判定の一次根拠は実コード行。
- **Uncertainty:** なし(scope内で未検証の分岐は残っていない)。

## 3. 中心実装(`aleph/core/repository_snapshot.py:275-282`)

8行変更。`text.splitlines()` から `line.strip()` が非空の**元line**を保持し、最後の元lineを `{"VERDICT: PASS":"PASS","VERDICT: FAIL":"FAIL"}.get(..., "UNKNOWN")` で辞書照合。regex・`re.I`・コロン後`\s*`・行の`strip()`を全廃。修繕契約1〜4に一致。

## 4. RED → GREEN と独立故障注入(`/tmp` fixture、実`_terminal_verdict`をimport)

26ケースを旧実装(base HEAD再現)と候補実装で対比:

- **NEW mismatches vs expected: 0**(全26一致)
- **OLD 偽陽性RED再現: 9件** — `verdict: pass`/`Verdict: PASS`/`VERDICT: pass`/`VERDICT:PASS`/`VERDICT:  PASS`(複数空白)/`VERDICT:\tPASS`(tab)/行頭空白/行末空白/**NBSP区切り** がすべて旧実装で`PASS`確定 → 候補で全て`UNKNOWN`。

候補が正しく`UNKNOWN`化した exotic ケース(要件3-5):lowercase/mixed、空白なし/複数/tab、prefix/suffix、Markdown bold `**…**`/quote `> …`、**全角コロン**、**NBSP**、**zero-width**混入、**BOM**先頭、本文中verdict語彙が最終行でない場合。
維持した正例(要件4-5):`VERDICT: PASS\n`、LF/CRLF、厳密verdict後の空白のみ末尾行(`\n\n \t\n`)、本文にFAIL語を含むが最終非空行がPASSのケース。

**改行はverdict文字列の一部でなく`splitlines()`境界**という契約も LF/CRLF両系で確認。

## 5. no-fallback / no-alternate-path(要件6・8)

- `_formal_audits` は登録artifactの verdict が `UNKNOWN` のとき **line 444-446** で `ledger_valid=False` を立てる。
- `_assurance` **line 580** は `not ledger_valid or latest.verdict not in {PASS,FAIL}` で status を `UNKNOWN` に落とす。`latest` は sequence最大の登録entryであり、malformed最新は登録されても latest のまま残り、**旧PASSへ降格・fallbackしない**(二重防御)。
- verdictの唯一の生成源は `_terminal_verdict`。glob順/JSON配列順/辞書順/本文語彙からPASSを推測する別経路は存在しない(要件8)。
- committed `test_malformed_latest_verdict_does_not_fall_back_or_become_conclusive` が実projection経路で status=UNKNOWN を確認し、再実行でも通過。

## 6. 回帰なし(要件7)

- ledger: version 1 / 登録7件 / legacy 23件。supersedes順序 2→1・4→3・6→5 健在(R-1 clsoure)。R-3 diff は `config/formal-audits.json` に未接触。
- 該当回帰テスト(supersedes解決・same/future/self/cycle・tree binding・README snapshot整合)は全て full non-local 431 に含まれ通過。
- README日英marker: `currency: CURRENT → NEEDS_AUDIT`(両言語)に変更。**旧PASSを監査済みと詐称せず**、R-3変更が未closureであることを正直に反映(受入条件6の監査前 `PASS / NEEDS_AUDIT` 表示に一致)。
- 付随ドキュメント差分は「作品・予算・期限・生成経路は非変更」を**宣言する行のみ**で、実体変更なし。

## 7. コマンド実測

| コマンド | 結果 |
|---|---|
| `doctor.sh` | `SUMMARY failures=0 warnings=1 network=0` |
| focused `test_repository_snapshot.py` | `26 passed` |
| full `-m 'not local'` | `431 passed, 1 deselected` |
| `compileall aleph scripts` | rc=0 |
| `audit_repository_snapshot.py --format report` | latest=**PASS** / currency=**NEEDS_AUDIT** / tree state=**INDEX** |
| `git diff --cached --check` / `--check` | clean |

## 8. Findings(P0/P1/P2/P3)

- **P0 / P1 / P2:** なし。
- **P3(注記のみ、欠陥ではない):** doctorの `warnings=1 = "git worktree: has local changes"` は構築証拠の `warnings=0` と相違するが、**staged候補(9ファイル未コミット)を監査する設定そのものに内在**する良性警告。`failures=0 / network=0` は一致。R-3スコープ外の `w0001-w0003 unknown termination category` は poetics系で本修繕と無関係。

## 9. tests-green と formal verdict の分離

431 pass / 26 pass は**施工品質の証拠**であり、それ自体は formal verdict ではない。本監査の判定根拠は、独立`/tmp`故障注入(旧9件RED→候補全UNKNOWN、正例維持)と、no-fallback/no-alternate-pathのコード実証、および identity不変。契約1〜6を過不足なく満たし、scope creep なし。

## 10. R-3 を formal 完了としてよいか

**可**。修繕契約を厳密に実装し、規約外artifactのconclusive昇格という偽陽性を除去、fail-closed projection と supersedes/tree/closure/予算・期限・生成経路の不変を維持している。

---

VERDICT: PASS
