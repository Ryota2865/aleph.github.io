# w0009 6,000字抜粋／全文 publication shadow 事前登録

**状態**: `PREREGISTERED_NOT_RUN`

**事前登録日**: 2026-07-30

**実験ID**: `exp-w0009-publication-input-shadow-v1`

**機械可読manifest**:
`works/w0009/publication_shadow/preregistration.json`

## 1. 地位と目的

本書は`designs/post-phase6-aug-sep-literary-campaign.md` §6を具体化する。
新作生成でもw0009の再生成でもなく、既存採用稿への公開意思確認で使う入力packetを選ぶための
一組だけのshadow比較である。一般的な長文入力性能、Fable 5の安定性、作品群全体の最適な
抜粋長は主張しない。

分離して観測する問いは二つだけとする。

1. 現行6,000字構成と全文とで、strict JSON parseの成否が異なるか。
2. 現行6,000字構成が、w0009の公開判断に関係する中盤情報を失うか。

house-style人間annotationは本事前登録より先に完了したが、campaignの実施順に含まれる
別protocolであり、w0009のモデル応答はまだ存在しない。annotationの回答、合意率、難度所感は、
本比較のarm、prompt、採点規則、packet選択へ入力しない。

## 2. 凍結する一次情報

### 2.1 候補本文

- 採用規則: `reviews/trajectory.jsonl`で`mean_score`最大のversion。
- 選択結果: `works/w0009/drafts/v2.md`、`mean_score=9.233333333333333`。
- v1、v2、v3は同一bytesであり、本文選択の曖昧さはない。
- 全文: 11,139 Python文字、32,903 UTF-8 bytes。
- 全文SHA-256:
  `1b351e11fad55967c7f7f7821c1fc5e72e3092b15a61dcbbbe416e97c755649c`
- trajectory SHA-256:
  `cf9b7b4194926b8524dbb5091fb68bd0b235fde622ef6a63fe0a58e96321177d`

現行6,000字構成はproduction helperと同じく、
`text[:4000] + "\n……\n" + text[-2000:]`とする。separatorを含むため実長は6,004文字である。

- 抜粋SHA-256:
  `117e23b7d006de3d17d1de24300863aac438e1dabb4d957df295ed2ef9f6e3ee`
- 省略区間: 元本文のPython文字offset `[4000, 9139)`、5,139文字。
- 省略区間SHA-256:
  `ebd4e077a7b2919a34bdf83d149b42e773e3fa407c05b40b517e2bb8a840a7f8`

### 2.2 固定条件

- 想定読者配合: `LLM 0.15 / 人間 0.35 / 自分 0.5`
- 棚summary（この順、LF結合、末尾LFなし）:
  `半呼吸`、`床の硬さ`、`灯のうしろ`、`折り目`、`暗い側`
- 棚summary SHA-256:
  `5fd4e47da44efcb02c48c05d61a7fe7edff11b54d784e4e1fa5de326866c1c59`
- Author role: `author_primary`
- provider/model: `anthropic` / `claude-fable-5`
- `max_tokens=16384`、temperature指定なし
- 価格: input `$10.00/MTok`、output `$50.00/MTok`
- 価格版identity:
  `config/models.yaml` SHA-256
  `c3388c01bbc7f89ce5e051f98add74c5c026777cd1e9b1e3e12c9f3593a7b9c1`
  の`roles.author_primary.pricing`
- provider明細との照合は実行後best-effortとし、取得不能なら
  `provider_reconciliation=UNAVAILABLE`を残す。config宣言との計算一致とprovider照合を
  混同しない。

## 3. arm、blind、順序

モデルへA/B、excerpt/full、対照/介入という名前を渡さない。内部packet IDだけを記録する。

| 内部packet ID | 実体 | prompt SHA-256 |
|---|---|---|
| `packet-db058b2776b4` | 現行6,004文字構成 | `28e78a2b56463a0d27accdac102b8960acbb2412eabef93a119fdaa269f480ae` |
| `packet-be6c78477dfd` | 全文 | `2802adbddc2964546be4a8f81874c34d7202385e013984bec4872ac0ef4617f6` |

順序seedは`w0009-publication-input-shadow-v1|2026-07-30`とし、固定順は
`packet-db058b2776b4`、`packet-be6c78477dfd`である。各callは別の無状態requestとし、
会話履歴、先行armの応答、arm名、比較目的をmessageへ含めない。

結果の中盤参照を採点する者には、二つのraw responseが固定されるまでpacket mappingを見せない。
mapping解除時刻と担当を結果manifestへ記録する。

## 4. prompt、schema、parse

### 4.1 公開意思call

公開意思promptは現行
`aleph.meta.publication_gate._ask_publish_intent`の組立てをそのまま用いる。
二arm間で変えてよいのは`作品（抜粋）:`後の本文bytesだけである。全文armでも見出し文言は
互換性のため変更しない。

schemaは次の二つを必須fieldとする。現行parserは未知fieldを拒否しないため、追加fieldがあっても
この二fieldが型どおりならparse成功とする。この挙動もshadow中に厳格化しない。

```json
{"publish": "bool", "reason": "str"}
```

schema identityは上記一行をUTF-8化したSHA-256
`ba40bab68fc91e1f047273d8b8129f5b5622c9e608742582c89a2538a5914f1b`
である。

判定には`parse_model_output(..., fail_closed=True)`だけを使う。現行productionの
文章fallback（「公開する」「非公開」等の語彙推定）は、JSON parseの成否を隠すためshadowでは
使用しない。parse失敗はSHELVEへ読み替えず`PARSE_INCOMPLETE`とする。

結果には少なくとも次を保存する。

