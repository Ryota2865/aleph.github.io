# Phase 2 深い解釈module 設計

日付: 2026-07-19
設計者・施工者: Codex
状態: 採用済み `designs/next-designer-execution-plan.md` Phase 2 の設計ゲート

## 1. 設計ゲートの結論

PLANの意味、保護テスト、公開上限、予算、終端状態不変条件を変えずに施工できる。
`SHELVE`は終端のまま維持し、公開再評価はPhase 1のpublication dispositionを読む。
既存`works/`と監査artifactは変更しない。

三つの依存はすべてin-process計算またはローカルファイルであり、外部portや公開adapter
interfaceは作らない。外部seamは次の三つだけにする。

```python
result = parse_model_output(text, schema={"publish": bool, "reason": str})
snapshot = WorkReader(work_dir).snapshot()
repository = RepositoryReader(root).snapshot()
```

テストはこのinterface越しに行う。内部JSON scanner、event reader、draft selectorを直接の
テスト面にしない。

## 2. read-only走査の観測

### 構造化モデル応答

- JSON object extractorが`explore.niche`、`intent.choose`、`meta.stopping`、
  `meta.publication_gate`、`meta.poetics`、`compose.generate`に重複している。
- `compose.generate`はarray extractorも独自実装する。
- `scripts/run_w0008.py`の家風分類と技術床は`bool(parsed.get(...))`を使う。
  技術床は型検査すらなく、文字列`"false"`がpassになる。
- 公開だけは局所的なbool coercionで修繕済みだが、同型欠陥を他のcallerへ残す。

### 作品現在像

- `checkpoint.json`、`decisions.jsonl`、`trajectory.jsonl`を`pipeline`、publication status、
  public site、dashboard、private shelf、colophon等が個別に読む。
- public siteの`_work_fact`はcheckpoint、decision、trajectory、colophonを独自に結合する。
- dashboardはcheckpointをそのまま現在状態とし、modern event列のstrict replayを通さない。
- 採用稿は`trajectory`最大値、最新decisionの`best_version`、`final/text.md`の間に複数の
  読み方がある。pipeline自身は最大mean score版をfinalへ採用する。
- publication statusだけはPhase 1のstrict replayとdisposition由来検証を実装済みである。

### repository現在像

- dashboardとCLIはbudgetを別々に読む。CLI `status`は作品現在像を返さずJSONもない。
- active jobはPID、formal auditはreport、期限付き決定は正典文書と設定コメントへ分散する。
- public site、dashboard、CLIが同一fixtureを共有するinterfaceがない。

## 3. `ModelOutput`

### interface

`parse_model_output(text, schema, fail_closed=True) -> ModelOutput`。

- schemaは通常のPython型を使う小さい宣言とする。objectは`dict[str, spec]`、arrayは
  `[spec]`、enumは`frozenset`、strict bool/int/float/stringは対応する型で表す。
- `ModelOutput`は`value`、応答全体`raw`、採用fragmentとspan、`warnings`を持つ。
- `require_value()`は拒否結果を例外へ変換し、外向き操作の続行を防ぐ。

### failure model

- fenceや前後文は許すが、独立したJSON値が0件または複数なら拒否する。
- duplicate key、必須field欠落、型違い、enum外、非有限数を拒否する。
- boolは`type(value) is bool`で検査し、文字列や0/1を真偽化しない。
- float specはint/floatを数として受けるがboolを拒否する。int specはboolを拒否する。
- `fail_closed=False`は探索的な内部生成で最初の候補を保持できるがwarningを残す。
  公開・技術床・家風分類・停止・詩学・志向・構成は原則fail closedで移行する。

## 4. `WorkSnapshot`

### interfaceと値

`WorkReader(work_dir).snapshot() -> WorkSnapshot`。返す値は少なくとも次を持つ。

- `work_id`, `title`, `lifecycle`, `publication`, `audience`
- `best_draft`, `latest_draft`, `effective_constraints`
- `poetics_version`, `atlas_identity`, `costs`
- `warnings`, `provenance`

draftはversion、path、text、選択理由を持つ読み取り専用値とする。snapshotはJSONへ決定的に
直列化できる。

### 状態と由来

- modern eventがあればstrict replayを一次像とする。checkpoint不一致はwarningであり、
  表示はreplay側を採る。strict replay不能ならlifecycle/publicationをunknownにしてfail closed。
- legacyは履歴を書き換えずcheckpointを現在像に使い、legacy warningを返す。publicationは
  既存互換の最終L0公開判断だけから得る。
- modern `SHELVE`の公開は、正当な`publication_reassessment` projectionだけを認める。
- 採用版は最新の明示`best_version`を優先し、なければtrajectory最大mean score、最後に
  最新draftへ縮退する。final/textとの不一致はwarningにする。
- `final/text.md`は公開済み作品の採用表現であり、存在だけで公開とは判定しない。
- canonical armはroot作品のcheckpoint payloadまたはarm `meta.json`のstrict boolから読む。
- effective constraintsはseed experimentの`criteria_constraints`を由来つきで返す。
- poetics/atlasはcolophonを読む。欠落または古いcolophonはwarningにする。
- costはcallsの有限な`cost_usd`合計を返し、不正行はwarningにする。

## 5. `RepositorySnapshot`

### interfaceと集約

`RepositoryReader(root).snapshot() -> RepositorySnapshot`。

- `works`: `WorkSnapshot`のwork id順tuple
- `budget`: config宣言と永続ledgerの現在像
- `experiments`: seedにexperiment idを持つ正典workの一覧
- `active_jobs`: `state/run_<work_id>.pid`の存在と生死
- `formal_audits`: audit/report artifactの判定と対象
- `deadlines`: machine-knownな期限付き決定
- `warnings`, `provenance`

`publish.max_per_month == 999`では採用済み決定に従い、2026-08-01の再審査期限を返す。
値を自動変更はしない。tests greenとformal audit PASSは混同しない。

## 6. adapter移行順

1. `RepositorySnapshot.to_dict()`を監査JSON面にする。
2. public siteの公開列挙とwork factをsnapshotへ移す。
3. dashboardの作品・予算収集をsnapshotへ移す。
4. CLI `status --json`を追加し、通常statusも同じsnapshotを表示元にする。
5. README状態節はPhase 6まで手書きの意味を変えず、Phase 2ではsnapshotとの検証可能性だけを置く。

process pageが生のdecision本文やreview本文を表示することは「独自解釈」ではないため残せる。
状態・題・採用稿・公開可否をそこで再計算してはならない。

## 7. tracer bullet受入テスト

1. `ModelOutput`: w0008技術床へ`{"pass":"false"}`を渡すとholdになる。
2. `ModelOutput`: fence＋前後文の単一JSONは通り、複数JSONとduplicate keyは拒否される。
3. `WorkSnapshot`: modern eventと古いcheckpointではreplay状態を返しwarningを持つ。
4. `WorkSnapshot`: 採用版と最新版を分け、壊れたtrajectory・欠落note・古いcolophonを警告する。
5. `RepositorySnapshot`: 同じfixtureをsite、dashboard、CLI JSONへ渡し、状態・題・採用稿が一致する。
6. 実作品8件をread-onlyでsnapshot化し、warningを隠さず決定的な監査JSONを作れる。

各項目を一つずつRED→GREENにし、interfaceテストが成立してから置換済みの浅いparser／reader
テストと実装を整理する。
