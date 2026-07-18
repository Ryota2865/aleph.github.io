# Phase 1 TransitionCommit 正式独立再監査

日付: 2026-07-19
監査者: Claude Code（施工者と異なる独立担当）
対象commit: `df1552dc82f73c87a10234f83635da6aa2a04123` (`Close transition recovery audit gaps`)
比較base: `2f3dc6e` (`Make publication event authoritative`)
判定: **PASS**

## 監査条件

- `PLAN.md`、`AGENTS.md`、`designs/transition-commit.md`と関連実装を参照した。
- WSL側Gitを正典として、worktree cleanと対象HEADの一致を確認した。
- `bash scripts/doctor.sh`は`failures=0 warnings=0`。
- `git diff --check 2f3dc6e..df1552d`は空だった。
- 監査者は追跡ファイル、report、commitを変更していない。

## テストと独立故障注入

- `uv run pytest -q -m 'not local'`:
  **272 passed, 1 deselected in 5.78s**。
- 既存テストの緑を前提にせず、`tmp`内で46件の独自故障注入を行い、全件PASSした。
  - バッチ1（19件）: projection由来偽装、schema/event id型偽装、監査metadata欠落、
    Loop stale checkpoint回復、冪等再commit。
  - バッチ2（19件）: SHELVE/PUBLISH公開後のfinal補完、reflection一度きり、legacy
    publishのfail closedと明示reconcile、schema欠落modern拒否。
  - バッチ3（8件）: 空L0とcheckpoint不一致、FINISH初回publish、decision表示不整合、
    非正典遷移、event id非連続、checkpointとstrict replayの一致。

## 確認済み修繕

1. **Loop stale checkpoint回復**
   - `Loop.run()`はhandler実行前にevent streamから`recover()`し、stateとstepを採用する。
   - event=EXPLORE/checkpoint=INTENTでもINTENTの課金handlerを再実行しない。
2. **legacy reconciliationの権限分離**
   - `aleph publish`は不一致を自動reconcileせずfail closedする。
   - 確認済みcheckpointのmodern基線化は明示`aleph reconcile --work <id>`だけが行う。
   - schema欠落modernはreconcileでも拒否され、部分的なevent追記を残さない。
3. **publication dispositionの由来検証**
   - `publication_disposition=PUBLISH`は、lifecycle PUBLISHまたはSHELVE上の
     `projection:publication_reassessment`だけが記録できる。
   - 公開判定は最後にdispositionを書いたeventの由来を検証する。
4. **modern／legacy分類**
   - modern専用fieldが残るschema欠落eventをlegacyへ降格しない。
   - schema_version/event_idはbool、float、stringを含む非整数型を拒否する。
5. **公開後の回復**
   - PUBLISHと正当に公開再評価されたSHELVEの双方でfinalを補完する。
   - 確定済み公開の補完はackゲートより先に行う。
   - reflectionは開始記録後の不明状態で自動再課金せず、完了済みなら一度きりになる。
6. **strict replayの監査metadata**
   - appendとreplayが同じ検証を共有し、`ts/layer/decision/reason/decided_by`欠落を拒否する。

過去に指摘された、公開eventとfinalの順序、空L0からのSEEDED巻戻し、FINISH初回公開の
projection誤用、publish CLIのcheckpoint先行判定、整数型・decision表示検証、同一commandの
再実行によるevent/step/費用増加についても、退行がないことを独立に確認した。

## 所見

**契約違反（P0–P2）: なし。**

### P3 — reconcileの未捕捉`FileNotFoundError`

legacy L0履歴が存在する一方で`checkpoint.json`が欠落した作品に`aleph reconcile`を実行すると、
graceful errorではなく生のtracebackで終了する。

- 設計上legacy作品はcheckpointを持つ前提であり、契約違反ではない。
- データ破損や誤公開は起こらず、極端なedge caseでのUX劣化に限られる。
- 後続の堅牢化では、`Checkpoint.load`の`FileNotFoundError`を
  `LegacyHistoryError("reconciliation requires an existing checkpoint")`へ変換する案がある。
- 本項を直ちに変更すると監査済みHEADが変わるため、Phase 1完了を妨げない後続候補として保留する。

## 未検査範囲

- GPU・ネットワーク依存の`RealDeps`実LLM経路。
- `aleph publish/reconcile`のプロセスレベルE2E（関数レベルで代替検証済み）。
- 既存8作品のlegacy履歴実データ。

これらは今回のPhase 1契約に対する正式PASSを妨げない。Phase 1 TransitionCommitは
施工者と異なる担当による独立再監査を通過し、Phase 2へ進むための監査ゲートを満たした。
