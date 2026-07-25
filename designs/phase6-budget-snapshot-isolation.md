# Phase 6 R-4 — budget snapshot返却値の分離

状態: 施工green・正式監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-33、
`designs/next-designer-execution-plan.md` §6.3。

## 1. 問題

`RepositorySnapshot`はfrozen dataclassだが、`to_dict()`が`budget`を参照のまま返す。
budgetは`ledgers`、`ledger_status`、`work_spent`の入れ子dictを持つため、呼出し側が
返却payloadを変更するとsnapshot本体の観測値も変化する。公開用JSONやadapterの後処理が、
取得済みcurrent stateを書き換えられる不変性破れである。

## 2. 契約

1. `RepositorySnapshot.to_dict()`はsnapshot本体からdetachedなbudget値を返す。
2. 返却後にbudget配下の任意の入れ子dictを変更しても`snapshot.budget`は不変である。
3. budgetの値、shape、算出、provenanceは変更しない。
4. snapshot生成後のrepository再読込や新しいmodule/interfaceを要求しない。

## 3. 最小実装

既に同じinterface内で使用している`deepcopy()`をbudget返却にも適用する。
呼出し側adapterへcopy責務を分散せず、snapshotのserialization seamで一度だけ保証する。

## 4. 受入条件

1. 実`RepositoryReader.snapshot().to_dict()`のbudget入れ子値を変更してもsnapshot本体が不変。
2. `ledgers`、`ledger_status`、`work_spent`の三面で逆流しない。
3. focused repository snapshot tests、全non-local tests、compileall、diff checkがgreen。
4. current repositoryは設計version更新により監査前`PASS / NEEDS_AUDIT`を表示する。
5. 作品、予算、期限、生成経路、formal auditの判定規則を変更しない。

## 5. 非目標

- immutable mapping型や新しいserialization frameworkの導入
- budget schema、上限、予約、charge/reconciliation規則の変更
- `to_dict()`の他の残置リスクの同時修繕
- R-5〜R-9またはR-2残置P3の同時修繕
- 新作、local inference、有償API call、provider cost照合
