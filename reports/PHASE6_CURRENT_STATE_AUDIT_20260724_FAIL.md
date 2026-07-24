# ALEPH Phase 6 current-state tracer bullet — 独立監査報告

## 0. Candidate identity と不変性

| 項目 | 開始時 | 終了時 |
|---|---|---|
| `git rev-parse HEAD` | `14f138a6df36e43a57c7bada8e4f6daa4e289d55` | 同一 |
| `git write-tree` | `39da78c8a3c942404ac2ef47378ed228381bdca8` | 同一 |
| `git diff --name-only` | 空 | 空 |
| untracked | なし | なし |
| staged files | 11件（依頼書の列挙と完全一致） | 同一 |

依頼書の期待treeと一致。監査中の書き込みは `/tmp` のみ（probe 5本、uv cache `/tmp/aleph-uv-cache-audit`）。repositoryへの書き込みなし。

---

## 1. Observed evidence — 施工記録の独立再現

WSL上で独立実行。**施工側の申告はすべて一致**。

| コマンド | 施工記録 | 独立実行 |
|---|---|---|
| `bash scripts/doctor.sh` | — | `SUMMARY failures=0 warnings=1`（warnは`git worktree: has local changes`＝候補staged自体） |
| `pytest -q tests/test_repository_snapshot.py` | 9 passed | **9 passed** in 7.19s |
| `pytest -q -m 'not local'` | 414 passed, 1 deselected | **414 passed, 1 deselected** in 3.87s |
| `compileall -q aleph scripts` | PASS | rc=0 |
| `git diff --cached --check` | PASS | rc=0 |
| `audit_repository_snapshot.py --format report` | — | `tests: NOT_RECORDED` / `latest recorded formal audit: PASS` / `currency: NEEDS_AUDIT` / `warnings: 24` |

CLI `status` 非JSON面、`--json` 面、README ja/en の派生blockも実測。README両版は生成器出力と**バイト一致**（`test_checked_in_readme_snapshot_sections_match_current_repository` が実tree照合を担保）。

**tests green と formal verdict は別物である。** 上記はすべて「testsが緑」の証拠に過ぎず、以下の故障注入で契約違反が出ている。

---

## 2. 契約ごとの判定

| # | 契約 | 判定 |
|---|---|---|
| 1 | tests証拠とformal verdictの分離、未永続化時`NOT_RECORDED` | **満たす**（ただしF-5参照） |
| 2 | retained FAILを消さず、最新の確定verdictとpathを一箇所から取得 | **不成立（F-1）** |
| 3 | 過去PASSを現候補全体のPASSと誤表示しない／false CURRENTなし | **不成立（F-2）** |
| 4 | PLAN宣言・CHANGELOG最新・poetics版の集約と不一致warning | 部分的（F-3, F-4） |
| 5 | 2026-08-01境界の`UPCOMING/EXPIRED`、自動変更なし | **満たす**（F-6, F-10は付随） |
| 6 | `resume`が`run`と同じ引数・同じ再開経路のalias | **満たす** |
| 7 | README日英・dashboard・public site・CLIの共有、二generatorの役割維持 | **満たす** |
| 8 | malformed/missing入力で虚偽PASSや例外喪失なし／列挙順の「最新」安定性 | **不成立（F-1）**、例外耐性は満たす |
| 9 | 新作・local inference・有償call・cost照合をscope外 | 遵守（実行せず） |

---

## 3. Findings

### P1

#### F-1. audit artifactの列挙順は「最新」を意味せず、より新しいFAILを隠した過去PASSを公開READMEへ表示しうる（契約2・8違反）

`aleph/core/repository_snapshot.py:256-257` は列挙順を

```python
paths = sorted((self.root / "audits").glob("*.md"))
paths += sorted((self.root / "reports").glob("*AUDIT*.md"))
```

とし、`_assurance` が `conclusive[-1]`（`repository_snapshot.py:275, 285-287`）を「最新の確定verdict」として採用する。これは**日付順ではなくディレクトリ順＋ファイル名の辞書順**である。

*現treeですでに順序と時系列が乖離している*（probe 1）:

```
20 PASS  reports/PHASE5C_P2_1_REAUDIT_20260724.md            (07-24)
21 PASS  reports/PHASE5_PREIMPLEMENTATION_DESIGN_AUDIT_20260721.md (07-21)  ← 後に列挙
24 UNKNOWN reports/TRANSITION_HISTORY_AUDIT_20260718.md       (07-18)  ← 最後に列挙
```

現在正解が出ているのは、PHASE6の2件がたまたま辞書順で末尾側に来ており、`TRANSITION_HISTORY_AUDIT_20260718.md` にVERDICT行が無い（`conclusive`から除外される）という**命名の偶然**による。

実corpusの複製に対する故障注入（probe 5、`/tmp`のみ）:

