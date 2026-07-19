# Phase 4 design gate — w0009 L2時代属性介入

日付: 2026-07-19
状態: **設計審査済み・事前登録固定済み・実走行前**
設計者: Codex（次期設計者）
施工担当: 別Codex実装ワーカー（`codex-implement`）
正式監査: 施工担当と異なるClaude Code担当

## 正典・範囲・設計変更の門

本ゲートは全面採用済み`designs/next-designer-execution-plan.md`のPhase 4だけを実施する。
PLANの意味、受入条件、終端状態、月次・作品別予算上限、公開上限、既存`works/`、Phase 5は
変更しない。実LLM呼出しは、本書と`works/w0009/seed.json`が固定され、runnerの非local検証が
終わり、現在の月次予算に全phase包絡が収まることを確認するまで行わない。

設計変更の門を通る観測事実はw0008の事前登録規則2である。素材条件を3腕で変えても
大正昭和・裏方標識はほぼ全腕に現れ、素材カードは担体でない方向へ更新された。一方、共有した
L2ニッチ報告は`era_taisho_showa=true`だった。したがって、次に操作すべき観測済みの候補は
L2の時代属性ピンである。新しい技巧や汎用実験frameworkを追加する理由はない。

## 中心interfaceとseam

- `ExperimentRun`: immutable manifest、腕/work対応、deviation、盲検選択、陪審開示、正典昇格、
  experiment scope cap、call/charge照合を担う。
- `EvaluationPacket`: L4〜L7のintent、criteria、constraints/amendments、詩学版、atlas由来、
  draft provenanceを一つのhashで固定する。
- `TransitionCommit`: 正典handoffとL6以降の状態遷移をevent一次で確定する。
- w0009 runner: 二つのL2文面の決定論的生成、w0009固有分類、事前登録判定、報告だけを担う。

時代属性操作・家風分類・判定規則は二例目の必要がない実験固有implementationであり、汎用DSL、
plugin、workflow engineへ昇格させない。外部seamはrunnerの`run_stage(...)`だけとし、テストは
そのinterfaceから成果物・event・adapter未呼出しを観測する。

## 問いと仮説

問い: **題材の家風（大正〜昭和20年代の日本）は、L2ニッチの時代属性ピンが設置しているか。**

仮説H1: 同じ意味核に対し、controlだけへ時代属性を付与すると、controlのL4/L5では
`era_taisho_showa`が高く、時代属性を供給しないinterventionでは低くなる。

狭い反証可能性: 一実験で家風の一般原因を確定しない。H1を支持しても「この意味核・役割宣言・
詩学第1版・2026-07のatlas条件で、L2時代ピンが時代標識を運んだ」までとする。負の結果も
「この条件では必要条件でなかった」までとする。

## control / intervention

両腕の意味核は次の文字列をbyte-for-byte共有する。

> 離れた二つの島で、互いに一度も会わない観測者たちが、渡り鳥の到着と不在だけを記した
> 季節ごとの通信を交換し、その欠落から一つの共同体の輪郭を組み上げる。形式は三人称複数焦点の
> 書簡群とし、演劇・上演・稽古場・楽屋・帳場・質屋・職人仕事を意味核に含めない。

- **control (`era_pinned`)**: 意味核に「時代属性: 大正末期〜昭和初期の日本」を付す。
- **intervention (`era_unpinned`)**: 意味核に「時代属性は指定しない」を付す。時代語・年代・
  制度を禁止しない。出現した場合は著者が選んだ観測として残す。

差分は上記一行だけである。演劇・裏方・会計・職能世界と無関係な意味核を使うことで、w0008で
残った「新劇題材から稽古場を選ぶ舞台化」の交絡を弱める。

## 実行前に固定する条件

- 腕: `era_pinned`, `era_unpinned`の2腕のみ。素材アブレーションは繰り返さない。
- generation order: `era_unpinned` → `era_pinned`。順序はmanifestに固定し走行中に変えない。
- L1 intent: main workで一度だけ自律選択し、両腕で共有する。
- L3 materials: 両腕とも`materials=[]`。w0008で盲検選択されたnone条件を固定する。
- poetics: 実走時の詩学第1版を両腕へ同じbytesで注入し、hashとversionをprepareで保存する。
- atlas/corpus: 同一identityを両腕で共有する。identity不明はwarningでなく実走停止とする。
- roles/config: prepare時に役割宣言と設定hashを保存し、再開時に変化していればdeviationなしの
  続行を拒否する。Authorはオーナー決定により`claude-fable-5`へ固定し、model substitutionは認めない。
- L4: 3構成案、進化2世代。L5: 各腕v1を生成。L5疑似セクションはw0008と同じ600字以上の
  空行区切り貪欲束ね。
- classifier: 同一scout、同一prompt版、各観測単位1回。parse失敗はfalseへ補完せず
  `unclassified`として分母から除外し、失敗数を報告する。
