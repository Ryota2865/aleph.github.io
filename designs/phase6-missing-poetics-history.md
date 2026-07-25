# Phase 6 R-8 — poetics履歴欠落の可視化

状態: 施工green・正式監査待ち

## 契約

1. `poetics/`あり・`history.jsonl`欠落はcanonical helperどおりv0。
2. 欠落fallbackを固有warningで可視化する。
3. 存在する空履歴、malformed履歴、poetics dir欠落の既存意味を変えない。
4. 履歴を作成・補完しない。

## 受入条件

- missing historyでv0とwarningを同時に返す。
- focused、全non-local、compileall、diff checkがgreen。
- 監査前current-stateは`PASS / NEEDS_AUDIT`。

## 非目標

- poetics version規則変更、履歴自動生成、R-9または残置P3
- 新作、local inference、有償API call、provider cost照合
