# ALEPH Phase 6 R-1 supersedes order independence — 独立形式監査報告

## 1. Candidate identity（実測 / 開始=終了で不変）

| 項目 | 期待 | 実測 |
|---|---|---|
| branch | `codex/phase6-r1-supersedes-order` | 一致 |
| HEAD | `d9f320e…4bd3f7` | 一致 |
| staged tree (`write-tree`) | `a6e9a2c…08a08` | 一致 |
| staged files | 10 | 10 |
| unstaged / untracked | 0 / 0 | 0 / 0 |
| `git diff --cached --check` / `git diff --check` | clean | exit 0 / exit 0 |

監査中に候補は変化していません。故障注入はすべて `/tmp/r1_fixtures` 配下で実施し、リポジトリは read-only を維持しました。

## 2. Observed evidence（一次情報）

- **doctor**: `SUMMARY failures=0 warnings=1 network=0`（warnは `git worktree: has local changes`＝staged候補由来、宣言通り）
- **focused**: `24 passed`（[tests/test_repository_snapshot.py](tests/test_repository_snapshot.py)）
- **all non-local**: `429 passed, 1 deselected`
- **compileall**: PASS
- **projection**（現リポジトリ）: `latest recorded formal audit=PASS` / `path=reports/PHASE6_AUDIT_TREE_BINDING_P2_REAUDIT_20260725.md` / `currency=NEEDS_AUDIT` / `tree state=INDEX`
- **README一致テスト**: `test_checked_in_readme_snapshot_sections_match_current_repository` = 1 passed。日本語 `README.md`／英語 `README.en.md` の `repository-snapshot` マーカーが `readme_status_markdown()` 出力と厳密一致。render 内 currency=`NEEDS_AUDIT`。

すべて構築時の宣言値と一致。

## 3. 中心差分の分析（[aleph/core/repository_snapshot.py:353-424](aleph/core/repository_snapshot.py)）

修繕は2箇所のみ:

1. 全entry処理の**前**に `declared_sequences: path→sequence` を収集（`isinstance(path,str) and type(sequence) is int` を満たすもののみ。`bool` は `type() is int` で除外）。
2. `supersedes` 検証を「`supersedes not in registered_paths`（走査順依存）」から「`superseded_sequence is not None and superseded_sequence < sequence`（sequence権威順）」へ置換。`type(sequence) is not int` を先に短絡判定し、非intでの `>=` 比較による TypeError を回避。

権威順序の維持は既存の [`_assurance`](aleph/core/repository_snapshot.py:573)（`registered` を `sequence` でソートし `[-1]` を latest 選定）が担保しており、JSON配列順は latest 選定・supersedes 検証のどちらにも影響しなくなりました（契約1・3）。

## 4. RED→GREEN と独立故障注入（`/tmp` harness、旧実装 vs 候補）

| # | ケース | 旧実装 | 候補 | 判定 |
|---|---|---|---|---|
| 1 | reverse-order＋正当supersedes | **UNKNOWN**（RED再現） | — | ✓ RED確認 |
| 2 | 同ledger asc/desc配列 | — | PASS/PASS 一致・latest=NEW | ✓ 契約3 |
| 3 | 3連鎖lineage 全6配列順 | — | 全て `(PASS, C_AUDIT)` | ✓ 順序不変 |
| 4a-f | missing/self/same/future/2-cycle/3-cycle | — | 全て UNKNOWN＋`entry is invalid` | ✓ 契約2,4 fail-closed |
| 5a | 参照先が path/int-seqのみ有効・tree不正 | — | **UNKNOWN**（false PASSなし） | ✓ 核心要件 |
| 5b | duplicate path | — | UNKNOWN | ✓ |
| 5c | 非整数 sequence 参照先 | — | UNKNOWN | ✓ |
| 5d | `bool` sequence | — | UNKNOWN | ✓ |
| 6a | supersedesなし単一PASS | — | PASS | ✓ 回帰なし |
| 6b | 最新FAIL が PASS を supersede | — | FAIL 尊重 | ✓ |
| 6c | 登録artifactに terminal verdict なし | — | UNKNOWN | ✓ fail-closed |

**核心確認（5a）**: 事前収集 `declared_sequences` は「path＋int sequence だけ揃った不正参照先」を supersedes 検証で通過させ得るが、その参照先entry自身が `valid=False` → `ledger_valid=False` を立て、`_assurance` の `not ledger_valid` が最優先で projection を **UNKNOWN** へ倒す。したがって事前収集が false PASS を生む経路は存在しない（契約4・5、prompt末尾の懸念を満たす）。

2-cycle は strict `superseded_sequence < sequence` の全順序性により少なくとも1 entryが必ず invalid となり、ledger全体が UNKNOWN 化する形で拒否される（数学的にサイクル成立不能）。

## 5. Findings

- **P0 / P1 / P2 / P3: なし。**

diff は宣言スコープ（`repository_snapshot.py` の supersedes 検証＋テスト＋設計/README/changelog記録）に限定され、works・budget・deadlines・生成経路への変更なし（契約6）。既存の duplicate/artifact/verdict/tree-binding validation は 429 passed と故障注入5b-6cで無回帰を確認（契約5）。

## 6. Inference / Uncertainty

- **Inference**: legacy_unordered path を `supersedes` に指定すると（sequence不在のため）invalid となる。契約「同じledgerに存在する厳密に小さいsequence」に整合する妥当な fail-closed 挙動と判断。
- **Uncertainty**: local-marked 1件は deselected（宣言通り、実行対象外）。新作・local inference・有償API・provider cost 照合は指示通り未実行。これらは本監査の verdict 対象外。

## 7. tests green と formal verdict の分離

429/24 passed・compileall・doctor は**施工品質の客観シグナル**であり、それ自体は formal verdict ではない。formal 妥当性は、独立故障注入（旧実装での RED 再現→候補での GREEN、および17ケースの故障注入が全て fail-closed / order-invariant を満たすこと）と、候補identityの開始=終了不変性によって別途確立した。

## R-1 を formal 完了としてよいか

**可**。修繕契約1-6を満たし、RED は再現・解消され、事前収集は false PASS 経路を作らず、既存validationに回帰なし。候補treeは監査中不変。R-3〜R-9・R-2残置P3・汎用DAG化は scope外として未着手のままで正当。

VERDICT: PASS