- raw responseのUTF-8 bytesとSHA-256
- parserの`ok`、`fragment`、`source_span`、warnings
- `PARSED | NO_JSON | DUPLICATE_KEY | MULTIPLE_JSON | SCHEMA_INVALID`
- parse成功時だけ`PUBLISH | SHELVE`

複合warningはraw tupleを権威とし、上の分類は表示用の一値である。

### 4.2 棚比較call

現行productionと同じく、公開意思がstrict parse成功かつ`publish=true`のarmだけ、次の
棚比較callを一度行う。prompt SHA-256は
`f762ea9cdc54ac7aee3fbae26f7ecef8f98e2b645462d4c4a76b14cad902bf81`
である。free textをそのまま保存し、semantic retryもparseも行わない。発火しないarmは
`NOT_TRIGGERED`と記録する。

この現行棚比較promptは作品本文を含まず、無状態callである。したがって棚比較出力は
`SPECIFIC | GENERIC_OR_UNGROUNDED | NOT_TRIGGERED`として観測するが、6,000字／全文の
packet選択根拠には使わない。これはshadow中に黙って修繕せず、正規再評価前の
直接blocker審査へ回す。

## 5. 中盤情報の採点

各parse成功armの`reason`について、blind採点者が次を記録する。

- `middle_reference`: `YES | NO | UNCERTAIN`
- `decision_relevant`: `YES | NO | UNCERTAIN`
- response側の根拠quote
- 元本文側の根拠quoteとPython文字offset

`middle_reference=YES`にできるのは、reasonが具体的な出来事、物、関係、認識の変化を指し、
その根拠が省略区間`[4000, 9139)`内に完全に存在し、先頭4,000字と末尾2,000字だけからは
同じ具体性で得られない場合だけである。作品全体の主題を言い換えただけ、一般的な長所短所、
Fable 5の既存批評に偶然似た表現は`YES`にしない。

採点者はreasonから元本文への対応を示せない場合`NO`、複数箇所に跨がり省略区間固有性を
確定できない場合`UNCERTAIN`とする。`decision_relevant=YES`は、その中盤情報が
PUBLISH/SHELVEの理由を実質的に支えている場合だけとする。結果を見た後で新しい判定軸を
追加しない。

## 6. 事前固定したpacket選択規則

1. 両armがparse失敗: `INCONCLUSIVE_PARSE`。正規再評価を行わない。
2. 一方だけparse成功: parse成功側を正規再評価packetとして選ぶ。
3. 両方parse成功で判断が一致:
   - 全文reasonが`middle_reference=YES`かつ`decision_relevant=YES`なら全文。
   - それ以外は現行6,000字構成。
4. 両方parse成功で判断が不一致:
   - 全文reasonが`middle_reference=YES`かつ`decision_relevant=YES`なら全文。
   - それ以外は`INCONCLUSIVE_DECISION`とし、正規再評価を行わない。
5. `UNCERTAIN`を`YES`へ繰り上げない。棚比較の質、latency、安価だった側、ownerの好みで
   上の規則を上書きしない。

全文が選ばれた場合、それはproduction変更の自動承認ではない。
`aleph publish`が選択packetを渡せる最小変更、test、独立監査を完了してから正規再評価する。
6,000字が選ばれた場合も、既知の棚比較prompt問題が直接blockerでないかを別に審査する。

## 7. 費用包絡と停止

semantic retryとtransport retryはいずれも0、各slotのattemptは1回だけとする。
条件付き棚比較を両armが発火する最悪時まで、最初の有償call前にまとめて予約する。

| slot | input token ceiling | output token ceiling | slot max |
|---|---:|---:|---:|
| excerpt intent | 24,000 | 16,384 | $1.0592 |
| full intent | 40,000 | 16,384 | $1.2192 |
| excerpt shelf comparison | 4,000 | 16,384 | $0.8592 |
| full shelf comparison | 4,000 | 16,384 | $0.8592 |
| **合計** | **72,000** | **65,536** | **$3.9968** |

この$3.9968は8月のAPI hard cap $45の内数であり、別枠ではない。実行は2026-08-01以降、
`api_usd_per_month=45`と`publish.max_per_month=4`の期限actionが正しく反映され、
月次残額とshadow reserveが成立した後に限る。reserve不成立、identity不一致、片arm終了後の
cap不足、provider/model差替え、価格版変更があれば、有償call前またはその時点で停止する。
片armだけの結果から主判定を出さない。

## 8. 非変更契約と実施ゲート

shadow中は次を変更しない。

- `works/w0009/checkpoint.json`とlifecycle `SHELVE`
- `works/w0009/decisions.jsonl`とpublication disposition
- `works/w0009/drafts/`、`final/`、公開site
- 既存`works/w0009/calls.jsonl`
- 詩学、作品、house-style annotation結果

変更を許すのは、承認済みrunnerによるshadow専用結果、必要な費用台帳、provider usage記録だけ
である。runnerはまだ本事前登録に含まれない。

実run前に、runnerが本manifestの全hash、無状態call、順序、retry 0、$3.9968 reserve、
非変更契約、raw response保存を機械検証できるよう施工し、Codex施工とは独立した
Claude Code read-only監査でPASSを得る。監査前、有償call、local inference、公開再評価は
行わない。

## 9. 正規再評価

shadowがpacketを一意に選び、必要なproduction変更と監査が閉じた場合だけ、既存
`aleph publish`経路で一度だけ正規再評価する。w0009のlifecycleは`SHELVE`のまま維持し、
publication dispositionを追記する。shadow応答を正規判断として転記せず、第五査読、
陪審再採点、本文再生成は行わない。
