## ALEPH Phase 6 current-state — P1/P2 focused再監査（独立・read-only）

---

## 0. Candidate identity と不変性

| 項目 | 開始時 | 終了時 |
|---|---|---|
| `git rev-parse HEAD` | `14f138a6df36e43a57c7bada8e4f6daa4e289d55` | 同一 |
| `git rev-parse --abbrev-ref HEAD` | `main` | 同一 |
| `git write-tree` | `351cd83ffe0bdaeec527d3dbb512e63070ccd19e` | 同一 |
| `git diff --name-only` | 空 | 空 |
| untracked | なし | なし |
| staged files | 14件（依頼書の期待と一致） | 14件 |

依頼書の repair tree と一致。**候補は一切変更していない。** 書き込みは `/tmp` のみ（`/tmp/aleph-reaudit-probe`、`/tmp/aleph-reaudit-probe2*`、uv cache `/tmp/aleph-uv-cache-reaudit`）。新作生成・local inference・有償API call・provider cost照合は実行していない。

初回FAIL artifact `reports/PHASE6_CURRENT_STATE_AUDIT_20260724_FAIL.md` は**保持**を確認（index blob `59567ac8…`、最終非空行 `VERDICT: FAIL`、231行）。過去のFAIL 2件（`PHASE5B_NORMAL_RUN_CLOSING_AUDIT_20260723_FAIL.md`、`PHASE6_CLOSING_READER_IDENTITY_AUDIT_20260724_FAIL.md`）も削除・改変なし。

---

## 1. Observed evidence — 施工記録の独立再現

| コマンド | 施工記録 | 独立実行 |
|---|---|---|
| `bash scripts/doctor.sh` | — | `SUMMARY failures=0 warnings=1`（warnは`git worktree: has local changes`＝候補staged自体） |
| `pytest -q tests/test_repository_snapshot.py` | 16 passed | **16 passed** in 6.76s |
| `pytest -q -m 'not local'` | 421 passed, 1 deselected | **421 passed, 1 deselected** in 3.93s |
| `python -m compileall -q aleph scripts` | PASS | rc=0 |
| `git diff --cached --check` | PASS | rc=0 |
| `audit_repository_snapshot.py --format report` | — | `FAIL` / `path: reports/PHASE6_CURRENT_STATE_AUDIT_20260724_FAIL.md` / `currency: NEEDS_AUDIT` / `warnings: 24` |
| `python -m aleph.cli status` | — | `latest recorded formal audit: FAIL (currency=NEEDS_AUDIT, path=reports/PHASE6_CURRENT_STATE_AUDIT_20260724_FAIL.md)` |

**施工側の申告はすべて一致した。** 依頼書の期待値（`status=FAIL` / 当該path / `currency=NEEDS_AUDIT` / 26 artifacts）も4面すべてで一致。

**tests green と formal verdict は別物である。** 上記は「testsが緑」の証拠に過ぎない。以下は `/tmp` 複製への故障注入の結果であり、これが verdict の根拠である。

---

## 2. 初回 F-1〜F-7 の一件ごとの判定

### F-1 — 列挙順が「最新」を意味しない（P1・blocking）→ **閉鎖**

`config/formal-audits.json` を明示ledgerとし、`_assurance` は `ledger=="registered"` の entry を `sequence` で整列して `[-1]` を採る（`aleph/core/repository_snapshot.py:396-400`）。列挙順は在庫化にしか使われない。

初回FAILで名指しした probe A/B/C を**同じ形で実corpus複製へ再注入**した（probe2）:

| 初回probe | 初回挙動 | 再監査での挙動 |
|---|---|---|
| (A) `reports/CODEX_AUDIT_20260801_000000.md` にFAILを追加（辞書順で前） | `PASS`（旧artifactのまま） | 未登録 → **`UNKNOWN` / `currency=UNKNOWN`**＋`formal audit artifact is unregistered:` warning |
| (A2) 同artifactを sequence 4 で正規登録 | — | **`FAIL` / 当該path / `CURRENT`**（辞書順で前でも選ばれる） |
| (B) `audits/M9_audit.md` にFAILを追加 | `PASS`（`audits/` は構造的に「最新」になれない） | 未登録 → **`UNKNOWN`**／登録すれば **`FAIL` / `audits/M9_audit.md`** |
| (C) `TRANSITION_HISTORY_AUDIT_20260718.md` に `VERDICT: PASS` を補う | 「最新」が2026-07-18へ逆行 | `legacy_unordered` のため latest判定に**関与せず**、`FAIL`のまま（`repository_snapshot.py:319-324`) |

