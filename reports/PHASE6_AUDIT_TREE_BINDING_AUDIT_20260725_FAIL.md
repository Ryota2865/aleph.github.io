# ALEPH Phase 6 R-2 candidate-tree binding — 独立形式監査報告

## 1. Candidate identity（開始時／終了時の不変性）

| 項目 | 依頼値 | 実測（開始時） | 実測（終了時） |
|---|---|---|---|
| repository | `/home/ryota_tanaka/llm_literature` | 一致 | 一致 |
| branch | `codex/phase6-audit-tree-binding` | 一致 | 一致 |
| HEAD | `0828082bef8ae129ce6642a294bbb7c47953a41a` | 一致 | 一致 |
| `git write-tree` | `51c9f05ef0c4dababb61542cba61bc8eb3614acf` | 一致 | 一致 |
| `git diff --name-only` | 空 | 空 | 空 |
| untracked | 0 | 0 | 0 |
| staged files | 13 | 13 | 13 |

監査中に repository へ書き込みは行っていません。故障注入はすべて `/tmp` 配下の使い捨て
repository で実施しました（`/tmp/aleph_r2_inject.py`、`/tmp/aleph_r2_inject2.py`）。

**Evidence durability（observed）**

```text
git cat-file -t 351cd83…  -> tree
git cat-file -t 9bdfe0e…  -> commit
git rev-parse 9bdfe0e^{tree} -> 351cd83ffe0bdaeec527d3dbb512e63070ccd19e
git rev-parse refs/tags/audit-candidate/phase6-current-state-20260725^{commit} -> 9bdfe0e…
git ls-remote --tags origin -> 9bdfe0e… refs/tags/audit-candidate/phase6-current-state-20260725
```

三点一致を local で確認し、remote 側にも同 tag が同一 commit で存在することを read-only の
`git ls-remote` で確認しました（network 使用はこの1回のみ、送信内容は remote URL のみ）。
proof commit `9bdfe0e` は parent `14f138a` を持ちますが **HEAD の祖先ではなく**、到達性は
当該 tag のみに依存します（`git merge-base --is-ancestor 9bdfe0e HEAD` → no）。

## 2. Construction verification（独立再実行、observed）

| 検査 | 施工側記録 | 独立実行結果 |
|---|---|---|
| `scripts/doctor.sh` | PASS | `SUMMARY failures=0 warnings=1 network=0`（warn は worktree に local 変更あり＝staged candidate） |
| focused `tests/test_repository_snapshot.py` | 20 passed | **20 passed** |
| 全 non-local | 425 passed, 1 deselected | **425 passed, 1 deselected** |
| `compileall aleph scripts` | PASS | PASS |
| `git diff --cached --check` | PASS | PASS |
| `audit_repository_snapshot.py --format report` | — | 実行成功 |

現候補の投影（observed）:

```text
status=PASS  currency=NEEDS_AUDIT  tree_binding.state=INDEX
target_changelog=0.7.20-28  changelog_latest=0.7.20-29
unexpected_paths=[PLAN.md, aleph/cli.py, aleph/core/repository_snapshot.py,
                  designs/formal-audit-runbook.md, designs/phase6-audit-tree-binding.md,
                  scripts/audit_repository_snapshot.py, tests/test_repository_snapshot.py]
```

依頼の期待値 `status=PASS, currency=NEEDS_AUDIT, tree_binding.state=INDEX` と一致します。
README 日英 marker は `readme_status_markdown()` の出力と完全一致（ja/en とも True）、CLI は
`currency=NEEDS_AUDIT, tree=INDEX` を表示します。

## 3. 独立故障注入（observed）

`/tmp` に29シナリオを構築し、うち27が期待どおり。残り2件の内訳は「私の期待記述の誤り1件」
「実装欠陥1件」です。

**契約充足を確認したもの**

