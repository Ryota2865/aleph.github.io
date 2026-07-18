# 次期設計者 実行計画

日付: 2026-07-18
設計者: Codex（GPT-5）
入力: `reports/DESIGNER_INSIGHTS_20260718.md`
状態: **全面採用（2026-07-18、オーナー明示承認）**。各phaseはこの順序を正典上の
実行方針とし、個々の施工では設計変更の門、必要なオーナー承認、施工者・監査者の
分離を経る。

## 0. 目的

新しい機能を増やすことより、状態・費用・実験条件・評価文脈を一貫して記録・再生する
moduleを先に深くする。その上でw0009をL2属性介入として走らせ、家風の担体仮説を検証する。

設計原則:

- 一つの意味を複数の呼び出し側に実装しない。
- interfaceをテスト面とし、内部実装のテストを増殖させない。
- 過去の`works/`を黙って書き換えない。必要な訂正は追記イベントにする。
- 実験固有の分類器は汎用化しない。反復する意味だけをmoduleへ抽出する。
- 設計者が施工した変更を、同じ設計者が監査しない。

## 1. 実行順の全体像

| Phase | 目的 | 新しい中心interface | 完了条件 |
|---|---|---|---|
| 0 | 就任・事実固定 | なし | 就任記録、洞察、計画が保存済み |
| 1 | 一次記録の正規化 | `TransitionCommit` | 新規runがevent列だけから厳密再生できる |
| 2 | 解釈の集約 | `ModelOutput`, `WorkSnapshot`, `RepositorySnapshot` | 公開・監査・dashboardが同じ現在像を読む |
| 3 | 実験を一級化 | `ExperimentRun`, `EvaluationPacket` | 腕・費用・制約・正典選択が一つに結ばれる |
| 4 | w0009 | w0009 manifest | L2時代属性仮説が事前登録規則で判定される |
| 5 | 計器・地図校正 | `InstrumentRecord`, `AtlasIdentity` | 比較可能条件と既知の盲点が追跡される |
| 6 | 統治・公開整合 | current-state projection | 正式監査、README、期限付き決定が一致する |

## Phase 0 — 就任と基線の固定

### 実施済み

- PLAN §12.1の必読4文書を通読。
- `PLAN_CHANGELOG.md` 0.7.20-2に就任と現状理解を記録。
- 全体洞察と本計画を保存。
- 非localテスト229件、公開サイト主要ページ一致、git cleanを基線として確認。

### 残作業

- 本変更後の文書リンク・テスト・git差分を検証する。
- 次phase着手時に、施工担当と独立監査担当を明記する。

## Phase 1 — `decisions.jsonl`を実効上の一次記録にする

### 1.1 先に設計するinterface

```python
result = transition_commit.commit(
    work,
    command_id=...,
    expected_state=...,
    next_state=...,
    reason=...,
    decided_by=...,
    payload_delta=...,
)
# result.event, result.checkpoint, result.replayed_snapshot, result.warnings
```

interfaceが隠すもの:

- 遷移表検証
- 単調な`event_id`と冪等な`command_id`
- eventの追記とcheckpointの原子的projection
- 遷移元の連続性検査
- クラッシュ時の再試行と重複抑止
- 起動時のevent/checkpoint不一致検出
- legacy eventの警告とreconciliation注釈

### 1.2 置換対象

- `Loop.transition()`
- `pipeline._transition()`
- `aleph publish`のcheckpoint直接巻き戻し
- w0008 runnerのcanonical handoff
- 一回性scriptが行う状態変更

旧interfaceの上に新interfaceを重ねて残さず、呼び出し側を移行後に旧経路を削除する。

### 1.3 公開再評価の設計ゲート

SHELVEを終端のまま維持しつつ公開再評価を表現する方法を、実装前に決める。

- 候補A: lifecycleとpublication dispositionを直交する投影に分ける。
- 候補B: state machineへ明示的な再評価command/eventを導入する。

`SHELVE->FINISH`を単純追加する案は、terminal state不変条件を弱めるため採らない。
もし不変条件変更が必要なら、オーナー明示承認を先に得る。

### 1.4 過去作品の扱い

- 既存ログは書き換えない。
- 8作品へread-only監査を行い、不連続を機械可読なreportにする。
- 必要なら`reconciliation` decisionを追記する。元イベントの削除・並べ替えはしない。
- legacy payload不足は「再生不能範囲」として明示する。

### 受入条件

- 新規の完全run、クラッシュ再開、公開再評価、実験handoffで遷移元が連続する。
- `checkpoint == strict_replay(events)`が実作品fixtureで成立する。
- 同じ`command_id`の再実行でeventと費用が増えない。
- event追記とprojectionの間で故障させても、次回起動で自動回復または明示停止する。
- 現存8作品のwarning一覧が生成され、無警告を偽装しない。

### 停止条件