- **(A) 本repositoryに既に7件存在する `CODEX_AUDIT_*` 命名で、2026-08-01付のFAILを追加** → 表示は `status: PASS, path: reports/PHASE6_CLOSING_READER_IDENTITY_P2_REAUDIT_20260724.md` のまま。公開README行は `最新記録formal audit: PASS（…）、保存artifact: 26件` となり、**新しいFAILの存在が件数にしか現れない**。
- **(B) `audits/M9_audit.md` にFAILを追加**（milestone命名） → 同じく PASS 表示のまま。`audits/` は常に `reports/` より前に列挙されるため、`audits/` へ入れた新規verdictは構造的に「最新」になれない。
- **(C) 既存の `TRANSITION_HISTORY_AUDIT_20260718.md` にVERDICT行を補うと、「最新」が2026-07-18へ逆行する。**

契約2は「retained FAILを消さず、最新の確定verdictを取得できる」ことを要求する。FAILは `formal_audits` に残る（消えてはいない）が、**「最新」の一語が偽になる**。契約8が名指しした「audit artifactの列挙順が『最新』を安定して意味するか」への答えは No。しかも誤りの向きが false PASS であり、README・README.en・CLI・監査JSON/reportの4面すべてに同時に出る。

対応の方向: verdictを含むartifact自身に日時（もしくはfront-matter）を要求し、ファイル名やディレクトリではなく記録日時＋同日内のsupersedes関係で順序を決める。決められない場合は `UNKNOWN`/`AMBIGUOUS` を返して黙って最後の要素を採らない。

#### F-2. `currency` はCHANGELOG見出しの文字列一致のみで決まり、artifact集合と一切照合しない（契約3違反）

`repository_snapshot.py:276-282`:

```python
elif re.search(r"(?:監査|audit).*(?:PASS|合格)", latest_change, re.I):
    currency = "CURRENT"
```

判定材料は**最新CHANGELOG見出しの後半テキスト1行だけ**。以下がすべて `CURRENT` になる（probe 2 C2/C3）:

| 見出し | 実態 | 判定 |
|---|---|---|
| `0.7.20-26の監査PASSを撤回しFAILへ差し戻し` | PASS撤回 | **CURRENT** |
| `監査でPASSしなかった項目の暫定施工` | 不合格 | **CURRENT** |
| `監査PASS済み設計の再構成・独立監査待ち` | 未監査 | **CURRENT** |
| `audit PASS prerequisite recorded; implementation not yet audited` | 未監査 | **CURRENT** |

さらに **audit artifactが0件のtree** でも `{"status": "UNKNOWN", "path": None, "currency": "CURRENT"}` を返す（probe 2 C3）。「記録verdictは無いが最新である」という自己矛盾した表示で、currencyは証拠と一度も突き合わされていない。

最も重いのは仮想例ではなく**直前の実状態**である。HEAD `14f138a` のPLAN/CHANGELOGをそのまま読ませると（probe 3-3）:

```
latest_change: Phase 6 P2 focused再監査PASS
currency     : CURRENT
```

0.7.20-26 は**P2修繕候補に限定したfocused再監査**であり、tree全体の監査ではない。それが「repository全体の formal audit currency = CURRENT」を生む。これは契約3が禁じる「過去の（部分的な）PASSを現在候補全体のPASSと誤表示する」そのものである。今回の候補が `NEEDS_AUDIT` を正しく出すのは、見出しに偶然「PASS」の語が無いからにすぎない。そして本監査がPASSして次エントリに「監査PASS」を含む見出しが書かれた瞬間、同じ穴が再び開く。

対応の方向: currencyを散文の語彙照合で決めない。最新CHANGELOG番号（またはcommit）と、その番号を明示的に対象と宣言したaudit artifactの `VERDICT` を突き合わせる。artifactが0件・対象宣言が無い場合は `CURRENT` を出さない。

### P2

#### F-3. CHANGELOG見出しの区切り欠落で、存在しない版番号と偽のstale warningを生成する

`repository_snapshot.py:307-311` の

```python
r"^## (0\.7(?:\.\d+)*(?:-\d+)?)\s*(?:\([^\n]*\))?\s*(?:—|-)\s*(.+)$"
```

は、見出しが `## 0.7.20-27 (2026-07-25)`（`— 説明` なし）のとき、`-` をハイフン区切りとして消費するようbacktrackし（probe 2 C4）:

```
changelog_latest: '0.7.20'          ← 存在しない版
latest_change   : '27 (2026-07-25)'  ← 説明ではなく版番号の断片
stale           : ['PLAN.md declares 0.7.20-27 but PLAN_CHANGELOG latest is 0.7.20']
```