| # | 注入 | 結果 |
|---|---|---|
| S1 | clean HEAD、差分が closure 内のみ | `CURRENT / HEAD` ✓ |
| S2 | 同差分を全 stage、unstaged/untracked なし | `CURRENT / INDEX` ✓ |
| S3a | code の unstaged 変更 | `NEEDS_AUDIT / DIRTY` ✓ |
| S3b | untracked file | `NEEDS_AUDIT / DIRTY` ✓ |
| S3c | commit 済み allowlist 外差分 | `NEEDS_AUDIT`, `unexpected=['aleph/impl.py']` ✓ |
| S4a–e | tree 不在／commit 不在／commit-tree 不一致／ref 不在／ref-commit 不一致 | 全て `UNKNOWN / UNAVAILABLE` ✓ |
| S5 ×9 | closure に `aleph/…`, `tests/…`, 契約design(`phase6-audit-tree-binding.md`), `formal-audit-runbook.md`, 他report, 絶対path, `..`, 重複, `PLAN.md` | 全て ledger invalid → `status=UNKNOWN, currency=UNKNOWN` ✓ |
| S6 ×5 | ref に `refs/tags/v1.0`, `refs/heads/main`, `refs/tags/audit-candidate/../../heads/main`, bare名, prefix混同 `audit-candidateX` | 全て ledger invalid → `UNKNOWN` ✓ |
| S7 | Git三点一致だが target CHANGELOG 不一致 | `NEEDS_AUDIT` ✓（S7 の "mismatch" 表示は私の期待文字列に `state=UNAVAILABLE` と書いた誤りで、実装は正しく `state=HEAD` を出しつつ `NEEDS_AUDIT` に倒す） |
| S8a | Git repository でない root | `UNKNOWN / UNAVAILABLE`、works/budget/design_state の read surface 維持 ✓ |
| S8b | PATH から git 消失 | `UNKNOWN / UNAVAILABLE` ✓ |
| S8d | `git diff` が returncode≠0 で失敗 | `UNKNOWN / UNAVAILABLE` ✓ |
| P1 | code file を allowlist path へ rename して commit | `NEEDS_AUDIT`, `unexpected=['aleph/impl.py']` ✓（`--name-only` が source/destination 両方を出すため rename 抜けなし） |
| P2 | code file の staged 削除のみ | `NEEDS_AUDIT / INDEX`, `unexpected=['aleph/impl.py']` ✓ |

**契約を満たさなかったもの → 下記 P2 finding**

| # | 注入 | 期待 | 実測 |
|---|---|---|---|
| S8c | `git diff` probe だけが 5 秒超ハングする shim | `UNKNOWN / UNAVAILABLE` | **`subprocess.TimeoutExpired` が伝播し snapshot 全体が例外終了** |

## 4. Findings

### P2-1（blocking）`git diff` probe の timeout が guard 外で、Git command 失敗時に read surface を失う

**observed.** [aleph/core/repository_snapshot.py:458](aleph/core/repository_snapshot.py:458) の
`run()` は全 probe に `timeout=5` を課しますが、`try/except (OSError, SubprocessError)` は
[:467–487](aleph/core/repository_snapshot.py:467) の4 probe（`rev-parse HEAD^{tree}` /
`status` / `cat-file -e` / `rev-parse …^{tree}` / `rev-parse …^{commit}`）だけを覆っています。
最後の diff probe は guard の外にあります。

- [aleph/core/repository_snapshot.py:534](aleph/core/repository_snapshot.py:534) `diff = run("diff", "--cached", "--name-only", candidate_tree, "--")`
- [aleph/core/repository_snapshot.py:537](aleph/core/repository_snapshot.py:537) `diff = run("diff", "--name-only", candidate_tree, head_tree, "--")`

このため `git diff` が 5 秒で打ち切られると `TimeoutExpired` が
[:584](aleph/core/repository_snapshot.py:584) → [:145](aleph/core/repository_snapshot.py:145)
を経て `RepositoryReader.snapshot()` の外へ抜けます。実測 traceback:

```text
File ".../repository_snapshot.py", line 145, in snapshot
File ".../repository_snapshot.py", line 584, in _assurance
File ".../repository_snapshot.py", line 537, in _tree_binding
subprocess.TimeoutExpired: Command '['git', '-C', ..., 'diff', '--name-only', ...]'
    timed out after 5 seconds
```

**契約違反の所在.** 受入契約8「Git 利用不能は UNKNOWN」、依頼の独立注入項目8「Git command
失敗で read surface を失わず UNKNOWN」、および `designs/phase6-audit-tree-binding.md:58–59`
「shell は使わず、5秒 timeout とする。…例外で read surface を失わず `UNKNOWN` へ倒す」。
returncode 失敗（S8d）は正しく `UNAVAILABLE` へ倒れるのに、同じ「Git command 失敗」の
timeout 変種だけが素通りします。同一関数内で guard 方針が非一貫です。

**影響.** currency が誤って `CURRENT` になる soundness 破綻ではなく、可用性の破綻です。
ただし壊れるのは currency だけでなく `snapshot()` 全体であり、`aleph status`
([aleph/cli.py:313](aleph/cli.py:313))、`scripts/audit_repository_snapshot.py`、README marker
生成が同時に落ちます。R-2 が守ろうとしている「現在像の read surface」そのものです。

**最小修正の形（施工側判断）.** 534/537 の 2 呼び出しを既存 try へ入れる、または `run()` 内で
`TimeoutExpired`/`OSError` を捕捉して returncode≠0 相当の結果へ正規化する。RED テストは
S8c と同形の PATH shim で書けます。

### P3-1（residual）closure allowlist が canon 参照文書 `designs/next-designer-execution-plan.md` を含む

