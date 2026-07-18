# Transition history audit — Phase 1 baseline

日付: 2026-07-18
実行: `uv run python scripts/audit_transition_history.py`
方式: read-only。既存の`decisions.jsonl`と`checkpoint.json`は変更していない。

## 判定

現存8作品はすべてlegacy streamであり、新しいstrict replayの無警告条件を満たさない。
これは作品や公開物の無効化ではなく、0.7.20-5以前の記録契約の限界を列挙した基線である。
今後これらへ状態操作を行う場合、元行を修正せず`reconciliation` eventから新しい厳密区間を
開始する。

## w0001

- L0 event 5 source MATERIA does not match replay state COMPOSE
- checkpoint payload differs from legacy replay payload

## w0002

- checkpoint payload differs from legacy replay payload

## w0003

- checkpoint payload differs from legacy replay payload

## w0004

- L0 event 9 source FINISH does not match replay state SHELVE
- checkpoint step 8 differs from L0 count 9
- checkpoint payload differs from legacy replay payload

## w0005

- checkpoint payload differs from legacy replay payload

## w0006

- checkpoint payload differs from legacy replay payload

## w0007

- L0 event 9 source FINISH does not match replay state SHELVE
- checkpoint step 8 differs from L0 count 9
- checkpoint payload differs from legacy replay payload

## w0008

- L0 event 1 source DRAFT does not match replay state SEEDED
- L0 event 3 source CRITIQUE does not match replay state FINISH
- L0 event 5 source FINISH does not match replay state PUBLISH
- L0 event 6 source CRITIQUE does not match replay state PUBLISH
- checkpoint step 8 differs from L0 count 7
- checkpoint payload differs from legacy replay payload

## 解釈

- w0001のsource不一致は歴史的重複に由来する。
- w0004・w0007は旧`aleph publish`がSHELVE checkpointを直接FINISHへ巻き戻した結果である。
- w0008はcanonical handoffのcheckpoint合成と実走再開の重複がevent列に現れている。
- 全作品のpayload差は、旧L0行がcheckpointの完全な差分payloadを持たないためである。

Phase 1施工後の新規作品では、これらをwarningとして許容せずfail closedにする。
