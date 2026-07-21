# Phase 5 設計ゲート — 計器、Atlas identity、予算保護

日付: 2026-07-21
設計者: Codex（sol）
状態: **実装前独立設計監査PASS。Phase 5A/5B core実装・独立監査PASS（2026-07-21）。
通常run予算manifestの厳格な入力境界まで着手したが、一括admission・role別routing・closing
settlementは未実装。5C、Atlas再構築、新規有料実走も未着手。**
調査証拠: `reports/PHASE5_READ_ONLY_INVENTORY_20260721.md`
計器定義: `designs/instruments.md`

## 1. 設計ゲートの結論

Phase 5は次の2方向を分けて施工する。

1. **計器とidentityの校正**: 値の由来、比較可否、反例、欠測を一級にする。
2. **欠損を防ぐ実行保護**: held-out評価と閉幕batchを予約し、parse失敗は
   予算問題と別の計器故障として記録する。

新規の深いmoduleは`InstrumentRecord`と`AtlasIdentity`の2つに限る。
`Budget`と`WorkSnapshot`は既存のseamを深くし、wrapperや別readerを追加しない。

## 2. 正典と範囲

この設計は次を実行可能な契約へ落とす。

- `designs/next-designer-execution-plan.md` Phase 5の計器台帳、fixation校正、
  `AtlasIdentity`、L2発生源の期限。
- `PLAN_CHANGELOG.md` 0.7.20-16の外部性三軸、非対称借用、予約付きatomic batch、
  閉幕batch、resource stop分類、`author_epoch`。
- Fable 5の助言にある「予算欠損とparse脆弱性の二層分離」。

### 非目標

- shadow RSI、Author migration benchmark、新作の生成を実行しない。
- 候補Authorまたは費用削減床`X%`を決めない。
- 評価語彙をinner playerの作品promptへ返さない。
- 汎用予算DSL、workflow framework、計器plugin systemを作らない。
- 既存work、colophon、Atlas、FAIL/PASS auditを遡及書き換えしない。

## 3. 依存分類とseam

- 計器の値・比較・校正定義は**in-process + local-substitutable**。
  filesystem fixtureで外向きinterfaceをテストする。
- Atlasはlocal fileとnumpy artifactであり、remote portを作らない。
- providerは既存`Router`adapterの向こうにある。Phase 5はprovider adapterを増やさず、
  `Budget` reservationとparse projectionをprovider呼出し前後の内部seamに置く。
- owner-only批評は意図的にローカル実行interfaceを持たない。記録はPLAN §12.2の
  外部artifact adapterから読む。

## 4. 深いmodule 1 — `InstrumentRecord`

### 4.1 interface

```python
registry = InstrumentRegistry.load(root / "config" / "instruments.yaml")
record = registry.record(
    instrument_id="novelty.atlas_cosine",
    subject_ref="works/w0010/drafts/v1.md",
    value={"nearest_dist": 0.27, "nearest_chunk_id": "..."},
    context=measurement_context,
    evidence_refs=(...),
)
comparison = registry.compare(left_record, right_record)
# comparison.comparable, comparison.delta, comparison.warnings
```

callerが知るのはinstrument id、subject、生値、実行contextだけとする。
module内部に次を隠す。

- registry schemaとstatusの検証。
- 必須model/prompt/identity/confidenceの検査。
- input/evidence hash、measurement id、canonical JSONの作成。
- 欠測、invalid、unclassifiedと0.0の分離。
- instrumentごとの`comparability_keys`と、非比較時のdelta拒否。
- `provisional`計器から自動採用判断へ値が流れることの拒否。

測定計算自体（cosine、正規表現、stddev、logprob、classifier）は各domain実装に残す。
`InstrumentRecord`を巨大な`measure(kind, **kwargs)` dispatcherにしない。

### 4.2 保存

- runtime recordは各workの`measurements.jsonl`へappend-onlyで保存する。
- 複数workを横断するfixation校正は、封印manifestとrecordを
  `reports/calibration/phase5/`に追跡可能artifactとして保存する。
- review・classification・trajectoryの既存artifactは一次証拠として残し、
  `InstrumentRecord.evidence_refs`から参照する。値を引越すために旧artifactを書き換えない。

### 4.3 比較

`registry.compare()`は次のどれかで`comparable=false`にする。

- instrument id/versionが異なる。
- registry hashが異なり、後方互換性が宣言されていない。
- instrument定義のcomparability keyのどれかが不一致または欠落する。
- 一方がmissing/invalid/unclassified。
- `author_epoch`をcomparability keyとする計器でepochが異なる。

非比較recordは並べて表示できるが、delta、勝敗、trendを作らない。

## 5. 深いmodule 2 — `AtlasIdentity`

### 5.1 interface

