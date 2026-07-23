# Phase 5C step 11 — runtime InstrumentRecord配線

日付: 2026-07-23
scope: Phase 5C施工順11のみ

## 観測

- 新規workは`measurements.jsonl`を持ち、`InstrumentRecorder`がregistry検証済みrecordを
  append-onlyで保存する。同一`measurement_id`/同一payloadの再投影は行を増やさず、
  同一id/異なるpayloadは拒否する。
- 通常runのreview seamから次を記録する。
  - `novelty.atlas_cosine`: full Atlas identity、embedder build identity、分割規則。
  - `jury.disagreement_stddev`: score scale、jury roster、evaluation packet、validity rules。
  - `parse.reliability`: valid/expected slot、failure taxonomy、schema/parser/retry policy。
  - `reader.mean_logprob`: reader model/tokenizer/context/promptとsegment別mean logprob。
- protected runの終端seamから`run.completion`を記録する。既存の
  `complete|complete_short|resource_interrupted`分類を再計算せず読み、
  通常完走だけrecord値`complete_normal`へ写像する。
- `cost.reconciled_usd`はcall/charge/providerの三者照合を要求する。provider statementが
  無い現在のruntimeでは値を0にせず、`measurement_status=missing`、
  `reconciliation_status=unreconciled`として保存する。
- CLIの通常`run`/`publish`既定Atlasをstep 10のfull identity Atlasへ切り替えた。
  legacy `explore`出力先は変更していない。
- provider call、新作生成、既存work、既存review/trajectory、auditの書換えは行っていない。

## 反例検証

- 3 juror中2件valid、1件parse failureでは、disagreementはvalidな`4, 8`だけから`2.0`、
  parse reliabilityは`2/3`となる。parse failureを0点に偽装しない。
- reader logprobのfixtureは`-2.0`を観測値として保存し、missingと0.0を混同しない。
- provider statement欠落fixtureはcost値を持たない。call logだけからreconciled USDを
  推定しない。
- terminal recoveryで同じcompletion/costを再投影しても2計器2行のままである。
- novelty recordはfull Atlas identityを必須とし、registryの既存比較guardにより
  cross-Atlas deltaを返さない。

## 検証

- focused（step 11＋既存review/pipeline契約）: **15 passed, 22 deselected**
- 全non-local: **388 passed, 1 deselected**
- `git diff --check`: 違反なし

## 推論

- 計測計算をdomain moduleに残し、coreをprovenance検証・比較・保存へ限定したため、
  `measure(kind, **kwargs)`型のdispatcherは導入していない。
- costの欠測を一級recordにしたことで、w0009型の未照合費用が完全照合額として後続判断へ
  流れることはない。

## 解釈と残余

step 11はruntime record配線としてgreen。ただしprovider statement取込adapterが無いため、
`cost.reconciled_usd`の観測値はまだ発行できない。reader tokenizerはprovider既定値を
`unverified` identityとして明記しており、厳密なtokenizer revisionが得られるまで
cross-run比較の根拠にしない。これらは値を捏造せず欠測・不確実性を保存する選択である。