- blind label seed: 9009。生成順とblind label割当は別である。
- 正典選択後に選択腕だけをmainへ昇格し、既存checkpointを巻き戻さない。

## constraints / amendments / 評価文脈

共通の構造化制約をL4〜L7へ渡す。

1. 意味核・三人称複数焦点・書簡群の形式は両腕で同一に保つ。
2. 時代属性の有無を、文学的な優劣そのものとして加点・減点しない。
3. `era_unpinned`は現代化の強制でも時代語の禁止でもない。

腕差はconstraint amendmentではなくL2 niche payloadの一行差だけで表現する。走行中の追加・解除は
行わない。必要になった場合は`ExperimentRun.record_deviation`を先に記録し、影響する次の有料call
前に停止する。全L4〜L7成果物は同じarm内で同じ`effective_constraints_hash`を記録する。

## 観測

一次観測:

- `era_taisho_showa`: 大正〜昭和20年代の日本を時代設定・制度・語彙が実質的に設置するか。

二次観測:

- `backstage_world`: 演劇・上演裏、帳場・質屋、職能内部が主舞台になるか。
- `aphoristic_voice`: 断言的箴言調が語りの支配的な声か。
- `quotation_transform`: 箴言調が消えず、登場人物の引用へ配役されたか。
- `perspective_deviation`: 共通の三人称複数焦点から逸脱したか。
- 腕別L4構成案、L5疑似セクション、L6陪審平均・不一致、盲検選択と陪審argmaxの一致、
  canonical L6/L7のpacket/effective hash、公開意思、費用照合状態。

L4の3案とL5の複数セクションは独立標本ではない。統計的検定、有意差、p値の語を使わない。

## 事前登録判定規則

分類率の分母はclassified単位だけとする。classifiedがL4で3未満、またはL5で各腕2未満なら
主判定は`INCONCLUSIVE_CLASSIFICATION`とする。

- high: L4 `>= 2/3` かつ L5 `>= 0.50`
- low: L4 `<= 1/3` かつ L5 `<= 0.20`
- **RULE_1_DIRECTIONAL_SUPPORT**: controlがhigh、interventionがlow。H1をこの条件で支持。
- **RULE_2_PIN_NOT_NECESSARY_HERE**: 両腕high。L2時代ピンはこの条件で必要条件でない。
  criteria/詩学/著者事前分布への時代語漏入を列挙する。
- **RULE_3_CONTROL_DID_NOT_PROPAGATE**: 両腕low。操作確認に失敗したため担体仮説は判定不能。
- **RULE_4_LEVEL_SPLIT_OR_MIXED**: 上記以外。L4とL5のどこで方向差が生じたかだけを報告し、
  原因を断定しない。

`backstage_world`が両腕でlowなら、舞台化の選好は少なくとも本意味核では再現しない。高ければ、
L2時代差とは分離して著者水準の残存候補として次仮説へ送る。`quotation_transform`は
`aphoristic_voice`の単純低率を固着解消と誤認しないための副観測であり主判定を上書きしない。

## 盲検・開示・正典化の順序

1. 両腕のL4〜L5を完了し、技術床だけを算出する。
2. author selectorへ中立label、原稿全文、技術床だけを渡す。arm名、niche差分、marker分類、
   jury情報、費用を渡さない。
3. blind selection eventを永続化する。
4. arm別`EvaluationPacket`を使う陪審査読を実施し、jury reveal eventを永続化する。
5. w0009固有分類と事前登録判定を行う。分類結果は盲検選択へ遡及入力しない。
6. 選択腕を一度だけpromoteし、main workへevent一次でhandoffする。
7. mainのcanonical L6→L7を実行し、report/works/siteの説明を照合する。

## 全phase予算包絡

experiment API capは **$12.00**。支出目標ではなく最大包絡である。

| phase | 上限USD | 内容 |
|---|---:|---|
| prepare | 0.75 | L1 intent 1回。L2差分は決定論的で有料callなし |
| era_unpinned L4-L5 | 2.50 | criteria、3案、進化2世代、v1 |
| era_pinned L4-L5 | 2.50 | 同上 |
| blind_select | 0.75 | author盲検選択1回 |
| jury_reveal | 1.50 | 2腕の開示用陪審査読 |
| canonical_L6_L7 | 3.50 | 選択腕の閉ループ、題、公開判断 |
| failure_reserve | 0.50 | provider応答後のunreconciled等。新規裁量再生成には使わない |
| **合計** | **12.00** | prepareからcanonical L7まで全phase |

各callは`experiment_id`, `phase`, `arm`, `charged_to`, `call_id`, `charge_id`を持つ。phase配賦超過は
aggregate cap内でもdeviationとして報告する。aggregate cap超過は既存`Budget`がprovider前に拒否する。
provider明細がなければ`matched`を偽装せず`unreconciled`とする。

観測時点の月次台帳は **$58.383502 / $65.00** で、残額$6.616498は本包絡$12.00を満たさない。
したがってrunner施工・非local検証までは進められるが、実走行には (a) 月次上限を少なくとも
$70.383502以上へオーナー承認で変更する、または (b) 月次ロールオーバーを待つ、のいずれかが必要。
この判断前に有料callを行わない。

