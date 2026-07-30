# w0009 publication入力長shadow runner

**状態**: `IMPLEMENTED / INDEPENDENT AUDIT PENDING`

**凍結済み事前登録commit**:
`8a5bd48`（`preregister w0009 publication input shadow`）

## 1. 目的とscope

`designs/w0009-publication-input-shadow-preregistration.md`を変更せず、
機械可読manifestを検証して一組のshadowを一度だけ実行できるrunnerを作る。
本施工はcampaignで許された「次runの直接blocker」であり、新作、公開再評価、
詩学改訂、汎用実験frameworkを含まない。

runner候補の独立監査がPASSするまで有償callを許さない。監査PASS後も、
2026-08-01のAPI cap `$45`と公開上限`4`の反映前には実行しない。

## 2. moduleとinterface

深いmoduleは`aleph.meta.publication_shadow.PublicationShadow`とする。

- `PublicationShadow.open(root)`: manifestを読み、全identityを再構成する。
- `verify()`: 本文選択、全文・抜粋・省略区間、棚、prompt、schema、Author role、
  価格宣言、canonical w0009非変更面を照合する。
- `execution_blockers()`: 日付、月次API cap、公開上限の未充足をread-onlyで列挙する。
- `run(adapter, ...)`: reserve、二つのintent、条件付き棚比較、strict parse、raw保存、
  token/費用/latency集計、settlement、canonical非変更再照合を一回で行う。

外部seamは`ShadowAdapter`一つだけとする。productionでは`BudgetRouterAdapter`、
testではfake adapterを用いる。callerへprompt組立て、hash、parser分類、保存順を漏らさない。

## 3. call順序とretry

主比較を欠損させにくくするため、固定packet順で二つのintentを先に完了し、その後に
`publish=true`となったpacketの棚比較を同じpacket順で行う。各callは無状態であり、
先行応答を後続promptへ渡さない。

既存`Router`はtransport失敗を固定3 attemptとしていた。事前登録のretry 0を守りつつ
全既存callerを変えないため、`transport_retries` overrideを追加する。

- 未指定: 従来どおり2 retry、最大3 attempt。
- shadow: `transport_retries=0`、最大1 attempt。
- bool、負数、非整数はprovider call前に拒否する。
- 実値はcalls logの`params.transport_retries`へ残す。

semantic retryと文章fallbackはshadow module内に存在しない。

## 4. 予算とprovenance

最初のcall前に、4 slotのworst-case `$3.9968`を一つのprotected closing batchとして予約する。
未発火の棚比較分は終了時にsettleして解放する。

課金work identityはcanonical `w0009`ではなく`w0009-publication-shadow`とする。
既存w0009の作品別累積費用とshadow reserveを混ぜず、`experiment_id`と`charged_to`で
w0009 shadowとして追跡する。全callは同じreservation IDを持つ。

provider cost statementは自動取得できないため、config宣言による実usage計算を保存し、
provider照合は`UNAVAILABLE_PENDING_BEST_EFFORT`から開始する。取得不能を一致扱いしない。

## 5. 成果物とblind

実run時だけ`works/w0009/publication_shadow/results/`を新規作成する。

- `calls.jsonl`: Routerのcall・charge provenance。
- `attempt.json`: reserve直後・最初のprovider call前に作るat-most-once marker。
- `responses/<packet>-intent.txt`: scrub済みraw response。
- `responses/<packet>-shelf_comparison.txt`: 発火時だけ。
- `observations.json`: parse、判断、usage、費用、latency、settlement、監査identity。
- `blind_middle_annotation_packet.json`: body mappingを含まない中盤参照採点packet。

既存results directoryがあればreserve前に拒否し、二重runを防ぐ。blind採点が完了するまで
runnerはexcerpt/full mappingを結果側へ書かず、packet選択を`PENDING`に保つ。

canonical `checkpoint.json`、`decisions.jsonl`、`calls.jsonl`はrun前後でhash照合し、
変化があれば完了扱いにしない。

## 6. CLI gate

read-only確認:

```bash
uv run python scripts/run_w0009_publication_shadow.py verify
```

有償実行には、次のすべてを要求する。

```bash
uv run python scripts/run_w0009_publication_shadow.py run \
  --execute-paid \
  --audit-report /path/to/read-only-audit.md \
  --candidate-commit <audited-clean-HEAD>
```

- audit reportの最終非空行が厳密に`VERDICT: PASS`
- report本文がcandidate commitとtreeを明記
- candidate commitがcurrent HEAD
- worktreeがclean
- 事前登録identityが全一致
- 日付、API cap、公開上限、予算reserveが成立

いずれか一つでも不成立ならprovider call前に停止する。

## 7. 受入条件

1. 現repositoryのmanifest全identityを再構成できる。
2. 2026-07-30時点では日付、`71`、`999`の三blockerを表示し、実行不能。
3. fake adapterでintentはpacketごとに一度、常に棚比較より先に呼ばれる。
4. 棚比較はstrict parse成功かつPUBLISHのpacketだけ一度呼ばれる。
5. JSONのない「公開する」文章をPUBLISHへfallbackしない。
6. stimulus/canonical hash driftをreserve前に拒否する。
7. results既存時はreserve前に二重runを拒否する。
8. transport retry 0でprovider attemptが一回、未指定時は従来の最大三回。
9. shadow reserveはcanonical w0009でなく専用work identityへ帰属する。
10. raw、parse、decision、棚比較、token、費用、latency、settlement、監査identityを保存する。
11. focused、全non-local、compileall、diff checkがgreen。

## 8. 非目標

- 今この施工で有償callを行うこと
- 中盤参照をCodexが先取り採点すること
- shadow結果なしに6,000字／全文を選ぶこと
- 現行棚比較promptの本文欠落を同時修繕すること
- 正規`aleph publish`、publication disposition、final、siteを変更すること
- 2026-08-01より前にbudget/publish configを変更すること
