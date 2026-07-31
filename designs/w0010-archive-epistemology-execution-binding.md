# w0010 アーカイブ認識論の出口封鎖 — execution binding

日付: 2026-07-31

状態: `CONSTRUCTED / INDEPENDENT AUDIT PENDING / NOT RUN`

## 1. 範囲と固定済み入力

本書は、結果観測前にcommit `aaade529dae421211871d83bcd54b835f67e1a1a`、tag
`preregistration/w0010-archive-epistemology-exit-closure-20260731`へ固定した
`designs/w0010-archive-epistemology-exit-closure-preregistration.json`を、現行normal-run
pipelineへ安全に束縛する。固定manifest SHA-256は
`340c5756715f076cf24a5031715617d50344429a6db72952435c92017364b070`である。

本施工は作品、seed、prompt応答、`works/w0010`、provider callを作らない。実験契約の仮説、
介入、比較、観測、結果分類も変更しない。追加するのは次の実行前条件だけである。

1. experiment provenanceとprotected normal-run予算の単一権威化。
2. `run_budget.version=2`と算出closing reserve。
3. paid run前の独立read-only正式監査条件。

## 2. 深いmoduleとseam

seamは`RealDeps`のseed解釈と`_call_overrides`である。Router、Budget、pipeline各callerへ新しい
分岐を散らさない。

- `run_budget v2`がある場合、予算権威は`run:w0010`だけとする。
- `experiment_id`とarmはcall provenanceとして保持する。
- 同じAPI callへ`experiment:*` scopeを重ねて登録しない。
- `run_budget`がない既存experiment runnerは従来どおり`experiment:*` scopeを使う。
- experimentでないprotected normal runは従来どおり`arm=normal-run`、
  `experiment_id=null`を記録する。

これにより、constraint seamは`seed.experiment.criteria_constraints`、budget seamは
`seed.run_budget`のまま保たれ、両方を使う一走だけが同一call record上で結合される。

## 3. REDからGREEN

旧実装は`experiment.id`と`run_budget v2`を同じseedへ置くと、provider callより前の
`RealDeps.__init__`で`run_budget and experiment budget routing cannot be combined`を送出する。

focused testは、両者を持つseedを構成して旧実装のREDを再現する。候補では次を観測する。

- admissionは`run:w-run`の一scopeだけ。
- L7 API callに`experiment_id`、`arm=main`、`charged_to=run:w-run`、closing reservation IDが残る。
- `experiment:*` scopeは未登録。
- experimentなしprotected runとrun-budgetなしexperimentの既存経路は不変。

## 4. closing reserve

機械可読正本は`designs/w0010-run-budget-v2.json`。全batchの`input_manifest_hash`を固定済み
実験manifest SHA-256へ束縛する。

L7の最悪経路は次の4 slotである。

| slot | kind | input ceiling | output ceiling | 最大額 |
| --- | --- | ---: | ---: | ---: |
| title | external / `author_primary` | 72,000 | 2,048 | $0.8224 |
| publication intent | external / `author_primary` | 32,000 | 16,384 | $1.1392 |
| shelf comparison | external / `author_primary` | 8,000 | 16,384 | $0.8992 |
| final projection | deterministic | — | — | $0 |
| **合計** |  |  |  | **$2.8608** |

単価は`config/models.yaml` SHA-256
`c3388c01bbc7f89ce5e051f98add74c5c026777cd1e9b1e3e12c9f3593a7b9c1`の
`author_primary`、input `$10/MTok`、output `$50/MTok`。各external slotは
`input_ceiling × 0.00001 + output_ceiling × 0.00005`で算出する。

input ceilingは実token見積りでなく、Routerがprecheckに用いるUTF-8 byte upper boundをさらに
包絡する。titleは最大16,004 Python文字の本文構成、publication intentは最大6,004文字の本文構成、
shelf comparisonは現行棚title群と固定promptを覆う。ceiling、単価、model、provider、価格版が
変われば同じ金額でもmanifest identityが変わり、再admissionされない。

closing `$2.8608`は作品cap `$9`と、2026-08-01以降の月次API hard cap `$45`の内数である。
残るplayer `$3.5000`、held-out `$2.6392`は実行上限であり支出目標ではない。closingと異なり、
各生成slotのworst-case購入を約束する額ではない。枯渇時は既存protected completion規則へ従い、
黙って借用・追加課金しない。

## 5. 実行前gate

次をすべて満たすまで`works/w0010`を作らず、有償callを行わない。

1. w0009 shadowと一度だけの正規公開再評価を完了、またはオーナーが明示延期する。
2. 2026-08-01にAPI cap `$45`、公開上限`4`を遡及なしで反映する。
3. 本candidateをClaude Codeがread-only正式監査し、最終非空行`VERDICT: PASS`を返す。
4. formal closure後のclean HEADで、固定manifest・run-budget・model・poetics identityを再現する。
5. 月次残額と作品別残額がrun cap `$9`をadmitできる。
6. `RunBudgetPlan.from_manifest`がclosing `$2.8608`と全slot被覆を再導出する。

有償provider費用照合は実行後best-effort。transport failureがprovider側で課金されたか不明な場合、
推定でmatchedにせず`unreconciled`として残す。

## 6. 監査契約

独立監査はtests-greenとformal verdictを分離し、少なくとも次を確認する。

1. 旧実装REDと候補GREENを独立fixtureで再現する。
2. experiment+run-budgetでbudget authorityが`run:*`一つだけである。
3. call recordにexperiment identity、arm、run charge target、reservation identityが同時に残る。
4. 既存experiment-onlyとprotected-run-only経路が不変である。
5. closing 3 external slotと1 deterministic slotがL7実装を完全に覆う。
6. `$2.8608`が宣言値でなくaxisから導出される。
7. 固定実験manifestのbytesとhashがcommit `aaade52`から不変である。
8. `works/w0010`、作品、poetics、budget config、provider stateが未変更である。
9. P0〜P3 finding、Observed / Inference / Uncertaintyを分離する。

正式監査前のgreenは施工シグナルであり、実行許可ではない。