依頼書の必須注入1（辞書順で後ろの旧PASS `ZZZ_OLD_AUDIT.md` と辞書順で前の新FAIL `AAA_NEW_AUDIT.md` を **sequence逆順で登録**）→ `status=FAIL` / `path=reports/AAA_NEW_AUDIT.md`。**閉鎖。**

必須注入2の4形態はすべて古いPASSへ fallback せず `UNKNOWN`:

| 注入 | 結果 |
|---|---|
| 新しい未登録FAIL | `UNKNOWN`／`unregistered` warning |
| ledgerにあるが欠落した最新FAIL | `UNKNOWN`／`entry is invalid` warning |
| duplicate sequence（両順序で試験） | `UNKNOWN`／`entry is invalid` warning |
| 壊れた `supersedes` | `UNKNOWN`／`entry is invalid` warning |
| ledger欠落 / 不正JSON / `version!=1` | すべて `UNKNOWN`＋固有warning |
| legacy artifactの実体欠落 | `UNKNOWN`／`legacy artifact is missing` warning |

fail-closed が全方向で成立している（`repository_snapshot.py:298-388`）。

### F-2 — currency が散文の語彙一致だけで決まる（P1・blocking）→ **閉鎖**

currency は `latest["target_changelog"] == design_state["changelog_latest"]` のみで決まる（`repository_snapshot.py:410-417`）。散文照合の正規表現は削除済み。

依頼書の必須注入4・5:

| 注入 | 結果 |
|---|---|
| artifact 0件（ledgerなし／空ledger）＋見出し`監査PASS済み` | `UNKNOWN` / `currency=UNKNOWN`（初回は `CURRENT` を返していた） |
| CHANGELOG欠落 | `currency=UNKNOWN` |
| target不一致（entry 0.8.0 / CHANGELOG 0.8.1） | `currency=NEEDS_AUDIT` |
| 見出し`0.8.0の監査PASSを撤回しFAILへ差し戻し` | `NEEDS_AUDIT` |
| 見出し`監査でPASSしなかった項目の暫定施工` | `NEEDS_AUDIT` |
| 見出し`監査PASS済み設計の再構成・独立監査待ち` | `NEEDS_AUDIT` |
| 見出し`audit PASS prerequisite recorded; not yet audited` | `NEEDS_AUDIT` |

見出しに何を書いても currency は動かない。**閉鎖。** 残存する狭い穴は R-2（後述、P2）。

### F-3 — 区切りなし見出しで版番号が壊れる → **閉鎖**

`repository_snapshot.py:439-445` は版パターンを `\d+(?:\.\d+)*(?:-\d+)?` に汎化し、date括弧とtitleを独立の optional group にした。必須注入6を実測:

```
## 0.7.20-27 (2026-07-25)                   -> latest='0.7.20-27' change=None      stale=0
## 0.7.20-27 (2026-07-25) — title here      -> latest='0.7.20-27' change='title here'
## 0.8.0                                    -> latest='0.8.0'     change=None
## 1.0.0-3 (2026-09-01) - ascii dash title  -> latest='1.0.0-3'   change='ascii dash title'
```

初回の偽版 `0.7.20` と偽 stale warning は再現しない。

### F-4 — `0.7` 固定で旧entryを「最新」に拾う → **閉鎖**

```
## 0.8.0 (2026-08-10) — 未監査の大改訂
## 0.7.20-26 (2026-07-24) — 再監査PASS      -> latest='0.8.0' change='未監査の大改訂'
```

