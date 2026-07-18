# TransitionCommit 設計

日付: 2026-07-18
設計者: Codex（次期設計者）
状態: 採用済み実行計画 Phase 1 の施工契約

## 1. 目的

`decisions.jsonl`を状態変更の一次記録、`checkpoint.json`を再構築可能な投影として
実効化する。状態変更の意味を`Loop`、pipeline、CLI、実験runnerへ重複実装しない。

中心moduleは`aleph.core.transition_commit`、外部seamは次の三操作に限定する。

```python
commit(work, command_id, expected_state, next_state, reason, decided_by,
       payload_delta=None) -> TransitionResult

initialize(work, command_id, state, reason, decided_by,
           payload=None) -> TransitionResult

project(work, command_id, expected_state, name, reason, decided_by,
        payload_delta) -> TransitionResult
```

- `commit`: 正典遷移表に従う通常遷移。
- `initialize`: 実験腕からの正典handoffなど、L0履歴が空の作品へ由来つき初期像を置く。
- `project`: lifecycle stateを変えず、公開再評価など直交するdispositionを追記する。

三操作は同じ内部実装を共有し、event id、冪等性、追記、投影、回復を隠す。

## 2. event契約

新しいL0行は既存の`decision`文字列を残しつつ、次を必須とする。

- `schema_version: 1`
- `event_id`: 作品内で1から単調増加する整数
- `command_id`: 再試行を同定する安定文字列
- `event_type`: `transition | initialize | projection | reconciliation`
- `state_before`, `state_after`
- `payload`: このeventが加える差分
- `ts`, `layer`, `decision`, `reason`, `decided_by`: 全decision共通の監査metadata

同じ`command_id`を同じ内容で再送した場合は既存結果を返し、eventもstepも増やさない。
別内容で再利用した場合は停止する。

## 3. 書込み・故障モデル

単一作品へのwriterは一プロセスを運用前提とする。二ファイルを同時renameすることは
できないため、次の順序を固定する。

1. 現在のevent列を検証する。
2. 新eventを含む`decisions.jsonl`全体を一時ファイルへ書き、`os.replace`する。
3. event列からcheckpointを再生し、一時ファイル＋`os.replace`で保存する。

event確定後、checkpoint保存前に停止した場合も一次記録は失われない。次回の
`recover()`または次のcommitがevent列からcheckpointを修復する。逆順にはしない。
JSONL全体の置換は追記意味を維持しつつ部分行を防ぐ。作品単位のログ規模では、毎回の
全体コピーを許容する。性能特性はO(decisions file size) / commitである。

## 4. replayとlegacy

`strict_replay()`はevent id、command id一意性、遷移元連続性、正典遷移、payload型、
全decision共通の監査metadataを検証し、一つでも破れば停止する。modern専用fieldを
持つ行から`schema_version`だけが欠けた場合もlegacyへ降格せず、破損modern eventとして
拒否する。矢印の右側だけを採用しない。

0.7.20-5以前のL0行はlegacyとしてread-only監査できるが、strict streamとはみなさない。
既存行の削除・並べ替え・書換えは禁止する。legacy作品へ新しい状態操作が必要な場合は、
`aleph reconcile --work <id>`を独立して明示実行し、現在のcheckpointと不一致一覧を持つ
`reconciliation` eventを追記して、そこを新しい厳密再生区間の基点とする。`publish`等の
別commandが暗黙にreconcileしてはならない。reconciliationは過去が整合していたという
主張ではない。

## 5. 公開再評価

制作lifecycleと後日のpublication dispositionを直交させる。

- 初回runの`FINISH->PUBLISH|SHELVE|DISCARD`は従来どおりlifecycle遷移。
- SHELVE後の再評価でcheckpointをFINISHへ巻き戻さない。
- 再評価結果は`project(... name="publication_reassessment", payload_delta={...})`で追記する。
- lifecycleはSHELVEのまま、`payload.publication_disposition`が現在の公開状態を表す。
- `publication_disposition=PUBLISH`を書けるのはSHELVE上の
  `projection:publication_reassessment`だけである。公開判定は累積payloadだけでなく、
  最後にdispositionを書いたeventの由来も検証する。

したがってSHELVEは終端のままであり、終端不変条件を弱めない。公開siteと将来の
`WorkSnapshot`はlifecycleだけでなくpublication dispositionを読む。

## 6. 実験handoff

w0008型handoffはcheckpointを直接合成しない。main作品にL0 eventがない場合だけ
`initialize(... state=DRAFT, payload=共有文脈)`を許す。すでにL0履歴がある場合は冪等な
同一commandを除き停止し、進行中checkpointを巻き戻さない。

## 7. 受入条件

- 完全runとクラッシュ再開で`checkpoint == strict_replay(events)`。
- source state不一致、event id欠落・重複、command id衝突をfail closedで拒否する。
- event確定後のcheckpoint欠落を`recover()`が修復する。
- 同一commandの再実行でeventとstepが増えない。
- 公開再評価はSHELVEを維持し、公開dispositionだけを変更する。
- 終端event後のfinal生成は冪等補完する。課金を伴う詩学reflectionは開始decisionを先行し、
  開始後・完了前の不明状態を自動再実行しない。
- w0008型handoffは由来つきinitialize eventから再生できる。
- 現存8作品は変更せず、不一致と再生不能範囲をreportへ列挙する。

## 8. 非目標

- 汎用event storeや分散transactionを作らない。
- legacy履歴を見た目上きれいに書き換えない。
- 複数writerの並行実行を保証しない。
- Phase 2の`WorkSnapshot`を先取りしない。