```python
identity = AtlasIdentity.build(index_dir, build_spec=spec)
identity.hash
identity.verify(index_dir)
comparison = identity.compare(other)
```

`Atlas.load()`、novelty計器、niche report、material card、colophonはこの値を参照する。

### 5.2 決定的payload

identity hashの対象は次とする。timestampや絶対pathはhash payloadから除く。

1. corpus snapshot manifestと各source/license manifestのhash。
2. chunker実装version、設定、chunks schema、`chunks.jsonl`のhash。
3. embedder model revision、tokenizer、quantization、dimension、normalization、
   `embeddings.npy`のhash。
4. PCA/UMAP/HDBSCAN/kNNのalgorithm名・実装version・全build params・seed。
5. Atlas schema versionと関連code version。
6. labels/density/style等の生成artifact hash。

payloadは`state/atlas/identity.json`にcanonical JSONとして書き、Atlas生成artifactの完了後に
最後のcommit markerとする。`Atlas.load()`はidentityとartifactを検証できなければ
比較可能なAtlasとして返さない。

identity一致はbit同一artifactを再利用するときだけ成立する。同じcorpusとbuild specでも、
独立再構築の出力hashが異なれば設計上は別identityであり、比較不能とする。これは上流実装の
非決定性を推測で同一視せず、実際に使ったartifactを比較単位にするためである。

### 5.3 legacy

- 現行Atlasとw0001–w0009を書き換えない。
- 現行のmanifest/meta hashは`legacy_partial_identity`として読み取れるが、
  full identityと比較しない。
- 新しいfull identityは次のAtlas再構築で初めて発行する。旧作に値を推定して遡及記入しない。
- 新identity発行後、別identityのnovelty値を機械判断で比較すると拒否する。

## 6. 既存`Budget`を深くする

予算の新wrapperは作らない。`Budget`のinterfaceへ次だけを追加する。

```python
reservation = budget.reserve_batch(spec, command_id="...")
budget.precheck(..., reservation_id=reservation.id)
budget.charge(..., meta={"reservation_id": reservation.id, ...})
result = budget.settle_batch(reservation.id, command_id="...")
```

### 6.1 `BatchSpec`

manifestで走行前に次を固定する。

- `batch_id`, `scope`, `pool`, `role`, `max_amount`
- expected slot数とslotごとのprovider/modelまたはdeterministic adapter
- input/packet manifest hash
- semantic parse retry回数、transport retryとの分離
- `atomic_projection=true`、完了条件
- protected定義version

poolは`player | held_out | closing`の三つだけとする。owner-only批評はこのinterfaceから
予約・起動・残額照会できない。

manifestが選べるのはcallの所属poolだけである。pool間の借用matrixは`Budget`のcodeに
固定し、manifestやouter loopから設定・緩和できない。

### 6.2 予約不変条件

1. admissionは`spent + active commitments + requested <= hard cap`を満たす場合だけ成功する。
2. active reservationはstateに耐久化し、同じ`command_id`/manifest hashの再試行は同じ予約を返す。
3. `held_out`不足は未予約`player`残額からだけ補充できる。`player`は`held_out`または
   `closing`から借りられない。`closing`は他poolへ借さない。
4. protected pool用callはreservation idなしにproviderを呼べない。
5. chargeは予約残額を減らし、settleは未使用commitmentを解放する。
6. provider実行後の実額が予約を超えたらunreconciledとし、次のcallを拒否する。
   実行済みcallを「無かった」ことにしない。
7. batch開始後の中止は完了ではない。部分証拠は保存し、aggregate projectionは
   `INCOMPLETE_*`として数値勝敗を出さない。
8. 同じ`charge_id`の再記録は既存chargeを返すno-opとし、台帳へ二重appendしない。

事前admissionと事後settlement/recoveryは別seamにする。admissionはprovider実行前なので
拒否できる。実行済みcallのsettlement/recoveryは、予約超過でも記録自体を拒否せず、
chargeを保存して`unreconciled`を立てる。現行`charge()`の`precheck()`送出経路を、
回復注入と実行後settlementに再利用してはならない。

### 6.3 閉幕batch

run開始時に題名、公開意思、公開ゲート、終端event/final投影をmanifest化する。
外部callが必要なslotだけ金額を予約し、event/finalの決定的書込みは無料slotとして
完了条件へ含める。

player残額が次の一巡に足りなくてもclosing予約が残るため、「正常に短く完走」できる。
これをresource interruptionと数えない。

run開始時にclosing予約のadmission自体が成立しなければ、runを開始しない。開始後に
closing commitmentが失われて閉幕不能になれば`resource_interrupted`とする。playerが
途中で尽きても有効なclosing予約で全閉幕条件を満たしたrunだけを`complete_short`とする。

## 7. parse安定性とatomic projection

budget reservationはparse失敗を解決しない。次を別に実装する。