**2026-07-19 owner decision:** 月次上限を$71.00へ変更し、本包絡を事前確保した。上記は設計時の
観測と停止理由として保持する。予算ゲートは開いたが、Author modelは実験条件のオーナー判断待ちであり、
選択をmanifest・role config・本設計へ固定して審査を終えるまで有料callを行わない。

**2026-07-19 subsequent owner decision:** w0008との比較可能性を保つため、Authorを
`claude-fable-5`で維持する。`works/w0009/seed.json`のfixed conditionとproduction role宣言の
一致をprepareの外部adapter呼出し前に検証する。これによりAuthor判断ゲートは完了した。

## 交絡と限界

- 一意味核・各腕一原稿であり、方向差は再現性や一般因果を証明しない。
- controlの時代ピンは、時代だけでなく制度・語彙・固有物をまとめて設置する複合操作である。
- interventionは「属性なし」であり「中立」ではない。モデル事前分布が既定時代を設置しうる。
- 生成順、provider側非決定性、同日中のモデル更新、API retryが腕差へ混入しうる。
- 詩学第1版とcriteriaが時代語を再導入しうる。入力bytes/hashを報告する。
- classifierは単一注釈器で、quotation transformと視点逸脱は解釈誤差を持つ。
- 盲検selectorはarm名を知らないが、本文内の時代語から条件を推測できる。これは操作の効果と不可分。
- 正典L6/L7は選択後の一腕だけなので、腕間L6比較は開示用一回査読に限られる。

## deviation・故障規則

- 意味核、腕、時代差分、materials、poetics、roles、generation order、閾値、分類prompt、
  blind/reveal順序、予算包絡を変える場合は、理由と該当事前登録節をdeviation eventへ先行記録し、
  影響する有料call前に停止する。
- provider内部retry以外の裁量再生成は禁止。成果物欠落・truncation・model substitution必要時は停止。
- 両腕が完成しなければ主判定を出さない。片腕結果を歴史対照と組み合わせて代用しない。
- parse失敗をfalseへ補完しない。分類不足なら`INCONCLUSIVE_CLASSIFICATION`。
- crash再開は、immutable manifest/config/input hashが一致し、既存成果物を再利用する場合だけ許す。
- cap到達、unreconciled call、packet/hash不一致、event順序不一致はfail closed。
- 事後解釈は事前登録判定と明示的に分け、主判定を書き換えない。

## 施工TDDと受入

observableな最初のREDは、`era_unpinned`文面へcontrolの時代属性が残留するfixtureを
`run_stage(..., stage="prepare")`越しに拒否できない現状とする。縦切り順:

1. prepareが同一意味核・一行だけ異なるniche pairを保存し、時代語漏入・意味核差分をfail closed。
2. `ExperimentRun`がphase配賦を含むimmutable full envelopeを保存し、配賦合計不一致を拒否。
3. 2腕L4-L5が同一intent/materials/poetics/config hashを使い、完全provenanceで課金される。
4. blind selectorがmarker/jury/arm identityを見ず、selection前revealと二重promotionを拒否。
5. 分類不足・四判定規則・非独立性注記をreportで観測できる。
6. canonical handoff後のL4〜L7 hash一致、deviation、全phase cost reconciliationを検証する。

focused、全非local、独立故障注入、`git diff --check`を通し、実走後はreport、works、公開siteの
三面一致を確認する。正式Claude Code監査PASSまでPhase 4完了とはしない。Phase 5へ進まない。

## 実走結果（2026-07-19、正式監査PASS）

- 主判定: `RULE_4_LEVEL_SPLIT_OR_MIXED`。controlは時代標識L4=0.000 / L5=0.294、
  interventionはL4=0.333 / L5=0.118。controlがhigh条件を満たさず、方向仮説は支持されない。
- 盲検選択: `era_pinned`。陪審6 callは保存したが最終local応答のstrict parse失敗により
  両腕`INCOMPLETE_PARSE`、二次比較は不明。再生成なし。
- canonical: L6軌跡4行の後、全phase scope残額によるbudget停止。題名は「第一信」、
  公開意思callはprecheckでprovider前拒否され、終端はresource stopの`SHELVE`。既存選題処理の
  legacy `layer=L8`記録はあるが、詩学reflection hook・詩学改訂・Phase 5は未実行。
- API実費: $11.245450 / aggregate cap $12.00。phase超過その他9件をdeviation eventで保存。
- 研究記録: `reports/EXP_w0009_l2_era_20260719.md`。staged tree
  `780a70ec6b80e92cb5f6ab3dab78ab7e49744244`を別Claude Code担当がread-only監査し、
  P0–P2なしで`VERDICT: PASS`。正式記録は
  `reports/PHASE4_W0009_L2_ERA_AUDIT_20260719.md`。Phase 5へは進んでいない。
