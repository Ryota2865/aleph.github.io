# 次期設計者 実行計画

日付: 2026-07-18
設計者: Codex（GPT-5）
入力: `reports/DESIGNER_INSIGHTS_20260718.md`
状態: **全面採用（2026-07-18、オーナー明示承認）**。各phaseはこの順序を正典上の
実行方針とし、個々の施工では設計変更の門、必要なオーナー承認、施工者・監査者の
分離を経る。Phase 5は2026-07-24に正式独立監査PASSで完了した。オーナーの同日決定により、
現任設計者CodexはPhase 6の正式完了まで継続し、途中で設計者を交代しない。

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

状態: **正式PASS（2026-07-19）**。Codex施工後、Claude Codeの独立再監査で
契約違反P0–P2なしと確認済み。設計契約は
`designs/transition-commit.md`、legacy基線は
`reports/TRANSITION_HISTORY_AUDIT_20260718.md`を参照。

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

状態: **正式PASS（2026-07-19）**。Codex施工後、Claude Codeの独立監査で
duplicate-key後の内部候補救済にP2を1件検出し、fail-closed回帰を追加。独立再監査は
**VERDICT: PASS**。設計ゲートは`designs/phase2-deep-interpretation.md`、監査記録は
`reports/PHASE2_DEEP_INTERPRETATION_AUDIT_20260719.md`と
`reports/PHASE2_P2_1_REAUDIT_20260719.md`。非local検証は284 passed, 1 deselected。

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

状態: **正式PASS（2026-07-19）**。Codex施工後、Claude Codeの独立監査で
P0–P2なし、必須7分類の故障注入がすべてfail closedと確認済み。設計ゲートは
`designs/phase3-experiment-evaluation.md`、監査記録は
`reports/PHASE3_EXPERIMENT_EVALUATION_AUDIT_20260719.md`。非local検証は
293 passed, 1 deselected。

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

**状態（2026-07-19）:** 設計・事前登録・実走・三面報告・正式独立監査を完了し、**PASS**。
主判定は`RULE_4_LEVEL_SPLIT_OR_MIXED`、終端はbudget経路の`SHELVE`。詳細は
`designs/phase4-w0009-l2-era-intervention.md`、`reports/EXP_w0009_l2_era_20260719.md`、
`reports/PHASE4_W0009_L2_ERA_AUDIT_20260719.md`。Phase 5には進んでいない。

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

**状態（2026-07-24）:** **完了。** read-only現状調査と設計を作成し、Claude Code
（Opus 4.8）の実装前独立設計監査でPASS。Phase 5A/5B core、通常run closing、
Phase 5C step 9–12を順に実装し、各候補を施工者と異なるClaude Code担当が正式監査した。
`reports/PHASE5_READ_ONLY_INVENTORY_20260721.md`、`designs/instruments.md`、
`designs/phase5-instruments-atlas-budget.md`を設計基線とした。Phase 5C candidate
`fd9740f`の正式監査はPASS。P2-1を修繕したtree `55960380567e5c040fb95cfbf9f77947644ee231`
も同じ監査担当がfocused再監査し、P0–P2なし、**VERDICT: PASS**。
監査記録は`reports/PHASE5C_FORMAL_MILESTONE_AUDIT_20260723.md`と
`reports/PHASE5C_P2_1_REAUDIT_20260724.md`。

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

**状態（2026-07-24）:** 開始。closing reserve算出とreader tokenizer identityを、
新作・有償callなしの自己完結tracer bulletとして施工した。初回正式監査は、v1 checkpoint
bypassとpricing/slot/versionのreservation identity欠落をP2として検出し**FAIL**。原文を保存し、
observable REDから同根修繕した。同一監査者のfocused再監査でP0–P2なし、
**VERDICT: PASS**。このtracer bulletはformal完了した。詳細は
`designs/phase6-closing-reader-identity.md`。Phase 6全体は継続中であり完了とはしない。

### 6.0 Phase 6前のdecision gate

以下は2026-07-24の設計者分類と同日のオーナー回答を統合したgateである。model/prompt、
人間labelの合意床、Author候補、費用削減床など、表に明記していない値は未決のままとする。