1. juror slotごとにcall/charge/raw response hashとparse結果を直ちにappendする。
2. aggregate scoreはexpected slotすべてが事前登録条件を満たした後だけ投影する。
3. semantic parse retryはmanifestの回数だけ予約に含める。未登録の裁量再生成を禁止する。
4. transport retryは既存Routerのprovider retryとして分離し、semantic retryと合算しない。
5. parse failureは`parse.reliability`の証拠とする。評価予算の欠損と報告項目を分ける。

w0009の既存artifactは不変の反例fixtureとし、同じIDでscoreを復元・再生成しない。

## 8. 既存`WorkSnapshot`を深くする

`WorkSnapshot`に次の読み取り属性を追加する。

```python
termination: TerminationSnapshot | None
author_epoch: str | None
```

`TerminationSnapshot` は`stop_path`、`category`、`reason`、source event/refを持つ。
categoryは既存の四分類だけとする。

- `aesthetic_failure`
- `resource_stop`
- `publication_choice`
- `safety_or_rights`

modern workの最小写像は次で固定する。

| source signal | category |
|---|---|
| `stop_path=budget`または予算・予約による閉幕不能 | `resource_stop` |
| 品質床・美的退行・詩学不適合によるSHELVE | `aesthetic_failure` |
| L7 `failure_category:publication_choice`または公開しないという完了済み判断 | `publication_choice` |
| 安全・権利・ライセンス上の停止 | `safety_or_rights` |

modern workではtransition payloadの`stop_path`とL7の`failure_category:*`を厳密に突合する。
不一致はwarningで隠さない。legacy workは既存理由からの推定をdisplay adapterとして
行えるが、provenanceを`legacy-inference`とし、自動negative map入力に使わない。

`author_epoch`はcolophon/provenanceの一属性だけとする。状態機械、experiment event、
新moduleにしない。旧作は欠損のままで、後継Author採用後の新workから必須にする。
`RepositorySnapshot`はepochをまたぐ計器集計にwarningを出し、勝敗を自動生成しない。

public site、negative map、fixation校正は`WorkSnapshot.termination`を読み、
`resource_stop`を美的失敗標本に入れない。

## 9. fixation初回校正

校正は既存artifactだけで開始できる。新規有料callは不要である。

### sealed fixture

1. w0004の「〜ほど」警句機関。
2. w0005の弁証法的往復。
3. w0007の職能語彙と統一比喩網。
4. w0008の箇言調の「引用への変換」。
5. w0008/w0009の`backstage_world`と意味核・ニッチ文面の反例。

各fixtureに「表層反復」「構文/修辞装置」「世界型」「役割変換」をowner/Fableの
既存批評由来でlabelし、新classifierの最適化用稿に使わない。

### 採用ゲート

- `fixation.poetics_lexical`の狭い主張は保持する。house-style監視と改名せず混同しない。
- `fixation.house_style`は、3作横断の衣裳替え反復を見逃さず、w0008の引用変換を
  無条件の解決と数えないまで`provisional`とする。
- classifierの学習/改稿と校正評価を同じfixtureで行わない。標本が少ない間は
  定量的精度を主張せず、反例と不一致を保存する。

## 10. L2発生源の期限

0.7.19-1の期限は変更しない。拡張後最初の2作、遅くとも2026-09-30までに、
ニッチ報告有無がL4構成案分布を実質的に変えることを示す。

ただし、この期限実験はfull `AtlasIdentity`、登録済み計器、protected reservationが
利用可能になるまで開始しない。期限自体を自動延長しない。

## 11. 失敗model

- registry欠落、schema不正、identity欠落は外部call前に拒否する。
- 計器record書込み失敗後に、同じ有料callを自動再生成しない。call証拠から
  `INCOMPLETE_PROJECTION`として回復する。
- Atlas identityとartifactが不一致ならAtlas読込みをfail closedする。
- active reservationを無視したprecheck、重複settle、manifestの異なるcommand再利用を拒否する。
- batchの一部slotだけでmean、disagreement、argmaxを生成しない。
- resource stopをaesthetic failureに落とす分類不明は、negative map書込みを拒否する。
- cross-atlas、cross-epoch、cross-roster/modelはrecordを消さず、比較だけを拒否する。

## 12. tracer-bullet施工順

### Phase 5A — 記録と比較の床

1. `config/instruments.yaml`と`InstrumentRegistry/InstrumentRecord`を公開interface testから作る。
2. `AtlasIdentity`のcanonical payload・verify・compareを小さなfixtureで作る。
3. `WorkSnapshot.termination/author_epoch`とRepositorySnapshot warningを作る。
4. 既存値を書き換えず、legacy record adapterと調査reportを作る。

### Phase 5B — 実行保護

