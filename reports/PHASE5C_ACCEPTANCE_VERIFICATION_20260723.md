# Phase 5C step 12 — 実データread-only受入検証と故障注入

日付: 2026-07-23
施工者検証であり、Claude Codeによる正式milestone監査のverdictではない。

## 候補と不変範囲

- baseline: `8f8bd59d470d9c8db8cd927cbbf93ed8f9293896`
- step 9 commit: `02517e76403086fd83f0478fb6ec90444b0ca18f`
- `git diff 8f8bd59d... -- works audits`は空で、既存work/auditに変更なし。
- 既存`state/atlas`は未変更。新Atlasは
  `state/atlases/phase5c-pca64-hdbscan40-aozora-v1`。
- full Atlas identity:
  `8ab3e51a4d8c64bdbb456b2dc7dbea9bdf4fe71f60888eda997203c4c59827ca`

## 実データ観測

- `AtlasIdentity.verify()` = `True`、`Atlas.load()` = PASS。
- 95,690 labels。label集合はnoise `-1`を含む5値、non-noise clusterは4。
- instrument registryは9計器、registry hashは
  `6bf77c9037a870562b2dc85975a135408e9161cbfb96f92d43c39678bd707ce4`。
- sealed fixation baselineは8 recordで、
  `fixation.poetics_lexical`と`fixation.house_style`を分離している。
- `WorkReader(works/w0009)`は既存artifactを変更せず
  `stop_path=budget/category=resource_stop/inferred=false`と読んだ。
- `works/w0007`にはmodern termination recordがなく、read-only readerは`None`を返した。
  従って「w0007型品質床」は実w0007へ遡及分類せず、登録fixtureで
  `aesthetic_failure`境界を検証した。

## 17受入条件の照合

| # | 条件 | 結果 | 主な証拠 |
|---:|---|---|---|
| 1 | 台帳 | PASS | `config/instruments.yaml`、registry completeness test |
| 2 | record provenance | PASS | step 9 baseline、step 11 runtime wiring tests |
| 3 | 非比較identity | PASS | Atlas/model/prompt/roster/epoch comparison tests |
| 4 | Atlas 1-byte fault | PASS | meta破損で`AtlasIdentityError`、identity unit faults |
| 5 | legacy read-only | PASS | legacy adapter tests、`works/audits`差分なし |
| 6 | fixation | PASS | sealed 5 fixture、8 baseline records |
| 7 | reservation durability | PASS | interleaved commitment/restart fault |
| 8 | borrowing matrix | PASS | player→held-outのみ許可、manifest注入拒否 |
| 9 | closing | PASS | player枯渇から題・公開判断・終端までのfixture |
| 10 | atomic parse | PASS | 3-slot末尾破損、前2証拠保持、aggregate拒否 |
| 11 | SHELVE分類 | PASS | 実w0009 read-only＋w0007型quality fixture |
| 12 | owner-only | PASS | owner-onlyの予約/起動/status interface不存在 |
| 13 | epoch | PASS | legacy欠落保持、cross-epoch warning |
| 14 | 回復 | PASS | reservation/call/parse/record append後の冪等再開 |
| 15 | 実額超過 | PASS | overage charge保存＋`unreconciled` |
| 16 | charge冪等性 | PASS | 同一`charge_id`のspent/行数不増 |
| 17 | 終了境界 | PASS | 未開始/`resource_interrupted`/`complete_short`分離 |

## 故障注入とtest

- Phase 5 focused:
  `test_instrument_registry.py`、全`test_phase5_*.py`、`test_design_invariants.py`
  = **82 passed**。
- 全non-local = **388 passed, 1 deselected**。
- `git diff --check` = PASS。
- Atlas artifact/build-spec不一致、reservation command collision、借用方向違反、
  jury末尾parse failure、completed overage、lost closing、measurement id collisionを
  それぞれfail closedで確認した。

## 推論

- 実データとfixtureの役割を分離したため、legacy欠測をmodern観測へ遡及変換せずに
  17条件を照合できる。
- tests-greenと施工者のread-only監査は、独立した正式verdictを代替しない。

## 解釈・未決・formal gate

step 12の施工者検証はgreen。Phase 5完了にはcandidateをcommitまたはstaged treeで固定し、
Claude Codeの別担当によるread-only正式監査で`VERDICT: PASS`を得る必要がある。
house-style classifier model/promptと人間label合意床、semantic retry既定値、
将来のclosing金額、次Atlas corpus拡張、Author候補と費用削減床は引き続きowner判断である。
正式PASSまではPhase 6へ進まない。
