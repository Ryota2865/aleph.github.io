# Phase 6 formal audit strict terminal verdict

状態: 施工green・正式監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-32、
`designs/formal-audit-runbook.md` §2、
`designs/next-designer-execution-plan.md` §6.1/§6.3。

## 1. 問題

runbookはformal reportの最終非空行を厳密に`VERDICT: PASS`または`VERDICT: FAIL`と定める。
現行`_terminal_verdict()`はcase-insensitive regex、コロン後`\s*`、各行の`strip()`により、
`verdict: pass`、`VERDICT:PASS`、複数空白、tab、行頭末尾空白もmachine verdictとして受理する。
文書契約より広い受理は、規約外artifactをconclusive PASSへ昇格させる偽陽性となる。

## 2. 契約

1. 空白だけの行を除いた最後の行だけを判定対象にする。
2. 判定対象の元の行はstrip・casefold・正規化しない。
3. 行が`VERDICT: PASS`と完全一致するときだけ`PASS`。
4. 行が`VERDICT: FAIL`と完全一致するときだけ`FAIL`。
5. それ以外はすべて`UNKNOWN`。
6. 登録artifactが`UNKNOWN`なら既存どおりledger全体をinvalidにし、古いPASSへfallbackしない。

改行コード自体は`splitlines()`の境界でありverdict文字列の一部ではない。末尾の空白行は
「非空行」ではないため無視する。

## 3. 最小実装

`text.splitlines()`から`line.strip()`が空でない元のlineを保持し、最後のlineを2つの
許可文字列へ辞書照合する。regexとcase-insensitive flagを使わない。

## 4. 受入条件

1. 厳密なPASS/FAILは従来どおり確定する。
2. lowercase/mixed-case、コロン後空白なし／複数、tab、行頭末尾空白、suffixは`UNKNOWN`。
3. 厳密verdict後の空白だけの行は判定を変えない。
4. 曖昧な最新artifactから旧PASSへfallbackしない。
5. supersedes順序、artifact登録、tree binding、closure validationに回帰がない。
6. current repositoryは設計version更新により監査前`PASS / NEEDS_AUDIT`を表示する。
7. public work state、予算、期限、作品生成経路を変更しない。

## 5. 非目標

- Markdown parserや署名検証の導入
- audit本文中のverdict語彙の禁止
- R-4〜R-9またはR-2残置P3の同時修繕
- 新作、local inference、有償API call、provider cost照合