READMEに「changelog 0.7.20」と虚偽の版が出て、同時に**偽のstale warning**が立つ。契約4（範囲不一致をwarningにする）が逆向きに壊れる。currencyは `NEEDS_AUDIT` 側へ倒れるためfalse PASSにはならない。

#### F-4. 版体系が `0.7` を離れると、旧entryを「最新」として拾い、その監査PASS文言を継承する

同じ正規表現は `0\.7` を要求するため、`## 0.8.0 (2026-08-10) — 未監査の大改訂` は不可視。`re.search` が下方の `## 0.7.20-26 … Phase 6 P2 focused再監査PASS` に一致する（probe 3-4）:

```
changelog_latest: '0.7.20-26'   stale: []   currency: CURRENT
README: - 設計状態: changelog 0.7.20-26、詩学 v0。
```

未監査の大改訂が `CURRENT` として表示され、staleにも上がらない。F-2と合成すると沈黙のfalse CURRENTになる。

#### F-5. `provenance["assurance"]` が currency の実際の出所を隠している

`repository_snapshot.py:144` は `"assurance": ("audits/", "reports/*AUDIT*.md")` と宣言するが、`assurance.formal_audit.currency` の唯一の入力は `PLAN_CHANGELOG.md` の見出しテキストである（`repository_snapshot.py:276-282`）。この repository は provenance を honesty契約として扱っているので、実入力が宣言に含まれないのは実質的な誤記録。同じフィールドで `design_state` は正しく `PLAN_CHANGELOG.md` を挙げている。

#### F-6. README派生blockが日付依存になり、既存testが2026-08-01に赤くなる（未宣言）

候補は `deadline_ja`/`deadline_en`（`repository_snapshot.py:51-60, 73, 90`）をREADME blockへ入れた。既存の `tests/test_repository_snapshot.py:200-203` は実tree照合なので（probe 5 D）:

```
today=2026-07-24: MATCH  -> PASSES
today=2026-07-31: MATCH  -> PASSES
today=2026-08-01: MISMATCH -> FAILS
```

期限到来をtest suiteの赤で強制するのは設計上ありうる選択だが、**契約5はREADME/CLI/JSON/report/dashboard gateでの可視化しか要求していない**。CHANGELOG 0.7.20-27 にもPROGRESSにも「2026-08-01にtest suiteが赤くなる」との宣言がない。意図なら明記が必要、意図でないなら期限行をREADME blockから外すか、testを日付固定化する必要がある。

#### F-7. verdict抽出（今回load-bearingに昇格）が太字日本語形式を取りこぼし、本文末尾以外の引用を優先する

`repository_snapshot.py:265-267` の正規表現は今回のdiffで変更されていないが、本候補で初めて「最新記録formal audit」というREADME/CLI表示の根拠になった。probe 2 B:

| 記法 | 結果 |
|---|---|
| `VERDICT: FAIL` | FAIL ✓ |
| `判定: PASS` | PASS ✓ |
| `**判定**: **FAIL**` | **UNKNOWN** |
| `VERDICT PASS`（コロンなし） | UNKNOWN |
| 末尾に `VERDICT: FAIL`、その後の付録で `verdict: PASS` を引用 | **PASS** |

前者はFAIL報告書が `conclusive` から静かに脱落し、古いPASSが「最新」に残る。後者は `explicit[-1]` が本文中の引用を拾う。`designs/formal-audit-runbook.md` が「最後の行を厳密に `VERDICT: …`」と定めている限り準拠artifactでは正しく動くが、契約8の「虚偽のPASSが起きない」は非準拠artifact1件で破れる。最低限、複数の非一致verdictを検出したら `AMBIGUOUS` を返すべき。

### P3

- **F-8** `repository_snapshot.py:318-319` の poetics版算出は `aleph/meta/poetics.py:15-27` の正典helper `current_version()` を再実装している。現時点で挙動は等価だが、契約7の「独自再解釈しない」精神に反し、drift源になる。`current_version` を呼ぶべき。
- **F-9** `poetics/history.jsonl` 欠落時、READMEは warning なしで `詩学 v0` を表示する（probe 2 C6）。CHANGELOG欠落は `changelog UNKNOWN` に落ちるのに、poeticsだけ「第0版」という実在しうる値を捏造して黙る。非JSON行も1行=1版として数える（garbage 2行→v2）。
- **F-10** `_deadlines`（`repository_snapshot.py:328-330`）は `type(cap) is int and cap == 999` で発火する。`999.0` / `"999"` では deadline面が**丸ごと消え**、READMEは `期限: 記録なし。` を warning なしで表示する（probe 2 D2）。また期限日 `date(2026, 8, 1)` はコード直書きだが provenance は `PLAN_CHANGELOG.md` を出所と主張している（既存挙動）。
- **F-11** CLI `status` 非JSON面（`aleph/cli.py:312-317`）と `render_report`（`scripts/audit_repository_snapshot.py:23-25`）は artifact path を出さない。契約2の「一つのsnapshot面から取得できる」はJSON/READMEで満たされるが、監査者が最も使う2面で欠けている。
- **F-12** `to_dict()`（`repository_snapshot.py:36-37`）は `assurance` / `design_state` を参照のまま返す（他フィールドはコピー）。frozen dataclassの不変性が実質的に破れる。