過去ログの完全再生を成立させるために履歴改変が必要になった場合は停止し、
append-only注釈で足りる範囲へ設計を縮小する。

## Phase 2 — 解釈を深いmoduleへ集約する

### 2.1 `ModelOutput`

```python
result = parse_model_output(text, schema=Schema, fail_closed=True)
# result.value, result.raw, result.warnings
```

責務:

- fence・前後文から単一JSONを抽出
- bool、enum、数値の厳密な型検査
- 欠落、複数JSON、矛盾の拒否
- 外向き操作と実験判定のfail-closed
- 生応答と解釈結果の監査可能な関連づけ

置換順: 公開・技術床・家風分類・停止・詩学・志向・構成。
とくにw0008 runnerの`bool(parsed.get(...))`を最初に回帰テスト化する。

### 2.2 `WorkSnapshot`

```python
snapshot = WorkReader(work_dir).snapshot()
# lifecycle, publication, audience, best_draft, effective_constraints,
# poetics_version, atlas_identity, costs, warnings, provenance
```

意味を一箇所で決める:

- eventとcheckpointが食い違うときの表示
- 採用稿と最新稿の区別
- 公開状態と完成状態の区別
- 壊れたtrajectory、欠落note、古いcolophonのwarning
- canonical/noncanonical armの扱い

### 2.3 `RepositorySnapshot`

`WorkSnapshot`群、予算、実験、active job、formal audit、期限付き決定を集約する。

最初のadapter:

1. 監査用JSON/report
2. public site builder
3. dashboard
4. CLI `status --json`
5. README状態節の検証または生成

### 受入条件

- 同一fixtureをpublic site、dashboard、CLIへ渡すと状態・題・採用稿が一致する。
- 壊れたevent列と文字列`"false"`が安全側のwarning/errorになる。
- 新しい読み取り実装が生ファイルを独自解釈しない。
- interfaceテスト成立後、置換された浅いparser/readerテストを整理する。

## Phase 3 — Experimentと評価文脈を一級化する

### 3.1 最小の`ExperimentRun`

持つもの:

- `experiment_id`、manifest版、仮説、介入、対照、観測規則
- arm identityと各work identity
- 全phaseを含むbudget envelope
- 盲検label mappingと開示時刻
- canonical selectionとpromotion event
- deviationと事前登録からの逸脱理由

持たないもの:

- 技法ごとの分類ロジック
- 任意の実験を表現するDSL
- 汎用workflow engine

### 3.2 call/charge provenance

各call recordへ次を追加する:

- `call_id`, `command_id`, `work_id`, `experiment_id`
- `phase`, `arm`, `charged_to`
- budget charge eventへの参照

budget永続化は合計だけでなくcharge eventを残す。呼び出しログ合計、内部台帳、
provider請求の三者を`matched/unreconciled`で表示する。

### 3.3 `EvaluationPacket`

```python
packet = EvaluationPacket.for_draft(work_snapshot, draft_version)
```

含めるもの:

- intentとcriteria
- base constraintsとamendments
- amendmentの出所・適用範囲・優先順位・失効条件
- poetics versionとatlas identity
- draft/provenance参照

L4、L5、L6、L7は同じpacketを読む。reviewにはpacket hashを記録する。

### 受入条件

- report、budget ledger、callsの費用が同一scope指定で一致する。
- selectとcanonical-L6がexperiment capに含まれる。
- blind selection前にjury情報へアクセスできないことがテストされる。
- 制約解除後の陪審が旧制約を違反として減点しない。

## Phase 4 — w0009: L2時代属性の介入実験

### 着手条件

- Phase 1の新規遷移経路が完成。
- `ModelOutput`のbool判定と`EvaluationPacket`が利用可能。
- 実験費用の全包絡を見積もり、必要ならオーナーが予算を承認。
- 設計manifestを次期設計者が審査し、施工は別担当が行う。

### 推奨する最小設計

- 問い: 題材の家風はL2の時代属性ピンが設置しているか。
- control: 現行方式の属性付きニッチ。
- intervention: 同じ意味核から時代属性だけを除く。
- ニッチは演劇・稽古場・帳場と無関係な主題を選ぶ。
- 素材条件は固定し、w0008の三腕アブレーションを繰り返さない。
- L4複数案とL5正典を観測する。
- 観測: 時代標識、裏方世界、箴言調、引用への変換、視点逸脱、陪審不一致。
- 判定規則と交絡を実行前に固定する。

### 判定の慎重さ

一作で「家風の原因」を確定しない。control/interventionの方向差を次の仮説更新に使う。
負の結果でも、L2属性が少なくともこの条件では担体でないという狭い結論に留める。

### 受入条件

- 全審級が同じeffective constraints hashを記録する。
- 事前登録外の裁量変更がdeviation eventとして残る。
- 費用包絡に全phaseが入る。
- 正典選択と陪審開示の順序がevent列から検証できる。
- 結果が研究report、works/、公開サイトの三面で同じ説明になる。