| 項目 | Phase 6との境界 | 決定・状態 |
|---|---|---|
| closing予約 | 新しいprotected normal runの開始前に必要。文書・read-only施工だけならPhase 6開始のblockerではない | **承認済み**。恒久的な固定USDではなく、走行前manifestのclosing slotごとのprovider/model、価格版、入力・出力token上限から最大費用を合算する |
| reader tokenizer identity | 新しい`reader.mean_logprob`測定または比較の前に必要 | オーナー入力を待たず、local GGUFのtokenizer metadataから決定的identityを作る。未検証identityのrecordは比較不能のままにする |
| house-style label protocol | `fixation.house_style`をprovisionalから昇格し、自動判断へ使う前に必要。Phase 6の統治・公開整合だけには不要 | **負荷枠を承認済み**。短い抜粋12組、3択、2名（1名はオーナー）、15–20分/人以内。LLMは候補抽出だけに使い、blindな人間goldを置換しない |
| Author migration benchmark | Authorを変更する前に必要。現Authorを固定するPhase 6の開始前には不要 | Phase 6完了後へ延期を推奨。候補、費用削減床、刺激数、有償call上限は未決 |
| 小規模corpus拡張 | 現Atlas identityを変えるため、Phase 6のcurrent-state整合には不要 | Phase 6中は現Atlas固定を推奨。拡張の価値判断は未決 |
| provider statement adapter | provider usage statementを取得でき、`matched`を主張する前に必要 | **Phase 6必須外**。top-up通知は`funding_receipt`。通常はbest-effort集計照合とし、低負荷で維持できる場合だけadapterを追加する |

したがって、全項目をPhase 6開始前に決める必要はない。外部callを伴う新規runをPhase 6中に
行う場合はclosing予約が先行する。reader計器を新規発行する場合はtokenizer identityが先行する。
Author、corpus、statement adapterは上記条件が発生しない限りPhase 6完了後へ延期できる。

Phase 6では新作のprotected normal runを既定では行わない。健全な進行に必要な場合だけ、
設計者が必要性、最大費用、入力、成功・停止条件を事前記録した有償runを実施できる。
この許可はrunごとのmanifest、closing reserve、既存hard cap、formal gateを緩和しない。

#### closing reserve算出契約

外部callを行う各closing slot `s`について、走行前に次を固定する。

```text
slot_max(s) =
  input_token_ceiling(s)  * input_usd_per_token(pricing_version, model)
  + output_token_ceiling(s) * output_usd_per_token(pricing_version, model)

closing_reserve = sum(slot_max(s) for external closing slots)
```

cached input、reasoning token、固定call料など別課金軸があるproviderでは、適用可能な最大単価を
同じ価格版へ含める。決定的な題・event・final投影等の無料slotも完了条件へ登録するが、
予約額は0とする。価格版、model、課金軸、token ceilingのいずれかが不明ならrun admissionを
拒否する。manifestの任意USDを根拠なく信頼せず、計算値と`max_amount`の一致を検証する。

#### house-style低負荷protocolの外枠

- 12組の短い抜粋を、`同じ装置 | 担体・役割を変えた変形 | 異なる・不明`の3択で独立annotationする。
- annotatorは2名で、1名はオーナー。各annotatorの作業時間は15–20分以内を目標とする。
- LLMは候補組とhard negativeを作れるが、annotatorへLLM labelや理由を事前表示しない。
- model/prompt、抜粋単位、もう1名のannotator、合意床と不一致裁定は未決であり、
  annotation開始前に固定する。12組の結果を見てから合意床を下げない。

### 6.0.1 Provider cost証拠のbest-effort運用

詳細なcall単位照合は継続性に対して負荷が高いため、Phase 6の必須条件にしない。請求書、
dashboard export、画面保存は非公開のlocal `cost/`へ保存し、git追跡しない。通常運用では
repositoryのcall/charge台帳、hard cap、protected reservationを維持し、provider側証拠は
期間・model別のsanity check、残高確認、重大な差異の調査へ限定する。

取得できる場合も、証拠は次の三層を混同しない。

1. `funding_receipt`: provider、チャージ日時、金額、通貨、取引ID（存在する場合）。
   利用可能残高の来歴には使えるが、call費用との`matched`判定には使わない。
2. 集計usage: 対象期間とtimezone、provider/project、model、input/cached-input/output/reasoning
   token、請求額、通貨、割引・credit・refund。日別またはmodel別集計なら、同じ粒度の台帳集計と
   照合できるが、個別callの一致は主張しない。
