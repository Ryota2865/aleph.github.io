# ALEPH Phase 6 R-2 P2-1 focused 再監査報告

初回 FAIL を発行した同一監査担当として、read-only で focused 再監査しました。repository への
書き込みは行っていません（故障注入はすべて `/tmp` 配下）。

## 1. Candidate identity 実測

| 項目 | 供給値 | 実測（開始時） | 実測（終了時） |
|---|---|---|---|
| branch | `codex/phase6-audit-tree-binding` | 一致 | 一致 |
| HEAD | `0828082bef8ae129ce6642a294bbb7c47953a41a` | 一致 | 一致 |
| `git write-tree` | `9940cbb4062187ce93fd4cdc394ecc98b52b522c` | **一致** | **一致** |
| `git diff --name-only` | 空 | 空 | 空 |
| untracked（`-uall`） | 0 | 0 | 0 |
| staged files | 14 | 14 | 14 |

初回 FAIL tree `51c9f05…` からの差分は依頼どおりの範囲に収まっています。

**保存 FAIL 証拠（observed）**: `reports/PHASE6_AUDIT_TREE_BINDING_AUDIT_20260725_FAIL.md`
は初回報告の原文（202行、末尾 `VERDICT: FAIL`）としてそのまま追加されており、改変は
ありません。ledger sequence 5 に `target_changelog=0.7.20-29`,
`candidate_tree=51c9f05…` で登録済み。既存 sequence 1–4 は無変更です。

## 2. P2-1 の修繕内容（差分読解）

`aleph/core/repository_snapshot.py` の変更は**この6行のみ**です。

```python
-        if has_staged:
-            diff = run("diff", "--cached", "--name-only", candidate_tree, "--")
-            state = "INDEX"
-        else:
-            diff = run("diff", "--name-only", candidate_tree, head_tree, "--")
-            state = "HEAD"
+        try:
+            if has_staged:
+                ...INDEX...
+            else:
+                ...HEAD...
+        except (OSError, subprocess.SubprocessError):
+            return base
```

初回指摘した最小修正の形と一致し、`base` を返すため tree binding は `UNAVAILABLE`、
`_assurance` の `binding["state"] == "UNAVAILABLE"` 分岐で currency は `UNKNOWN` へ
fail closed します。soundness 判定、`_valid_closure_paths` の fixed 集合、ref 正規表現、
changelog 比較、dirty 判定はいずれも 1 文字も変わっていません。

## 3. P2-1 修繕前 RED ／ 修繕後 GREEN（独立故障注入、observed）

monkeypatch ではなく **PATH shim で本物の `git diff` を 30 秒ハングさせ**、実 timeout を
発火させました。同一スクリプトを初回 FAIL tree から取り出したモジュール
（`git show 51c9f05:aleph/core/repository_snapshot.py`）と修繕 tree の双方へ適用しています。

**RED — 初回 tree `51c9f05`（module=`/tmp/aleph-oldtree/...`）**

```text
clean-HEAD  / no fault      : RETURNED currency=CURRENT  state=HEAD
staged-INDEX/ no fault      : RETURNED currency=CURRENT  state=INDEX
clean-HEAD  / git diff hang : RAISED TimeoutExpired      ← 再現
staged-INDEX/ git diff hang : RAISED TimeoutExpired      ← 再現
clean-HEAD  / git diff exec✗: RETURNED currency=UNKNOWN  state=UNAVAILABLE
staged-INDEX/ git diff exec✗: RETURNED currency=UNKNOWN  state=UNAVAILABLE
```

**GREEN — 修繕 tree `9940cbb`（module=repository の実ファイル）**

```text
clean-HEAD  / no fault      : RETURNED currency=CURRENT  state=HEAD
staged-INDEX/ no fault      : RETURNED currency=CURRENT  state=INDEX
clean-HEAD  / git diff hang : RETURNED currency=UNKNOWN  state=UNAVAILABLE
staged-INDEX/ git diff hang : RETURNED currency=UNKNOWN  state=UNAVAILABLE
clean-HEAD  / git diff exec✗: RETURNED currency=UNKNOWN  state=UNAVAILABLE
staged-INDEX/ git diff exec✗: RETURNED currency=UNKNOWN  state=UNAVAILABLE
```

