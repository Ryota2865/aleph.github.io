# Phase 6 R-7 — CHANGELOG版順の明示化

状態: 施工green・正式監査待ち

## 契約

1. fence外のtop-level `## <version>`だけを版候補とする。
2. 物理順ではなく数値版順最大をlatestとする。
3. dotとhyphenの各数値部分を順に比較する。
4. code fence・引用内の例示見出しを無視する。
5. latest title、stale判定、欠落時UNKNOWNの既存面を維持する。

## 受入条件

- 旧版が先、新版が後でも新版を選ぶ。
- より大きい偽版がfence内にあっても選ばない。
- 既存hyphenated版・次series test、focused、全non-local、compileallがgreen。
- 監査前current-stateは`PASS / NEEDS_AUDIT`。

## 非目標

- Markdown汎用parser、日付による順序、version schema変更
- R-8〜R-9、R-2残置P3、R-4監査P3
- 新作、local inference、有償API call、provider cost照合