---

## 4. 契約が満たされている点（確認済み）

- **契約6（resume alias）— 完全に満たす。** probe 4-1/4-2:
  - default `--index` 一致（`state/atlases/phase5c-pca64-hdbscan40-aozora-v1`）
  - `--force-audience` 一致、`--work` 必須で両方 `SystemExit 2`、未知flagで両方 `SystemExit 2`
  - 未知work: 両方 rc=1、`run: work not found: …/works/w9999`（同一 `_cmd_run` 経路、`aleph/cli.py:292-293`）
- **契約5（期限境界）— 満たす。** `2026-07-30/07-31 → UPCOMING`、`2026-08-01/08-02 → EXPIRED` ＋ warning 1件、README ja/en 両方に反映。dashboard human gate も実測で発火し、HTMLに `期限切れ … 2026-08-01 … do not mutate automatically` が入る。設定値の自動変更はコード上も存在しない。
- **契約7（面の共有）— 満たす。** README ja/en の派生blockは生成器とバイト一致、`test_checked_in_readme_snapshot_sections_match_current_repository` が実treeを照合。`build_dashboard.build()` は1回の `RepositoryReader` snapshotから works/budget/deadlines を取り、二重読みを解消（`scripts/build_dashboard.py:200-206`）。`build_public_site.py` は `iter_published` 経由で `RepositoryReader` を使い件数を独自算出しない。二generatorのdocstring（canonical vs M6 contract surface）は候補で未変更・無弱体化。
- **契約8の例外耐性 — 満たす。** CHANGELOG欠落／空／PLAN欠落／両方がディレクトリ、poetics欠落／空／garbage のいずれでも例外を出さず read surface を失わない（probe 2 C5/C6）。
- **契約1** `tests: NOT_RECORDED` は常に正直。ただしF-5の通り currency の出所宣言が不完全。
- **契約9** 新作生成・local inference・有償API call・provider cost照合は一切実行していない。

---

## 5. Inference / Uncertainty

**Inference（実測からの推論、断定ではない）**

- F-1の(A)(B)は実corpus複製への注入で再現したが、「今後 `CODEX_AUDIT_*` や `audits/` に新規verdictが書かれる」という運用前提に依存する。ただし該当命名は既に7件＋3件存在し、辞書順逆転は現treeで既に発生している（index 20/21）。
- F-2の「本監査PASS後に同じ穴が再び開く」は、CHANGELOG見出し慣行（0.7.20-26 が `…再監査PASS`）からの推論。実装上は見出し文字列次第。
- F-6の「意図的な強制関数か否か」は施工記録に記述がないため不明。testが赤くなる事実自体は実測。

**Uncertainty（本監査で確定させていない）**

- `designs/formal-audit-runbook.md` の全文は参照したが、verdict記法の許容範囲（太字日本語形式を認めるか）を規約として断定していない。F-7の重みはこの規約解釈に依存する。
- `state/dashboard.html` を実際に生成する end-to-end 実行は、repository書き込み禁止のため行っていない。gate文字列とHTML埋め込みは in-memory で確認した。
- 24件の既存 snapshot warnings（w0001–w0009 のreplay不一致等）は本候補のscope外として内容評価していない。
- local inference / 有償call / provider cost は依頼どおり未実行。

---

## 6. 結論

施工側の検証記録（9 / 33 / 414 passed、compileall、diff --check）は**すべて独立に再現した**。契約6・7、および契約5の期限境界と人間gateは実装として正しい。

しかし tests green は formal verdict ではない。本候補の中心的な約束である「監査状態を偽らずに一箇所から読める」ことについて、

- **F-1**: 「最新の確定verdict」がディレクトリ順＋ファイル名辞書順で決まり、より新しいFAILを隠した過去PASSを公開README・CLI・JSON・reportの4面へ同時に出しうる（契約2・契約8の明示要求に不成立）
- **F-2**: `currency` がCHANGELOG見出しの語彙一致のみで決まり、artifact 0件でも `CURRENT` を返す。PASS撤回見出し・不合格見出し・focused部分再監査のいずれも `CURRENT` になる（契約3に不成立、依頼書が名指しで厳格確認を求めた箇所）

の2件が残る。いずれも誤りの向きが false PASS / false CURRENT であり、この機構が防ぐために作られた失敗そのものである。修繕後の再監査を要する。

VERDICT: FAIL