required verification 1〜3 を充足します。**staged index 経路と clean HEAD 経路の双方**で、
timeout・起動失敗のいずれも同じ fail-closed 結果になり、`snapshot()` は返ります
（read surface 維持）。障害がない場合の `CURRENT/HEAD`・`CURRENT/INDEX` は不変です。

## 4. 回帰確認（required verification 4）

初回監査で用いた 29 シナリオ＋3 追加 probe を修繕 tree へ再実行しました。

- **28/29 が期待どおり**（初回は 27/29）。増分は S8c（diff timeout）の OK 化のみ。
- 残る 1 件の "MISMATCH" は初回同様、私が期待文字列に `state=UNAVAILABLE` と書いた誤りで、
  実装は正しく `currency=NEEDS_AUDIT / state=HEAD` を返しています（S7: Git 三点一致＋
  target CHANGELOG 不一致）。
- tree/commit/ref の不在・不一致 5 種 → 全て `UNKNOWN / UNAVAILABLE`、変化なし。
- closure allowlist 拒否 9 種（`aleph/…`, `tests/…`, 契約 design 2 種, 他 report, 絶対 path,
  `..`, 重複, `PLAN.md`）→ 全て ledger invalid、変化なし。
- candidate_ref 拒否 5 種 → 全て ledger invalid、変化なし。
- dirty（unstaged / untracked）→ `NEEDS_AUDIT / DIRTY`、変化なし。
- rename で code を allowlist path へ退避 → `unexpected=['aleph/impl.py']`、変化なし。
- code の staged 削除のみ → `NEEDS_AUDIT / INDEX`, `unexpected=['aleph/impl.py']`、変化なし。

## 5. Required checks（独立再実行、observed）

| 検査 | 施工側記録 | 独立実行 |
|---|---|---|
| `scripts/doctor.sh` | failures=0 | `SUMMARY failures=0 warnings=1 network=0` |
| focused `tests/test_repository_snapshot.py` | 21 passed | **21 passed** |
| 全 non-local | 426 passed, 1 deselected | **426 passed, 1 deselected** |
| `compileall -q aleph scripts` | PASS | PASS |
| `git diff --cached --check` | PASS | PASS |
| `git diff --check`（worktree） | PASS | PASS |
| `audit_repository_snapshot.py --format report` | FAIL / UNKNOWN / UNAVAILABLE | **一致**（下記） |

```text
- latest recorded formal audit: FAIL
- formal audit path: reports/PHASE6_AUDIT_TREE_BINDING_AUDIT_20260725_FAIL.md
- formal audit currency: UNKNOWN
- formal audit tree state: UNAVAILABLE
- formal audit unexpected paths: none
```

CLI も `latest recorded formal audit: FAIL (currency=UNKNOWN, tree=UNAVAILABLE, path=…)`。
README 日英 marker は `readme_status_markdown()` 出力と完全一致（ja/en とも True）。
FAIL entry は `candidate_commit` を持たないため `_assurance` が Git 照合前に `UNKNOWN` へ倒れ、
`tree_binding.state=UNAVAILABLE` になります。**古い PASS へ fallback していない**ことを確認。

## 6. Findings

### P0 / P1 / P2: なし

初回 P2-1 は**閉鎖**。RED を実 timeout で再現し、修繕後は HEAD/INDEX 両経路で
`UNKNOWN / UNAVAILABLE` へ fail closed することを独立確認しました。中心契約（tree/commit/ref
三点束縛、closure allowlist、changelog 束縛、dirty 判定）に回帰はありません。

### P3-5（新規・残置）FAIL ledger entry が runbook §3 の記載要件を満たしていない

`designs/formal-audit-runbook.md:43–50`（本候補で改訂された本文）は「**every new formal
artifact** を … `candidate_tree`、そのtreeを持つ proof `candidate_commit`、
`refs/tags/audit-candidate/` 配下の durable `candidate_ref` とともに登録する」と述べます。
一方 `config/formal-audits.json` sequence 5（FAIL artifact）は `candidate_tree` のみで、
commit/ref を持ちません。実測すると tree `51c9f05…` は loose object として存在しますが
**どの ref からも到達不能**です（`git rev-list --all --objects | grep -c 51c9f05…` → 0）。
すなわち FAIL 報告が引用する候補 tree は GC で失われ得ます — design §5 が名指しした
「local unreachable tree object と GC 偶然性」そのものです。

