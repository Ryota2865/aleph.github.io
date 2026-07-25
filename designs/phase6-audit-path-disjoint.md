# Phase 6 R-9 — audit path分類排他

状態: 施工green・正式監査待ち

## 契約

1. `legacy_unordered`と`entries`のpath集合は排他的である。
2. overlapを固有warningで列挙する。
3. overlap entryをregisteredへ昇格させない。
4. ledger全体をinvalidとしformal status/currencyをUNKNOWNへ倒す。
5. 非overlap ledger、sequence、supersedes、verdict、tree bindingは変更しない。

## 受入条件

- 同一PASS pathの二重分類が旧PASSからUNKNOWNへ反転する。
- artifactはlegacyとして保持され、消失しない。
- focused、全non-local、compileall、diff checkがgreen。
- 監査前current-stateは`PASS / NEEDS_AUDIT`。

## 非目標

- ledger schema一般化、legacy全件の再登録、残置P3の同時修繕
- 新作、local inference、有償API call、provider cost照合