## Phase 5 — 計器とAtlasの校正

### 5.1 計器台帳

既に承認済みだが未作成の`designs/instruments.md`を作る。最低5計器:

- novelty
- form fidelity
- fixation
- disagreement
- perplexity

各行に、主張、入力、出力、最終校正日、反例、既知の盲点、次の校正条件を持つ。
計器を増やす前に、台帳へ登録できることを採用条件にする。

### 5.2 fixation初回校正

w0004/w0005/w0007の警句機関と、w0008の「引用への変換」を対象にする。
単純な表層反復検出が、変換を「解消」と誤認しないかを検査する。

### 5.3 `AtlasIdentity`

次を決定的にhash化する:

- corpus snapshotとライセンスmanifest
- chunker設定
- embedder/量子化/版
- PCA/UMAP/HDBSCAN等のbuild params
- schema/code version

novelty値、niche report、material card、work colophonがidentityを参照する。

### 5.4 L2発生源の期限

0.7.19-1の事前登録を維持する。拡張後最初の2作品、遅くとも2026-09-30までに、
ニッチ報告有無が構成案分布を実質的に変えることを示す。示せなければ発生源役をclosedにする。

### 受入条件

- 版の異なるatlas間でnovelty比較を試みると拒否または明示warningになる。
- 全計器に最低1つの既知反例が登録される。
- 計器出力にモデル・prompt・identity・confidenceが付く。

## Phase 6 — 統治・公開・運用の整合

### 6.1 正式監査

- M7/M8の現行修理を、施工者と異なる監査者が再検証する。
- 既存FAIL artifactは消さず、再監査結果を追記または新artifactとして結ぶ。
- 「tests green」と「formal audit PASS」をRepositorySnapshotで別表示する。

### 6.2 批評家役職

`designs/critic-role.md`とFable 5の条件付き承認を反映したPLAN §12.2を実装する。
2026-07-19以降、外部批評はAPIを自動経路として継続する。設計者と批評家を同一モデルが
兼任してもよいが、依頼・文書・権限を分離する。批評専用月額はまだ適正値が不明なため、
当面は総API上限$65の内数としてcall/charge provenanceを残し、全文脈を削るのではなく
頻度と対象数で調整する。専用枠は実測後にオーナー決定を受けて追加する。これと並行し、
2026-07-20以降はClaude Proの$100クレジットを使うオーナー起動の手動全体批評adapterを
残す。これはAPI費用へ合算せず、PLAN §12.2の記録interfaceを満たす場合だけ正式な批評入力とする。

### 6.3 現在状態

- READMEの状態節をRepositorySnapshotから生成またはCI検証する。
- PLAN冒頭のCHANGELOG範囲、公開作品数、詩学版、audit状態の陳腐化を検出する。
- 2026-08-01に`publish.max_per_month=999`の期限切れを検出し、いったん4へ戻すか、
  再帰的自己改善の観測に必要な新上限へ変更する設計審査を必須にする。4は再審査の
  初期値であり、恒久的な最適値とは扱わない。
- `resume`は実装するか`run`のaliasにする。表示だけのcommandを残さない。
- 二つのsite generatorは正規interfaceとlegacy adapterへ役割を明記する。

### 受入条件

- README・dashboard・サイト・CLIの作品数と状態が一致する。
- 期限付き決定が期限を越えると自動で可視化される。
- formal auditの最終判定を一箇所から取得できる。

## 2. 明示的な非目標

この計画の完了前には、次を優先しない。

- UI-2の書き込みフォーム
- Gutenberg/Wikisourceの大規模取得
- 汎用実験DSLやworkflow framework
- 新しい公開チャネル
- §16.12の緊張の解消・緩和
- 人間エスカレーション条件の緩和

## 3. 施工・監査の割当原則

各phaseで次を記録する。

1. 設計者: interface、意味、受入条件、変更理由を書く。
2. 施工者: 設計に従い実装し、自己検証を添える。
3. 監査者: 施工者とは別で、interface越しの再実行、実データ、失敗注入を検証する。
4. オーナー: 予算変更、§12.1の保護三類型、新しい外部公開、価値判断を承認する。

本設計者が直接施工したphaseは、別の監査者へ渡す。監査artifactがPASSになるまで、
次phaseの不可逆な外部操作や高額実走へ進まない。

## 4. 最初の具体的な着手順

1. `TransitionCommit`の設計書と実データ回帰fixtureを作る。
2. w0004/w0007の公開再評価、w0008のhandoffをfixture化する。
3. `ModelOutput`の文字列false回帰を追加する。
4. `WorkSnapshot`のwarning contractを定義する。
5. `EvaluationPacket`を最小実装し、w0008相当の解除条項伝播テストを作る。
6. ここまで独立監査を通した後、w0009 manifestを起草する。

次のセッションで着手するなら、入口は**1の設計書**である。いきなりw0009 runnerを
書き始めない。
