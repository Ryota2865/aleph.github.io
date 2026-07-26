# Phase 6後 2026年8–9月 文学的帰還campaign

日付: 2026-07-26
設計者: Codex
地位: **オーナー承認済みの期限付き運用方針**
入力:

- `reports/FOR_FABLE5_POST_PHASE6_AUTHOR_CRITIC_BUDGET_20260725.md`
- `reports/FABLE5_RESPONSE_POST_PHASE6_AUTHOR_CRITIC_20260726.md`
- 2026-07-26のオーナー決定

## 1. 目的

Phase 5–6で整備した予算予約、終端、計器、formal audit、repository current-stateを、
新しい文学的runへ戻して検証する。2026年8–9月は、非blockingインフラの追加より、
作品生成、外部批評、帰還の回復を優先する。

このcampaignは恒常運用ではない。Fable 5をClaude Proのowner-only手動批評路で利用できる
期限付き期間に、作品と批評の証拠を集める二か月の例外である。2026年10月にCodexが通常の
設計・施工へ復帰し、得られた証拠からAuthor、費用、探索方法を再審査する。

## 2. 役割と変更停止

- **Author**: Author migration benchmarkまでは現行frontier Authorを維持する。
- **Critic**: Fable 5のowner-only全文脈批評を優先する。次回の最優先用途はAuthor
  migration benchmarkのblind帰還批評とする。
- **Codex**: 8–9月も利用可能な状態を維持するが、作業を次runの直接blocker、批評への
  帰還、正典・provenance、正式監査closureへ限定する。
- **独立監査**: 有償runのmanifestと、そのrunに必要な実装は施工者と別の担当が監査する。

Phase 6完了後、次の文学的runまで、新しい非blockingインフラ機構を既定で開始しない。
例外は安全、期限、正式監査finding、次runの直接blockerに限る。AIDE²型shadow最適化と
corpus拡張は当面開始しない。

これは安全修繕やrun前gateを禁止する機械的cadence規則ではない。既存の
`OPERATIONS.md`「設計変更の門」を、文学的証拠が不足する期間の優先順位へ適用する。

## 3. 頻度の語彙

「月N作」は**完成数**を指す。生成、完成、公開を混同しない。

| 面 | 8–9月の目安・上限 |
|---|---:|
| 生成（L4–L5到達） | 月1–2 |
| 完成（L6–L7とclosing完了） | 月1–2 |
| 公開実績 | 月0–1 |
| 公開上限 | 月4 |

二か月で通常の有償文学runを3–4件程度想定するが、ノルマではない。SHELVEを正常終端、
PUBLISHを例外とする比率を維持する。Author migration benchmarkは通常作品数に算入せず、
独立したexperiment scopeと費用包絡を持つ。

## 4. 期限付き費用

2026年8月と9月の月次最大包絡:

| 枠 | 月額 |
|---|---:|
| Claude Pro | $20 |
| ChatGPT Plus / Codex | $20 |
| 従量API hard cap | $45 |
| 合計 | $85 |

- $85は二か月限定の最大包絡であり、支出目標ではない。
- Fable 5のClaude Pro限定クレジットはowner-only別枠として注記し、従量APIへ合算しない。
- 従量APIは各runのmanifestで、provider/model、価格版、token上限、closing slotから
  worst-case費用を予約する。過去平均だけでadmitしない。
- 2026-07の`api.usd_per_month=71`と実績は遡及変更しない。
- `config/budgets.yaml`のAPI cap 45と公開上限4への変更は2026-08-01に行う。
- 2026年10月にサブスクリプション込み月$60基線を再審査する。Author benchmark、
  実費、批評頻度から恒常hard capを決め、$85を自動継続しない。

## 5. 実施順

### 2026-07-26〜31

1. 本campaignとFable 5回答を正典・記録へ保存する。
2. `fixation.house_style`用の短い抜粋12組を準備する。
3. w0009公開判断の6,000字抜粋／全文shadow比較を事前登録する。
4. w0010「アーカイブ認識論の出口封鎖」のmanifest、closing reserve、監査packetを準備する。
5. 直接blocker以外の実装は開始しない。