3. call単位usage: provider request/call ID、発生日時とtimezone、model revision、token内訳、
   請求額・通貨、status、refund/reversal。repositoryのcall recordへ同じprovider request IDが
   保存されている場合だけ、call単位の三面照合候補にする。

取得はCSVまたはJSON exportを優先し、export生成日時、対象期間、timezone、列定義を一緒に残す。
スクリーンショットしかない場合は原証拠として保存できるが、自動adapterの入力とはみなさない。
API key、完全なaccount ID、支払カード、住所等の秘密・個人情報は取得物へ含めず、必要なら
安定した非秘密project labelへ置換する。dashboardが集計粒度しか提供しない場合も正常であり、
その粒度を越える精度を推定しない。

call単位request IDの完全一致、全provider共通adapter、毎runの手動downloadは要求しない。
provider証拠がない計器recordは`matched`を主張せず、`unreconciled`または
`operational_estimate`と表示する。これは費用値の精度表示であり、hard cap違反や台帳破損が
ない限りPhase 6のformal completionを単独ではblockしない。

### 6.1 正式監査

- M7/M8の現行修理を、施工者と異なる監査者が再検証する。
- 既存FAIL artifactは消さず、再監査結果を追記または新artifactとして結ぶ。
- 「tests green」と「formal audit PASS」をRepositorySnapshotで別表示する。

### 6.2 批評家役職

`designs/critic-role.md`とFable 5の条件付き承認を反映したPLAN §12.2を実装する。
2026-07-19以降、外部批評はAPIを自動経路として継続する。設計者と批評家を同一モデルが
兼任してもよいが、依頼・文書・権限を分離する。批評専用月額はまだ適正値が不明なため、
当面は総API上限$71（2026-07-19のオーナー決定）の内数としてcall/charge provenanceを残し、
全文脈を削るのではなく
頻度と対象数で調整する。専用枠は実測後にオーナー決定を受けて追加する。これと並行し、
2026-07-20以降はClaude Proの$100クレジットを使うオーナー起動の手動全体批評adapterを
残す。これはAPI費用へ合算せず、PLAN §12.2の記録interfaceを満たす場合だけ正式な批評入力とする。

### 6.3 現在状態

施工状態（2026-07-24）: RepositorySnapshotのassurance/design state/deadline可視化と
`resume` aliasを0.7.20-27で施工。初回正式監査FAILの辞書順・散文currency問題を
0.7.20-28の明示audit ledgerで修繕し、2026-07-25の同一監査者focused再監査で正式PASS。
candidate tree実照合は残置R-2として次tracer bullet候補。公開上限の値変更は期限時の
設計審査まで行わない。

R-2施工状態（2026-07-25）: `designs/phase6-audit-tree-binding.md`と0.7.20-29で、
candidate tree/commit/tag、clean HEADまたはfully-staged index、closure allowlistをcurrencyへ
束縛するtracer bulletを施工。初回正式監査FAILの`git diff` timeout P2-1を0.7.20-30で
fail-closed修繕した。同一監査者がHEAD/INDEX両経路の実timeout RED→GREENを独立確認し、
P0〜P2なし、**VERDICT: PASS**。R-2はformal完了。初回FAILとPASSのcandidate treeは
proof commit/tagへ固定し、P3-5をclosureで解消した。P3-1〜P3-4、P3-6、
Git index flag等の監査uncertaintyは残置する。次の自己完結tracer bullet候補はR-1
（`supersedes`検証のledger記載順依存）。

R-1施工状態（2026-07-25）: 0.7.20-31と
`designs/phase6-audit-supersedes-order.md`で、ledger `entries`のJSON配列順を意味から除き、
`sequence`だけを権威順序とするtracer bulletを開始した。`supersedes`は厳密に小さいsequenceの
既存entryだけを参照でき、reverse-order記載を受理しつつself/future/cycle/missing参照を
fail closedにする。observable RED 2件から修繕し、focused 24件、全non-local
429 passed, 1 deselectedがgreen。独立Claude Code正式監査は3-entry全6配列順を含む
17ケースを独立注入し、P0〜P3なし、**VERDICT: PASS**。R-1はformal完了。
次の自己完結tracer bullet候補はR-3（terminal verdictの厳密大小文字契約）。

