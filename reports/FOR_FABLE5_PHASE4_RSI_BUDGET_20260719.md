# Fable 5への伝書 — Phase 4後のRSI・評価予算・Author移行

日付: 2026-07-19  
作成: Codex（Phase 4施工・検証担当）  
用途: オーナーがFable 5（設計者）へ持ち込み、Phase 5着手前の意見を受け取るための自己完結文書

## 依頼の位置

`reports/CRITIC_ROLE_REVIEW_20260717.md`で、Fable 5はALEPHを
「批評→制約実験→作品改善→批評改善」の小規模RSI系と読むことを条件付きで承認した。
本書は「RSIを入れるべきか」を尋ね直すものではない。Phase 4 `w0009`で新たに観測した
予算停止と評価欠損を踏まえ、同審査が定めた**評価器の外部性**を、実行予算とAuthor交代へ
どう実装するかについて意見を求める。

参照:

- `reports/CRITIC_ROLE_REVIEW_20260717.md`
- `designs/phase4-w0009-l2-era-intervention.md`
- `reports/EXP_w0009_l2_era_20260719.md`
- `reports/PHASE4_W0009_L2_ERA_AUDIT_20260719.md`
- Weco AI, [“AIDE²: First Evidence of Recursive Self-Improvement”](https://www.weco.ai/blog/first-evidence-of-recursive-self-improvement)

## Phase 4で新たに得た事実

w0009は、Fable 5をAuthorに固定し、同一意味核についてL2時代属性ありcontrolと
指定なしinterventionを比較した。主判定は`RULE_4_LEVEL_SPLIT_OR_MIXED`で、L2時代属性が
時代家風の主担体だという方向仮説はこの一走では支持されなかった。正式独立監査はPASS。

全phase API capは$12.00、実費は$11.245450で、aggregate capは守った。ただし配賦は偏った。

| phase | 配賦 | 実費 |
|---|---:|---:|
| prepare | $0.75 | $0.087930 |
| era_unpinned L4–L5 | $2.50 | $2.690760 |
| era_pinned L4–L5 | $2.50 | $2.856650 |
| blind select | $0.75 | $0.240970 |
| jury reveal | $1.50 | $0.356420 |
| canonical L6–L7 | $3.50 | $5.012720 |
| failure reserve | $0.50 | $0.000000 |

前半の余剰をcanonicalが使い、主実験に必要な両腕・分類・盲検選択は完了した。一方、
canonical第五査読はAPI陪審2件完了後にlocal陪審中断となり、再生成せず軌跡から除外した。
題名「第一信」は得たが、その後の公開意思callは残額不足によりprovider前に拒否され、
resource stopの`SHELVE`で終端した。別件として、開示陪審6 callは完了したものの最後のstrict
parse失敗により二次score比較が`INCOMPLETE_PARSE`になった。主判定は失われていないが、
作品の自然な終端と二次評価は一部欠けた。

## Codex提案1 — 一律phase hard capではなく、評価予算をplayerから保護する

一律に各phaseをhard cap化すると、全体残額があっても自然な再校を途中で止め、実験価値を
かえって損なう。提案は次の三枠＋aggregate hard capである。

1. **Player探索枠**: Author、開示critic、再校。phase配賦はsoft targetとし、内部借用を許す。
2. **Held-out評価枠**: blind selector、非開示jury、転移評価。playerから借用不能な
   protected hard reserveとする。
3. **Owner-only外部批評枠**: ALEPH自身が起動できない批評。費用は記録するが自動ループの
   残額として見せない。
4. **Aggregate cap**: 全枠合計のprovider前hard gateとして維持する。

陪審3件や再校一巡は`atomic batch`として、全件を完了できる予算がある場合だけ開始する。
終端前には、次の一巡だけでなく題名・公開判断・held-out評価を先に取り置く。予算不足時は
入力を抜粋せず、批評頻度を下げるか延期する。これは既審査の
「入力の完全性 > 批評の頻度 > 対象の網羅」を実行予算へ翻訳する案である。

実装するなら、各callerが台帳計算を知る浅い分散配線ではなく、「batchを開始してよいか」を
一度だけ答える小さなinterfaceの背後へ、scope残額・protected reserve・atomicity・deviationを
隠す深いmoduleを置く。ただしw0009固有の判定や役職論を汎用予算DSLへ昇格させない。

## Codex提案2 — ALEPH型AIDE²は、score勾配ではなく外部評価seamを持つ

単純なAuthor–Critic対話を反復し、平均scoreを上げる構成にはしない。criticまで内側へ入り、
作品が評価語彙を実演するGoodhart化と家風の均質化を招くからである。提案するshadow構成:

1. inner playerはAuthor＋開示批評による局所改稿を行う。
2. playerに見せない異種混合juryが、凍結版をheld-out評価する。
3. outer loopが変更できるのはprompt、context管理、停止規則等のharness候補であり、
   critic正典・private packet・評価用作品を変更できない。
4. 改善候補は、最適化に使わなかった複数意味核・形式・棚作品へ転移し、同一費用で優位を
   保った場合だけ採用する。
5. 完成度だけでなく、陪審不一致、新奇性、家風固定化、parse失敗、費用を別軸で保持する。
6. 過去批評の予測が成立したかを次回批評で検証し、critic自身を計器台帳へ載せる。
7. owner-only批評路は外側に残し、inner/outer loopのどちらも呼出し文面を変更できない。

最初から自己改訂を本番適用せず、Phase 5で計器を校正した後に、現行harnessと候補harnessを
固定費用・held-out作品で比較するshadow experimentを想定する。

## Codex提案3 — w0009は再実行せず閉じる

同じ`w0009`で第五査読、陪審score、公開意思だけを再試行することには反対する。

- 事前登録の非再生成規則に反する。
- resource stopを含む正式監査PASS済みartifactを書き換える。
- 追加予算を知った後の継続になり、元の実験条件ではない。
- 主判定は既に成立しており、失われたのは主にcanonical制作と二次評価である。

作品「第一信」をさらに育てる文学的理由がある場合は、w0009を不変の親として、別work ID・
別予算・「Phase 4の追試ではない」と明記した派生制作として開始する。オーナーは7/23まで
新規有料実験を停止し、Fable 5の意見後にPhase 5の優先順位を決める方針を承認済みである。

## Codex提案4 — Author交代はwork/experimentの途中でなく、校正済みの世代境界で行う

オーナーは予算持続性のため、将来AuthorをFable 5から軽量モデルへ移したい。候補として
`gpt-5.6-terra`、`gpt-5.4`、`claude-opus-4-8`が挙がったが、選定は未決である。

交代に適さない時点:

- 同一workの改稿途中
- control/interventionの生成途中
- 詩学改訂と同時
- classifierや陪審構成の変更と同時

適する時点は、Phase 5で最低限の計器校正を終え、次の新規work/experimentを開始する直前。
詩学・criteria・意味核・生成条件を固定した小さなblind migration benchmarkを先に行い、
旧Authorと候補Authorを比較する。評価はAuthor名を隠したheld-out juryとowner-only criticで行う。
見るべきは平均scoreだけでなく、長文完走率、parse安定性、改稿への応答、家風標識、作品間の
多様性、費用である。採用後は`author_epoch`（または同等の明示的世代記録）を新workへ刻み、
旧作との単純な縦比較を避ける。

緊急に費用を下げる必要がある場合、次作から明示的に切り替えること自体は可能だが、最初の
1作を「通常運用の証拠」と「モデル移行校正」の二重用途にしない方がよい。まずshadow比較、
次に採用決定、その後に新規制作という順を推す。

## Fable 5へ伺いたい点

1. Player探索枠とheld-out評価枠を分離し、後者をplayerから借用禁止にする案は、
   `CRITIC_ROLE_REVIEW`の外部性原則を正しく実装しているか。
2. 陪審・再校一巡・完全文脈批評をatomic batchとして予約し、足りなければ抜粋せず延期する
   規則に異論はあるか。
3. Owner-only批評の費用を自動実験scopeと別にし、ALEPHへ残額を見せない設計でよいか。
4. AIDE²型shadow experimentで、private評価に置くべき作品群・計器・棄却条件は何か。
5. w0009はresource stopを含む完成した実験として閉じ、必要なら別workへ派生させる判断で
   よいか。
6. Author移行はPhase 5の計器校正後、詩学を固定した世代境界で行うべきか。比較時に
   最低限必要な刺激数・作品条件・評価役職は何か。
7. `author_epoch`を新しい正典概念として導入する価値があるか、それとも既存のmodel/config/
   call provenanceだけで十分か。

回答は、賛否だけでなく、どの提案が批評家の外部性を損なうか、また予算制約下で何を削り
何を絶対に保護すべきかを優先していただきたい。設計変更を伴う回答はオーナー承認後に
PLAN_CHANGELOGへ記録し、実装・実走前に独立監査する。
