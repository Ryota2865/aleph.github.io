# Phase 1 TransitionCommit 独立監査と修繕記録

日付: 2026-07-18
監査対象: `51b7316` (`main`)
受領判定: **FAIL**
修繕状態: **全6所見を回帰テスト化して修正済み、独立再監査待ち**

## 監査所見

1. **P1 — 公開成果物が正典eventより先に生成される。**
   pipelineがfinalを生成してから`FINISH->PUBLISH`をcommitしていたため、故障窓では
   lifecycleがFINISHのままサイトに収載され得た。
2. **P1 — stale checkpointからの再開で課金対象処理を重複実行する。**
   run開始時にL0から回復せず、checkpoint上のhandlerを先に実行していた。
3. **P1 — 空L0の`recover()`が既存checkpointをSEEDEDへ巻き戻す。**
   legacyまたは未記録状態を警告なく破壊し得た。
4. **P1 — FINISHからの`aleph publish`が非終端状態のまま成功する。**
   初回判断にもprojectionを使い、`FINISH->PUBLISH` lifecycle遷移を記録しなかった。
5. **P2 — publish CLIが一次記録より先にcheckpointを信用する。**
   checkpoint欠落・stale・誤状態をrecover前に判定していた。
6. **P2 — `strict_replay()`がevent契約を完全には検証しない。**
   整数型偽装、schema型偽装、`decision`表示とevent内容の矛盾等を受理した。

監査時の既存非localテストは`239 passed, 1 deselected`だったが、上記の故障窓は
未検査だった。別Codex監査でも所見1、2、5、6が独立検出された。Claude Code
`claude-opus-4-8`による正式クロス監査は、外部サービスへのリポジトリ送信に関する
安全審査で実施されていない。明示承認なしに再試行しない。

## 修繕

- pipelineとpublish CLIはhandler・事前判定より先にstrict recoveryを行う。
- 空L0と既存checkpointが不一致ならfail closedとし、明示的な初期化または
  reconciliationを要求する。
- `strict_replay()`はschema/event idのJSON整数型、必須payload、modern eventのL0所属、
  event type・state・`decision`表示の整合性を検証する。
- FINISHからのpublishは通常の`commit()`、SHELVE後の再評価だけを`project()`とする。
- PUBLISH eventを先に確定し、その後finalを原子的に生成する。event済みでfinalが欠落・
  破損していれば、runまたはpublish再実行時に冪等補完する。
- 簡易サイト、GitHub Pages生成器、LLM索引はfinalの存在だけでなく正典公開状態を要求する。
  modern履歴はstrict replayし、既存legacy作品は最後のL0公開遷移で互換維持する。
- SHELVE上の`publication_disposition=PUBLISH`だけを公開再評価として認め、FINISH上の
  projectionによる初回遷移の迂回は公開扱いしない。

## 検証

- 監査6所見と追加のfail-closed境界を回帰テスト化。
- 非local全体: **259 passed, 1 deselected**。
- 既存公開作品の生成結果は不変で、追跡済み`docs/`に差分なし。

本書は修繕者による対応記録であり、独立監査のPASS判定を代行しない。
