# Phase 6 formal audit supersedes order independence

状態: 施工green・正式監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-31、
`designs/next-designer-execution-plan.md` §6.1/§6.3。

## 1. 問題

formal audit ledgerは`sequence`を明示的な権威順序として持つが、現行の`supersedes`検証は
JSON `entries`配列を先頭から走査し、その時点までに登録済みのpathだけを参照可能としている。
このため同じentry集合でもsequence昇順なら有効、降順なら`UNKNOWN`となる。runbookは配列順を
契約にしておらず、正当なledgerが表現上の順序だけで拒否される。

## 2. 契約

1. `entries`配列のJSON記載順は意味を持たない。
2. 最新auditの選択と`supersedes`の時間順は、正の一意な`sequence`だけで決める。
3. `supersedes`は同じledger内に存在する別entryのpathを指す。
4. 参照先sequenceは参照元sequenceより厳密に小さくなければならない。
5. 欠落、自己参照、same/future-sequence参照、cycleはledger invalidとして`UNKNOWN`へ倒す。
6. entry固有の既存検証、artifact登録、verdict、Git tree bindingは弱めない。

## 3. 最小実装

entry本体の処理前に、ledgerが宣言するpathとsequenceの対応をread-onlyで収集する。
各entryの既存validationは維持し、`supersedes`だけを走査済みpath集合ではなく宣言済みsequence
対応へ照合する。参照先が存在し、`target_sequence < source_sequence`の場合だけ受理する。

重複path/sequenceや壊れたentryがあれば既存どおりledger全体をinvalidにするため、事前収集が
不正entryをformal PASSへ昇格させることはない。

## 4. 受入条件

1. 同じ2 entryをsequence昇順・降順のどちらで記載しても、focused re-auditの最新PASSを選ぶ。
2. 降順記載でも`supersedes`が過去sequenceを指すならledger warningを出さない。
3. `supersedes`のmissing/self/future参照は`UNKNOWN`とinvalid warningを返す。
4. duplicate sequence/path、未登録artifact、壊れたverdictは従来どおりfail closed。
5. current repositoryのformal projectionは、設計version更新により監査前
   `PASS / NEEDS_AUDIT`となる。
6. public work state、予算、期限、作品生成経路を変更しない。

## 5. 非目標

- audit lineageの汎用DAG化
- 複数親、branching audit history、artifact内容の意味比較
- R-3〜R-9またはR-2残置P3の同時修繕
- 新作、local inference、有償API call、provider cost照合
