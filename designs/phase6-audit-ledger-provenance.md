# Phase 6 R-5 — formal audit ledger provenance

状態: 施工green・正式監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-34、
`designs/next-designer-execution-plan.md` §6.3。

## 1. 問題

`RepositorySnapshot.formal_audits`の登録entryは、artifact本文に加えて
`config/formal-audits.json`からledger区分、sequence、target changelog、candidate tree/commit/ref、
closure paths、supersedesを得る。しかし公開provenanceは`audits/`と
`reports/*AUDIT*.md`だけを列挙し、値の権威順序とidentityを決めるledgerを出所として示さない。

## 2. 契約

1. `formal_audits` provenanceは権威ledgerとartifact集合の両方を列挙する。
2. ledgerはmetadataと順序の権威なので、provenance listの先頭に置く。
3. ledger欠落・malformed時も、provenanceはこのmoduleが読む宣言入力を正直に示す。
4. `assurance` provenance、artifact在庫、ledger validation、verdict、currencyは変更しない。

## 3. 最小実装

既存`RepositorySnapshot.provenance["formal_audits"]` tupleの先頭へ
`config/formal-audits.json`を一項目追加する。新しいmodule、reader、adapterは作らない。

## 4. 受入条件

1. `RepositoryReader.snapshot().to_dict()`の`formal_audits` provenanceが
   ledger、`audits/`、report globの三入力を返す。
2. artifact sourcesを削除せず、ledgerを重複登録しない。
3. focused repository snapshot tests、全non-local tests、compileall、diff checkがgreen。
4. current repositoryは設計version更新により監査前`PASS / NEEDS_AUDIT`を表示する。
5. 作品、予算、期限、生成経路、formal audit判定を変更しない。

## 5. 非目標

- provenance schemaの一般化や自動導出
- R-6〜R-9、R-2残置P3、R-4監査P3の同時修繕
- ledger schema、artifact parser、tree binding、closure allowlistの変更
- 新作、local inference、有償API call、provider cost照合
