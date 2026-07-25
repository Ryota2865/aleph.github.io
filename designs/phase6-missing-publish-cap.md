# Phase 6 R-6 — publish cap欠落の可視化

状態: 施工green・正式監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-35、
`designs/next-designer-execution-plan.md` §6.3。

## 1. 問題

`publish.max_per_month`が非整数ならdeadline unavailable warningを出すが、key自体の欠落は
`None`として黙って処理される。その結果、deadline面が消えた理由を読者が区別できない。

## 2. 契約

1. key欠落時はdeadlineを生成せず、`publish_cap=None`を維持する。
2. key欠落を明示するwarningを一件出す。
3. 非整数、999期限、通常の整数capの既存意味を変えない。
4. 値を推測・補完・自動変更しない。

## 3. 最小実装

既存cap validationの前にmissing key分岐を追加する。新moduleや設定adapterは作らない。

## 4. 受入条件

1. missing fixtureが空deadline、None cap、固有warningを返す。
2. malformed fixtureは既存の非整数warningを返す。
3. focused、全non-local、compileall、diff checkがgreen。
4. 監査前current-stateは`PASS / NEEDS_AUDIT`。
5. 作品、予算値、期限値、生成経路、formal audit判定を変更しない。

## 5. 非目標

- publish capの既定値導入や期限日の変更
- R-7〜R-9、R-2残置P3、R-4監査P3の同時修繕
- 新作、local inference、有償API call、provider cost照合
