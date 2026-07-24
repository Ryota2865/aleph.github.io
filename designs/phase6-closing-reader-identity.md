# Phase 6 closing reserve・reader tokenizer identity

日付: 2026-07-24
状態: 初回formal audit FAIL保存、同一監査者focused再監査PASS
設計者・施工者: Codex
正本: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-22〜24、
`designs/next-designer-execution-plan.md` §6.0

## 1. 範囲

Phase 6の外部run前gateとreader計器利用前gateを、外部callを伴わない二つのtracer bulletで
閉じる。新作、有償run、provider statement adapter、house-style annotation、Author移行、
Atlas変更は範囲外とする。costのprovider側照合はbest-effortのまま維持する。

## 2. Closing reserve

新しいprotected normal runは`run_budget.version=2`とし、closing batchの
`expected_slots`を`closing_slots`がちょうど一度ずつ被覆する。

- `external`: `provider`、`model`、`pricing_version`、課金`axes`を持つ。
- 各axis: `name`、整数`unit_ceiling >= 0`、有限`usd_per_unit >= 0`。
- `input_tokens`と`output_tokens`は必須。cached input、reasoning、固定call料等は追加axisで
  同じ価格版へ含める。
- `deterministic`: slot/batch/kindだけを持ち、最大費用0 USD。

算出は次の一箇所で行う。

```text
slot_max = sum(axis.unit_ceiling * axis.usd_per_unit)
closing_reserve = sum(slot_max)
```

各closing batchの算出値と`max_amount`、全slot合計とclosing poolが1e-9 USD以内で一致する
場合だけ受理する。未知field、欠落slot、重複slot、非closing batch参照、価格版/model/provider
欠落、bool・NaN・負値を拒否する。

完全なv2 manifestのcanonical hashと`phase6-run-budget-v2`を全BatchSpecへ束縛し、
reservation identityと耐久stateへ保存する。同じcommand IDでprovider/model/価格版/axis/
ceiling/slot/versionのいずれかが変われば、算出額が同じでも再admissionとrestart再水和を拒否する。
v1は履歴解釈用にparseできるが、checkpointの有無・内容にかかわらずprotected normal runの
admissionには使用できない。gateは`RealDeps`だけでなく`Budget.admit_run_plan`にも置く。

## 3. Reader tokenizer identity

GGUFから次を抽出する。

- scalar: tokenizer model/pre、BOS/EOS/PAD、add-BOS、chat template
- ordered arrays: tokens、token types、merges
- tokenize実装: llama.cpp commit

配列はitem typeと値をcanonical JSON化し、8-byte length prefixを付けて順序どおりSHA-256へ
流す。artifact全体もcanonical SHA-256でtamper evidentにする。GGUFのファイル名・mtimeは
identity材料にしない。model artifact/quantization identityはこのtokenizer identityへ混ぜず、
reader model identityとして別に保持する。

現在の発行値:

- reader alias: `Qwen3.6-27B-Q4_K_M`
- identity: `af98a8928972c29a99be5604daff1afaff411a1ace658cfae1935500e1e799a0`
- llama.cpp: `d77599234ea6e498775aeadbce665eece5bd98cd`

runtimeはartifact hashとreader aliasが一致した場合だけ
`gguf-tokenizer:<identity>`をmeasurementへ入れる。欠落、改変、schema不一致、alias不一致は
`provider-default:<model>:unverified`へ倒す。そのrecordは比較可能なtokenizer identityを
持たない。

## 4. 受入・停止条件

受入:

1. 算出reserve、closing batch、closing poolの一致が自動検証される。
2. 価格・ceiling・課金軸・slot被覆の欠陥がprovider call前にfail closedする。
3. metadata配列順序またはllama.cpp revisionの変更でtokenizer identityが変わる。
4. artifact改変とreader alias不一致でverified identityを主張しない。
5. 全non-local回帰がgreenである。

初回正式監査tree `14772732aa87d1cfde6afd9a25493686bbc213f6`はP2を2件検出してFAIL。
原文は`reports/PHASE6_CLOSING_READER_IDENTITY_AUDIT_20260724_FAIL.md`。修繕はv1 admissionの
全面拒否と完全manifest identityの耐久化に限定し、同監査のP3群は残置リスクとして保持する。
修繕tree `b93a518c7cd27720456358d63b4a4026b1980b33`は同一監査者のfocused再監査で
P0–P2なし、`VERDICT: PASS`。原文は
`reports/PHASE6_CLOSING_READER_IDENTITY_P2_REAUDIT_20260724.md`。P3-1〜P3-10と
有償provider実費経路未検証はformal PASS後も残置する。

停止:

- GGUFに登録済み必須metadataがなければidentityを推測せず発行を停止する。
- provider固有課金軸を最大額へ包絡できなければv2 manifestを受理しない。
- formal milestone完了は`designs/formal-audit-runbook.md`に従う独立監査PASSまで主張しない。