5. `Budget.reserve_batch/settle_batch`とpoolの非対称借用を故障注入で作る。
6. juror slotの逐次硬化とatomic aggregate projectionを作る。
7. held-out評価batchとclosing batchを通常run/experiment manifestへ配線する。
8. owner-only費用・起動権が自動status/reservationから不可視であることをtestする。

### Phase 5C — 校正

9. fixation sealed fixtureと既存計器のbaselineを固定する。
10. 新Atlasをlocal再構築し、full identityを最初に発行する。
11. novelty、disagreement、mean logprob、parse reliability、completion、costの
    `InstrumentRecord`配線と反例検証を行う。
12. 全受入条件を実データread-only auditと故障注入で確認する。

各subphaseは前subphaseのinterfaceだけを読む。各callerがregistry、identity payload、
pool残額を独自解釈してはならない。

## 13. 受入条件と故障注入

1. **台帳**: 全計器が主張、入出力、版、校正日、反例、盲点、次条件を持つ。
2. **record**: 全出力にmodel、prompt、identity、confidence、evidenceが付く。
3. **比較**: Atlas/model/prompt/roster/epochの不一致でdeltaを返さない。
4. **Atlas**: corpus/chunker/embedder/params/code/artifactのどれか1 byteを変えるとidentityが変わる。
5. **legacy**: 既存Atlas/workを書き換えず、partial/missing identityをwarningにする。
6. **fixation**: 旧lexical計器の狭い主張とhouse-style計器を分け、初期反例をすべて登録する。
7. **reservation**: check後に他callを挿入してもprotected batchのcommitmentが消えない。
8. **借用**: player→held-outだけが通り、held-out/closing→playerとclosing→他poolは拒否される。
   manifestに借用許可fieldを注入しても拒否または無視され、code固定の非対称matrixが維持される。
9. **closing**: player不足のfixtureが閉幕予約で題・公開判断・終端まで完了する。
10. **parse**: 3-slot中最後のparseを壊しても前2-slotの証拠が残り、aggregateは
    `INCOMPLETE_PARSE`でmean/argmaxを返さない。未登録retryは行われない。
11. **SHELVE**: w0009をresource stop、w0007型品質床をaesthetic failureと読み分け、
    resource stopはnegative map/fixationの失敗作標本に入らない。
12. **owner-only**: 自動ループが起動、文面変更、残額照会を行えない。批評内容の後続流入は許す。
13. **epoch**: 欠落legacyを書き換えず、cross-epoch集計にwarningが出る。
14. **回復**: reservation後、call後、parse後、record append後の各故障で再開しても
    重複課金、二重settle、虚偽の完了projectionを作らない。
15. **実額超過**: 予約を超えた実行済みcallを回復注入してもcharge recordを保存し、
    `unreconciled`を立てる。記録前に`BudgetExceeded`で捨てない。
16. **charge冪等性**: 同一`charge_id`を再生すると既存行を返し、spentとcharge行数を増やさない。
17. **終了境界**: closing admission失敗、開始後のclosing喪失、player枯渇かつclosing生存を
    それぞれ未開始、`resource_interrupted`、`complete_short`として混同しない。

## 14. 検証と監査ゲート

### 実装前

- 本設計、計器台帳、read-only調査を、施工者Codexと異なるClaude Code担当が
  read-onlyで監査する。
- 2026-07-21、Claude Code（Opus 4.8）の別セッションが独立検証し、P0–P2なし、
  P3警告6件、`VERDICT: PASS`とした。candidate commit/staged treeは未固定だったため、
  これは設計ゲートの判定であり、実装後の正式milestone監査を代替しない。監査記録は
  `reports/PHASE5_PREIMPLEMENTATION_DESIGN_AUDIT_20260721.md`。
- P0–P2または`VERDICT: FAIL`があれば、そのartifactを保存し、設計を修繕して
  同じ監査者の再監査を受ける。

### 実装後

- focused acceptance、全non-local、`git diff --check`、実データread-only audit、
  上記故障注入を分けて記録する。
- `designs/formal-audit-runbook.md`に従いcandidateをcommitまたはstaged treeで固定する。
- Codex施工のため、正式milestone監査はClaude Codeの別担当が行う。PASSまでPhase 6へ進まない。

## 15. 設計後にも残る未決

- house-style classifierのmodel/prompt、人間labelとの最低合意床。
- semantic parse retryの既定回数（0または1）。batchごとに事前登録が必要。
- closing予約の金額。w0009の実測は見積りfixtureにできるが、永久値にしない。
- 次Atlasのcorpus拡張有無。identity実装と拡張の価値判断は分ける。
- Author候補と費用削減床`X%`。Phase 5完了後のオーナー判断とする。

これらを未決のままにすることは、本設計の不完全さではない。数値とmodel選定を
観測前に固定せず、決めるためのinterfaceと証拠条件を先に固定する。