0.8系を正しく読み、下方の「再監査PASS」文言を継承しない。加えて F-2 の修繕により、仮に版を拾い違えても currency は `NEEDS_AUDIT` 側へ倒れる（二重防御）。

### F-5 — assurance provenance が currency の実出所を隠す → **閉鎖**

`repository_snapshot.py:154-159` が `config/formal-audits.json`、`audits/`、`reports/*AUDIT*.md`、`PLAN_CHANGELOG.md` を列挙し、`_assurance` の実入力（ledger＋artifact verdict＋`design_state.changelog_latest`）を網羅する。残存は R-5（`formal_audits` 側、P3）。

### F-6 — 2026-08-01のtest RED が未宣言 → **閉鎖**

`PLAN_CHANGELOG.md` 0.7.20-28 に明記された（「README markerの期限状態は日付依存であり、2026-08-01に整合testが意図的に赤くなる。これは公開上限999を黙って継続させない設計review gateである…自動変更しない」）。`PROGRESS.md` にも同旨。値は自動変更されない（`_deadlines` は読み取りのみ、`repository_snapshot.py:487-499`）。**意図的gateとして正典化された**ため、初回の指摘（宣言がない）は解消。

### F-7 — verdict抽出が非終端の引用を拾う → **閉鎖**

`_terminal_verdict`（`repository_snapshot.py:272-278`）は最終非空行への `re.fullmatch` のみ。必須注入3を実測:

| 記法 | 結果 |
|---|---|
| 本文中に`VERDICT: PASS`、末尾は`VERDICT: FAIL` | **FAIL**（本文の引用を拾わない） |
| 末尾`VERDICT: FAIL`の後に付録`verdict: PASS` | **UNKNOWN**（初回は`PASS`だった） |
| `**判定**: **PASS**`（太字日本語） | **UNKNOWN**＋`no terminal verdict` warning |
| `判定: PASS` | **UNKNOWN**（runbookどおり厳格化） |
| `> VERDICT: PASS`（引用） | **UNKNOWN** |
| `VERDICT PASS`（コロンなし） | **UNKNOWN** |
| `VERDICT: PASS (see appendix)` | **UNKNOWN** |

`designs/formal-audit-runbook.md` にも規約が明文化された（「The report's final non-empty line must be exactly `VERDICT: PASS` or `VERDICT: FAIL`. Prose, quoted verdicts, bold Japanese labels, filenames, and directory order are not machine verdicts.」）。曖昧化はすべて `UNKNOWN` へ倒れ、登録済みartifactが `UNKNOWN` なら ledger 全体が無効化される（`repository_snapshot.py:380-382`）。

### 初回P3（F-8〜F-12）

| # | 判定 | 根拠 |
|---|---|---|
| F-8 poetics版の再実装 | **閉鎖** | `repository_snapshot.py:476-478` が正典 `aleph.meta.poetics.current_version` を呼ぶ |
| F-9 poetics欠落で黙って v0 | **契約範囲で閉鎖** | dir欠落 → `UNKNOWN`＋warning、README `詩学 UNKNOWN。`／malformed行 → `UNKNOWN`＋warning。残存は R-8（P3） |
| F-10 `999.0`/`"999"` で deadline面が消える | **閉鎖**（前半） | `999.0`/`"999"`/`True` すべて warning 発火・deadline非表示。残存は R-6（P3）と、期限日コード直書き（既存挙動、未変更） |
| F-11 CLI/report に artifact path なし | **閉鎖** | `aleph/cli.py:313-316`、`scripts/audit_repository_snapshot.py:25`。実測で両面に path 出力 |
| F-12 `to_dict()` の参照漏れ | **部分閉鎖** | `assurance`/`design_state` は `deepcopy`（`:37-38`）。`budget` は依然参照（R-4、P3） |

**F-1〜F-7 は7件すべて閉鎖。**

---

## 3. 残存findings（新規）

### P0 / P1

なし。**false PASS / false CURRENT に到達する経路を、ledgerの内容を偽らずに構成できなかった。**

### P2