soundness への影響はありません（FAIL entry は commit 不在ゆえ元より `UNKNOWN`）。
運用文書と実践の不一致、および FAIL 証拠の耐久性の問題であり、blocking scope 外の
残置として記録します。是正は「FAIL 側も proof commit/tag を作る」か「runbook §3 を
PASS entry 限定と明記する」のどちらかです。

### P3-6（新規・残置）新規 RED テストが修繕 2 箇所のうち 1 箇所しか覆っていない

`tests/test_repository_snapshot.py::test_git_diff_timeout_preserves_snapshot_and_returns_unknown`
は closure を commit 済みの clean worktree を作るため、`git diff --name-only`（HEAD 経路、
旧 :537）だけを通ります。`git diff --cached --name-only`（INDEX 経路、旧 :534）を通る
RED テストはありません。今回は私が実 shim で INDEX 経路も GREEN を確認済みですが、
将来の refactor で INDEX 側だけが再び guard 外へ出ても既存テストは緑のままです。
また同テストは `subprocess.run` を monkeypatch するため、`timeout=5` 引数が実際に
渡されていること自体は検証していません。

### P3-1〜P3-4（初回からの残置、再掲）

1. **P3-1** closure allowlist が canon 参照文書 `designs/next-designer-execution-plan.md` を
   含み、path 粒度ゆえ「状態段落」と「契約段落」を区別できない。
2. **P3-2** proof commit `9bdfe0e` の到達性が lightweight tag 単独に依存する
   （`push --follow-tags` の対象外）。origin 上の存在は初回監査時に実測確認済み。
3. **P3-3** `config/formal-audits.json` 自身が allowlist 内にあり、ledger 権威が自己言及的。
   R-2 は tree の実在性を束縛するが ledger 記載の真正性は束縛しない。
4. **P3-4** legacy entry 1–3 は commit/ref を持たず構造上 `CURRENT` になり得ない（設計の
   非目標と整合、保守側）。

初回 uncertainty も維持します: `git status` は `.gitignore` と
`assume-unchanged`/`skip-worktree` を尊重するため、それらで隠された作業ツリー差分は DIRTY
判定を回避し得ます（本候補で該当は未検出、`git ls-files -v` 相当の検査は未実施）。

## 7. public 面への影響

staged 14 file に `works/`、`state/`、`config/budgets.yaml` は**含まれません**（実測 NONE）。
作品生成経路への変更なし。予算・期限・公開作品数は不変（api 69.628952/71.0 USD、
deadline UPCOMING 2026-08-01、公開 5 作、works 9 作）。今回の再監査でも新作生成・local
inference・有償 API call・provider cost 照合は一切行っていません。

## 8. tests green と formal verdict の分離

focused 21 passed / 全 non-local 426 passed / compileall / diff check green は施工品質の証拠
であり、それ自体は formal verdict ではありません。本 PASS の根拠は §3 の**実 timeout 注入に
よる RED→GREEN の対比**と §4 の 28/29 回帰一致であって、テスト緑ではありません。

## 9. R-2 を formal 完了としてよいか

**よい。** 初回 FAIL の唯一の blocking finding P2-1 は、指摘どおりの最小修正で閉鎖され、
HEAD/INDEX 両経路・timeout/起動失敗の両変種で fail-closed を独立実測しました。R-2 の中心
契約（candidate tree/commit/ref 三点束縛、clean HEAD または fully-staged index の currency
対象化、closure allowlist、changelog 束縛、UNKNOWN への fail-closed、監査可能な表示面）は
回帰なく成立しています。残る P3-1〜P3-6 は soundness を損なわない残置リスクであり、runbook
§3「A PASS may retain explicit P3 observations」の範囲内です。

closure 時には、この報告を `reports/` へ保存し ledger sequence 6 として登録するとともに、
P3-5（FAIL entry の commit/ref 欠落と runbook §3 の文言不一致）をどちらの方向で解消するかを
次の設計判断として記録することを推奨します。

VERDICT: PASS
