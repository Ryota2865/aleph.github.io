# Phase 5 read-only現状調査

日付: 2026-07-21
調査者: Codex（現設計者）
範囲: 計器、Atlas identity、予算予約、終端理由、`author_epoch`
操作: read-only。provider call、有料実験、既存artifactの書き換えは行っていない。

## 1. 結論

Phase 5は新機能の追加より先に、既存の測定値が「何を、どの地図・モデル・
prompt・欠損条件で測ったか」を記録し、比較可否を一箇所で判定する必要がある。

既存の有用な実装は多いが、測定の意味と由来がcallerとartifactへ分散している。
そのため現状では、同じfield名の値でも比較できる保証がない。

## 2. 観測証拠

### 2.1 Atlasとnovelty

- `state/atlas/atlas_meta.json`はPCA次元、kNN、HDBSCANの最小cluster寸法を持つが、
  corpus snapshot、license manifest、chunker、embedder・量子化・版、schema/code版を持たない。
- `state/atlas/manifest.json`と`atlas_meta.json`は存在するが、その2 hashだけを読む
  w0009のidentityは部分的なad hoc identityである。
- w0001–w0008のcolophonは`corpus_id=aozora`だが`atlas_version=null`。w0009 rootには
  colophonがなく、腕のcolophonと`experiment/w0009_shared.json`に由来が分散する。
- `novelty_review()`は稿の最近傍cosine距離を返すが、値にAtlas identity、embedder、
  分割規則、confidenceを付けない。
- L2の`novelty` / `measured_novelty`は候補集合内percentileであり、L6の
  `novelty_dist`と同じ測定量ではない。cell系は`novelty=1.0`、
  `measured_novelty=None`になる既知の盲点がある。

### 2.2 form fidelity

- `transmute()`の第二ゲートはlaw/RFCの正規表現detectorと保持率により実動する。
- S-2 pilotは40件でcontent distanceと骨格保持がほぼ無相関と示し、
  w0008は0.4床と実測値を保存した。
- detector未登録のkindは測定不能だが、現在の出力は計器の版、適用kind、既知の
  盲点、confidenceを共通schemaで表現しない。

### 2.3 fixation

- `aleph.meta.poetics.fixation_check()`は隣接する詩学本文の文字2-gram Jaccardを見る。
- `tests/test_fixation_check_first_case.py`は、w0004/w0005/w0007の作品横断の修辞装置・
  世界型反復を当該関数が検出できないことを、想定どおりの既知反例として固定する。
- w0008では箇言調が地の文から人物の引用へ変換された。これを固着の解消か
  配役変更による持続か判定する計器はない。
- w0008で意味核の裏方語彙を除外しても`backstage_world=1.0`だったため、
  house-style classifier自身に反例校正が必要である。

### 2.4 disagreementとparse安定性

- 通常のL6はvalid scoreの母標準偏差を`disagreement`とし、不正scoreを除外する。
  trajectoryはexpected/valid juror数、roster、prompt版、parse失敗内訳を持たない。
- w0009の二次比較は、6 call完了後の最後のstrict parse失敗により、全scoreの
  投影が空の`INCOMPLETE_PARSE`になった。call/charge/response hashは残ったが、
  jurorごとのparse結果を逐次硬化しなかった。
- w0009 reportの「disagreement」はmax-minで、通常L6の標準偏差と定義が異なる。

### 2.5 perplexity

- 実装が出力するのはsegmentごとのmean logprobであり、狭義のperplexity
  `exp(-mean_logprob)`ではない。
- reader model、tokenizer、contextとsegment規則、prompt版、logprob取得の可否が値に
  付かないため、modelまたぎの縦比較はできない。

### 2.6 予算とatomic batch

- `Budget` は月次・作品・experiment scopeの上限、precheck、charge event、残額を持つ。
- scopeには予約とpoolがない。precheckとprovider実行の間に他callが残額を消費でき、
  held-out評価・閉幕batchのcommitmentを表現できない。
- w0009のphase envelopeはmanifestにあるがsoft allocationであり、aggregate capだけが
  provider前のhard gateである。結果、閉幕の公開意思callは最後に拒否された。

### 2.7 WorkSnapshot、SHELVE、author epoch

- w0009のevent列は`stop_path=budget`と`failure_category:resource_stop`を正しく保存する。
- `WorkSnapshot`は`lifecycle/publication`を返すが、`stop_path`、failure category、
  終端理由を返さない。そのためrepository集計やsiteはresource stopと
  aesthetic failureを安定して分類できない。
- colophonに`author_models`はあるが`author_epoch`はない。RepositorySnapshotも
  cross-epoch集計のwarningを出さない。

## 3. 解釈

1. `InstrumentRecord`が必要な理由は測定関数の数を減らすことではなく、
   計器定義、出力由来、比較可否、反例と盲点を一つのseamに集約することにある。
2. `AtlasIdentity`は版番文字ではなく、決定的payloadとhashを持つ必要がある。
3. 予算保護は新しいbudget wrapperではなく、既存`Budget`に予約実装を隠すことで
   callerへの配賦計算の流出を防げる。
4. `WorkSnapshot`は既に作品現在像のseamであるため、SHELVE理由とepoch読み取りは
   ここを深くする。別readerは作らない。

## 4. この調査が確定しないこと

- 候補Author、費用削減床`X%`、新Author採用。
- 新しいAtlasの実構築、既存Atlasの遡及的identity付与。
- fixation classifierの最終promptと採用model。
- 評価語彙を作品本文へ返すshadow RSI実験。

これらはPhase 5設計監査と実装・校正後の別ゲートである。