**R-1. `supersedes` の参照検証がJSON配列の記載順に依存し、sequence降順で書かれた正当なledgerを丸ごと `UNKNOWN` にする**

`repository_snapshot.py:359-362` は `supersedes not in registered_paths` を不正とするが、`registered_paths` には**その時点までに走査済みの entry** しか入らない。依頼書の必須注入1と同じ「sequence逆順での登録」に `supersedes` を付けると:

```
[P-1 reverse-order list, supersedes=True]
  status=UNKNOWN path=None currency=UNKNOWN
  warn: formal audit ledger entry is invalid: 'reports/AAA_NEW_AUDIT.md'
```

誤りの向きは fail-closed（偽PASSにはならない）。ただし `designs/formal-audit-runbook.md` は entries の**記載順**に関する要求を一切書いていないので、runbookどおりに書いた正しいledgerが理由不明の `UNKNOWN` を出しうる。`registered_paths` を先に全走査して集めるか、runbookに「entriesはsequence昇順で記載する」と明記すべき。

**R-2. currency は散文の版番号に束縛され、記録済み `candidate_tree` は検証に一度も使われない**

`candidate_tree` は40桁hexの形式検査のみを受け（`repository_snapshot.py:350-351`）、実tree・実commitと照合されない。probe P-8:

```
ledger entry: target_changelog=0.8.0, candidate_tree="000…0"（存在しないtree）
→ status=PASS  currency=CURRENT
```

しかも改訂されたrunbook §5 は closure時に「keep the audited repair's `target_changelog` number unchanged」「update the existing target entry in `PLAN_CHANGELOG.md` … without creating a new design version」と定める。すなわち **PASS登録後、CHANGELOG番号を上げないコード変更は `status=PASS` / `currency=CURRENT` を維持する。**

これは依頼書のrepair contract F-1/F-2項5（「最新登録entryの`target_changelog`と実際の最新CHANGELOG番号が一致するときだけ`CURRENT`」）を**文字どおり満たしている**ので契約違反ではない。しかし初回F-2の本質（「監査していない状態をCURRENTと言わない」）は、番号を上げない限り成立しない。ledgerは既に検証可能な tree hash を持っているのだから、`git rev-parse`（またはsnapshotが git を触らない方針なら `state/` へ記録した tree）との照合を1本入れれば `CURRENT` を実物に束縛できる。**次サイクルの最優先候補。**

### P3

- **R-3.** `_terminal_verdict` の `re.fullmatch(..., re.I)`（`repository_snapshot.py:277`）により、最終行 `verdict: pass` が `PASS` として確定する（実測）。runbookは「exactly `VERDICT: PASS`」と定めているので、実装の許容がdocより広い。どちらかに揃えるべき。
- **R-4.** `to_dict()` は `budget` を参照のまま返す（`repository_snapshot.py:33`）。probeで `payload["budget"]["__probe__"]=1` が `snapshot.budget` に伝播することを確認。`budget` は `ledgers`/`ledger_status`/`work_spent` の入れ子dictを持つので、F-12と同種の不変性破れが残っている。
- **R-5.** `provenance["formal_audits"]`（`repository_snapshot.py:153`）は `audits/`, `reports/*AUDIT*.md` のみ。各artifact entryは `ledger`/`sequence`/`target_changelog`/`candidate_tree` を ledger から得ているので、`config/formal-audits.json` を挙げるべき。F-5と同じ honesty-of-provenance の類型。
- **R-6.** `publish.max_per_month` が **欠落**しているとき（malformedではなく不在）、deadline面が warning なしで消える（probe: `cap=None → deadlines=0, warning=False`）。malformedは閉鎖済み。
- **R-7.** `changelog_latest` は `re.search` の**最初の一致**＝ファイル先頭側の見出し。「新しい順」という慣行はrunbook/CHANGELOGに明文化されていない。coded fence 内や引用に `## 0.9.0 …` が入れば拾う。初回から未変更の挙動であり回帰ではない。
- **R-8.** `poetics/` は在るが `history.jsonl` が無い場合、`詩学 v0` を warning なしで表示する（probe P-7c）。正典 `current_version` のdocstringが「history.jsonl が空 or 無い = 第0版」と定めているため正典準拠だが、初回F-9の原文の懸念はこの狭い形で残る。
- **R-9.** 同一pathが `legacy_unordered` と `entries` の両方にあると、警告なしで registered に昇格し latest になりうる。probe D: 2026-07-24の旧PASS `reports/PHASE5C_P2_1_REAUDIT_20260724.md` を sequence 99 / target `0.7.20-28` で追記すると `PASS` / `CURRENT` を表示する。これは ledger 作者の誤記であり信頼モデルの内側だが、ledgerが他の矛盾（未登録・欠落・重複sequence）は検出するのに、この矛盾だけ黙る。