R-3施工状態（2026-07-25）: 0.7.20-32と`designs/phase6-audit-strict-verdict.md`で、
machine verdictを最終非空行そのものの厳密な`VERDICT: PASS|FAIL`へ限定するtracer bulletを
開始した。case-insensitive、空白欠落／過剰、tab、行頭末尾空白、suffixの受理を廃止し、
曖昧なartifactは`UNKNOWN`へfail closedする。observable RED 2件から修繕し、
focused 26件、全non-local 431 passed, 1 deselectedがgreen。独立Claude Code監査は
旧実装の偽陽性9件を再現し、候補の26ケース、no-fallback/no-alternate-path、candidate identity
不変を確認した。P0〜P3なし、**VERDICT: PASS**。R-3はformal完了。

R-4施工状態（2026-07-25）: 0.7.20-33と`designs/phase6-budget-snapshot-isolation.md`で、
`RepositorySnapshot.to_dict()`のbudget返却値をsnapshot本体から分離するtracer bulletを
開始した。返却payloadの`ledgers`、`ledger_status`、`work_spent`を変更するとfrozen snapshotへ
逆流するobservable REDを、budgetのdeep copy一箇所でGREEN化した。R-5〜R-9と
R-2残置P3は範囲外。focused 27件、全non-local 432 passed, 1 deselectedがgreen。
独立Claude Code監査は旧実装の三面逆流RED、候補のsnapshot不変、再serialization非汚染、
空budget shape不変を確認した。P0〜P2なし、**VERDICT: PASS**。R-4はformal完了。
他の浅いitem copyと未実行runtime/provider経路はP3残余として保持する。

R-5施工状態（2026-07-25）: 0.7.20-34と`designs/phase6-audit-ledger-provenance.md`で、
`RepositorySnapshot.formal_audits`の公開provenanceへ権威ledger
`config/formal-audits.json`を明示するtracer bulletを開始した。ledger metadataを使いながら
artifact directoriesだけを出所表示するobservable REDを、既存provenance tupleへの一項目追加で
GREEN化した。R-6〜R-9、R-2残置P3、R-4監査P3は範囲外。
focused 28件、全non-local 433 passed, 1 deselectedがgreen。
独立Claude Code監査は26件の故障注入とidentity不変を確認し、P0〜P3なし、
**VERDICT: PASS**。R-5はformal完了。

R-6施工状態（2026-07-25）: 0.7.20-35と`designs/phase6-missing-publish-cap.md`で、
`publish.max_per_month`欠落時にdeadline不在理由をwarningへ出すtracer bulletを開始した。
`deadlines=()`と`publish_cap=None`を維持したままwarningだけが欠落するobservable REDを、
missing key分岐の追加でGREEN化した。R-7〜R-9、R-2残置P3、R-4監査P3は範囲外。
focused 29件、全non-local 434 passed, 1 deselectedがgreen。
独立Claude Code監査は全中心契約とidentity不変を確認し、P0〜P3なし、
**VERDICT: PASS**。R-6はformal完了。

R-7施工状態（2026-07-25）: 0.7.20-36と`designs/phase6-changelog-version-order.md`で、
CHANGELOGのfence外top-level版見出しを数値版順で選ぶtracer bulletを開始した。物理先頭の旧版が
後方の正規最新版を隠すREDをGREEN化し、code fenceと引用内例示をlatest候補から除外する。
R-8〜R-9、R-2残置P3、R-4監査P3は範囲外。focused 30件、全non-local
435 passed, 1 deselectedがgreen。独立Claude Code監査はP0〜P2なし、
**VERDICT: PASS**。R-7はformal完了。版separator、未閉fence、indent fenceはP3残余。

R-8施工状態（2026-07-25）: 0.7.20-37と`designs/phase6-missing-poetics-history.md`で、
poetics history欠落時のcanonical v0 fallback理由をwarningへ出すtracer bulletを開始した。
v0値は維持しwarning欠落REDだけをGREEN化した。focused 31件、全non-local
436 passed, 1 deselectedがgreen。独立Claude Code監査はP0〜P3なし、
**VERDICT: PASS**。R-8はformal完了。R-9と残置P3は範囲外。

R-9施工状態（2026-07-25）: 0.7.20-38と`designs/phase6-audit-path-disjoint.md`で、
同一pathのlegacy/registered二重分類をfail closedするtracer bulletを開始した。旧実装の
無警告registered昇格PASSを、overlap warning、entry拒否、ledger UNKNOWNへGREEN化した。
focused 32件、全non-local 437 passed, 1 deselectedがgreen。
R-1〜R-9外の残置P3は範囲外。正式監査待ち。

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