[aleph/core/repository_snapshot.py:288–295](aleph/core/repository_snapshot.py:288) の fixed 集合と
`designs/phase6-audit-tree-binding.md:41` が同文書を機械的 closure 面として許可しています。一方
同 design の `:6` は同文書 §6.1/§6.3 を **正典** として引用しており、本監査依頼の canon にも
含まれます。allowlist は path 粒度なので「状態段落の更新」と「契約段落の改変」を区別できず、
PASS 後に canon 相当の記述が変わっても `currency=CURRENT` が保たれ得ます。design §3 は
「allowlist 内でも runbook の意味制約は残る」と明記しており、人手規律で埋める設計上の既知の
限界として残置扱いにします。同じ性質は `PLAN_CHANGELOG.md` / `README` / `PROGRESS.md` にも
内在します。

### P3-2（residual）proof commit の到達性が lightweight tag 単独に依存する

`git cat-file -t refs/tags/audit-candidate/phase6-current-state-20260725` は `commit` を返し、
lightweight tag です。`9bdfe0e` は HEAD/origin/main の祖先ではないため、この tag を失うと
object は GC 対象になります。`designs/formal-audit-runbook.md:78` は「tag を branch とともに
push する」とだけ述べ、annotated 化や明示 refspec を要求していません。lightweight tag は
`git push --follow-tags` では push されないため、運用手順が durability の主張よりやや弱い状態
です。今回に限れば origin に存在することを実測確認済みです。

### P3-3（observation）ledger 自体が closure allowlist 内にある自己言及性

`config/formal-audits.json` は allowlist に含まれ、entry 自身の report path も許容されます
（[:300](aleph/core/repository_snapshot.py:300)）。したがって「新 PASS report ＋ 新 entry ＋
現在 tree の proof commit/tag」を揃えれば currency は再び `CURRENT` になります。これは正規の
closure 手順と同型であり、R-2 は tree の実在性を束縛するもので ledger 記載内容の真正性までは
束縛しません。R-2 の欠陥ではなく、束縛範囲の明示として記録します。

### P3-4（observation）legacy entry は構造上 `CURRENT` になり得ない

ledger entry 1–3 は `candidate_commit`/`candidate_ref`/`closure_paths` を持ちません。
`commit is None` は ledger admission では有効ですが
（[:381–385](aleph/core/repository_snapshot.py:381)）、`_tree_binding` では
`candidate_commit_exists=False` となり `_assurance` で `UNKNOWN` に倒れます
（[:592](aleph/core/repository_snapshot.py:592)）。`designs/phase6-audit-tree-binding.md:88`
の非目標「legacy audit 全件への commit/ref 遡及作成」と整合し、保守的側へ倒れています。

## 5. Inference / uncertainty の分離

- **observed**: §1–§3 の全数値、traceback、`git ls-remote` 出力、README marker 一致、
  29＋3 シナリオの実測結果。
- **inference**: P2-1 の実運用到達性（大規模 tree、index.lock 競合、9p/NFS 越しアクセス、
  高負荷時に `git diff` が 5 秒を超え得る）は推論であり、本 repository での自然発生は未観測。
  故障は shim で強制注入して再現しました。
- **uncertainty**: (a) `git status` が `.gitignore` および `assume-unchanged`/`skip-worktree`
  を尊重するため、それらで隠された作業ツリー差分は DIRTY 判定を回避し得ます（今回の候補で
  該当は未検出、`git ls-files -v` 相当の検査は未実施）。(b) `self.root` が repository root で
  ない場合の path 基準ずれは保守的側（`unexpected` 増加）に倒れることを確認しましたが、
  網羅検証はしていません。(c) remote 確認は監査時点の 1 回のみで、以後の tag 保持は保証外。

## 6. tests green と formal verdict の分離

focused 20 passed、全 non-local 425 passed、compileall・diff check green は **施工品質の証拠**
であり、formal verdict ではありません。既存テスト群は S8c 型（probe timeout）の故障注入を
含んでおらず、緑であることは P2-1 の不在を意味しません。逆に P2-1 は既存テストを一切壊さずに
成立します。

## 7. R-2 の判定

**未閉鎖。**

受入契約 1–7、9、10 は独立注入で充足を確認しました（§3）。契約 8「Git 利用不能は UNKNOWN、
古い PASS へ fallback しない」は、returncode 失敗経路では充足しますが、timeout 経路で
`snapshot()` 全体が例外終了し read surface を失うため未充足です。R-2 の中心命題である
「currency を candidate tree 実体へ束縛する」こと自体は正しく実装されており、欠陥は
その probe の可用性 guard に限定されます。P2-1 を修正し focused RED → GREEN と全 non-local
再実行を経れば、同 scope の再監査で閉鎖可能と判断します。

## 8. public 面への影響

staged 13 file は `works/`、`state/`、`config/budgets.yaml`、作品生成経路のいずれも変更して
いません。`aleph/cli.py` の変更は status 行の表示 1 行のみです。予算・期限・公開作品数は
不変（api 69.628952/71.0 USD、deadline UPCOMING 2026-08-01、公開 5 作）。契約 10 は充足。

VERDICT: FAIL