---

## 4. tests green と formal verdict の分離

- **tests green（再現済み）**: doctor.sh failures=0 / 16 passed / 421 passed, 1 deselected / compileall rc=0 / `git diff --cached --check` rc=0。すべて施工申告と一致。
- **formal verdict の根拠は上記ではない**。根拠は §2 の故障注入結果である。追加された9本のtestは実挙動を固定しているが、tautologicalではないことを独立に確認した（同じ契約を、testが触れていない形—duplicate sequence、legacy欠落、ledger version不正、reverse-order登録、太字日本語、blockquote、実corpus 26件複製—で再注入し、いずれも fail-closed だった）。
- なお本候補は `snapshot.assurance["tests"]["status"]` を依然 `NOT_RECORDED` と正直に返す。test結果の永続証拠は未正典化のままで、これは初回から変わらず正しい。

---

## 5. Inference / Uncertainty

**Inference（実測からの推論、断定ではない）**

- R-2 の「PASS登録後にCHANGELOG番号を上げない変更が `CURRENT` を維持する」は、runbook §5 の新しい closure 手順文と `_assurance` の実装から導いた推論であり、実際にPASSを登録して確かめてはいない（そのためには候補への書き込みが必要）。currency の計算自体は probe P-8 で実測済み。
- R-1 が実運用で発火するかは、今後 ledger を descending 順で書くかに依存する。現ledgerは昇順で書かれており、現状は発火しない。

**Uncertainty（本監査で確定させていない）**

- ledger の `sequence` は単調性を作者が保証する前提であり、単調でないledger（新FAILに低いsequenceを付ける等）は検出できない。これは明示ledger方式の設計上の受容リスクであり、契約違反ではないと解釈した。
- `state/dashboard.html` の end-to-end 生成は repository 書き込み禁止のため未実行。`build_dashboard.py` は本修繕diffに含まれず、初回監査で契約7充足を確認済み。
- 既存24件の snapshot warnings（w0001–w0009 の replay 不一致等）は本候補のscope外として内容評価していない。件数が初回と同じ24であること、ledger起因のwarningが0件であることのみ確認した。
- ledger の3 entry の `candidate_tree`（`14772732…`、`b93a518c…`、`39da78c8…`）はいずれも実在する tree object であることを `git cat-file -t` で確認した。ただし各 entry と artifact 本文の対応内容までは突き合わせていない（entry 3 のみ、初回FAIL報告書の記載treeと一致することを確認）。

---

## 6. 結論

初回の blocking 2件は、推測（ディレクトリ順・ファイル名辞書順・見出しの語彙）を捨てて明示 ledger に置き換えるという、**症状ではなく原因に対応した修繕**で閉鎖された。初回で私が名指しした probe A/B/C を実corpus複製へそのまま再注入しても、旧PASSへの fallback は一度も起きず、すべて `UNKNOWN` か正しい新FAILを返す。currency は見出しに何を書いても動かない。P2 の F-3〜F-7 も、それぞれ実測で挙動が反転していることを確認した。初回FAIL artifact は保持され、ledger に事実として登録されている。

残る R-1（fail-closedな順序依存）と R-2（treeではなく版番号への束縛）は記録に値するが、いずれも依頼書の repair contract に違反しておらず、ledger の内容を偽らない限り false PASS / false CURRENT を生まない。P3 7件も同様に非阻害である。

VERDICT: PASS