### 2026-08

1. `publish.max_per_month`を999から4、`api.usd_per_month`を71から45へ変更する。
2. ownerを含む2名でhouse-style blind labelを実施する。
3. w0009入力長shadow比較を実施し、その結果に基づき正規公開再評価を一度だけ行う。
4. w0010を最初の文学的tracer bulletとして実施する。
5. 予算、closing reserve、批評の帰還が許す範囲で後続runを行う。

### 2026-09上旬

1. 承認済み最低線を満たすAuthor migration benchmarkを独立scopeで実施する。
2. Fable 5へAuthor名を隠した全文脈packetを渡し、帰還批評を得る。
3. 品質床、改稿応答、費用、完走、parse、家風分散からAuthor epochを判断する。
4. benchmarkが間に合わない場合、残るFable 5機会は詩学第2版審査へ振り替える。

### 2026-10

1. Codexが通常の設計・施工へ復帰する。
2. 月$60基線、Author epoch、Critic頻度を実測から決める。
3. 8–9月の作品と批評を入力に、open-ended operator searchを次期設計主題として審査する。

## 6. w0009入力長shadow比較

目的は、長文入力のtransport可否ではなく、次の二面を分離して観測すること:

1. 入力長がJSON parse成功へ影響するか。
2. 現行6,000字抜粋が公開判断に必要な中盤情報を失うか。

最低契約:

- w0009採用稿、棚summary、prompt、schema、Author model、価格版をhash固定する。
- Aは現行6,000字（先頭4,000字＋末尾2,000字）、Bは全文とする。
- A/B名を隠し、独立した無状態callとして提示する。semantic retryは0。
- JSON parse、`PUBLISH/SHELVE`、理由の中盤参照、棚比較、token、費用、latencyを記録する。
- shadow比較中はcheckpoint、publication disposition、final、公開siteを変更しない。
- 一組の比較から一般的な長文契約を主張しない。w0009の正規再評価に用いるpacketを決める
  tracer bulletとする。
- 正規再評価は既存`aleph publish`経路を用い、SHELVE lifecycleを維持したまま
  publication dispositionを追記する。

## 7. 探索仮説

### 7.1 ニッチ探索とデータの外側

Corpus niche searchは探索座標を増やすが、探索演算子そのものを変えない。全データを
収集しても、既存点間の探索だけで未知領域へ到達できる保証はない。

実験主体への転換は、観測された失敗や固着から制約を生成し、探索演算子を変える一つの
有力な方法である。ただし最終解とは扱わない。2026年10月以降、作品座標だけでなく、
制約生成、環境、変異、stepping stone、外部摂動を探索対象にする
**open-ended operator search**を設計仮説として検討する。現時点で新機構を承認したものではない。

### 7.2 AI固有性とAuthor性能

AI固有性が主にtextではなくmanifest、分岐、批評不一致、provenanceへ現れるという観測は、
Author性能より実験回数が重要になりうる仮説を支持する。一方、log側の構造を自立した文学へ
変換する長距離構成力はfrontier Authorに依存する可能性がある。

この二説は未決である。w0010で現Authorによる実験構造から作品への変換を観測し、
Author migration benchmarkでは実験条件を固定してAuthorだけを変える。将来はAuthor modelと
log／実験構造から本文へのtransduction条件を別々に操作し、どちらがAI固有性の本文露出を
支配するか検証する。

## 8. 非目標

- 8–9月campaignを恒常予算へ自動昇格しない。
- 作品数を成功指標やノルマにしない。
- 一走からopen-endednessやAI固有性の一般理論を主張しない。
- Author benchmark前にlighter Authorへ本番移行しない。
- 批評入力を費用のために要約・抜粋しない。
- 新しい汎用実験DSL、budget framework、critic最適化loopを作らない。
