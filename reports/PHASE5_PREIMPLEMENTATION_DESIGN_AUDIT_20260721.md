# Phase 5 実装前 独立設計監査

**監査者**: Claude Code（Opus 4.8、施工者Codexと別セッション）
**範囲**: read-only。provider call・有料実験・artifact書換なし。
**候補**: `main` / staged tree未固定（依頼書のプレースホルダは空欄のまま。設計文書4点、
参照実装、w0008/w0009実走artifactを対象に監査）
**受領日**: 2026-07-21

> このファイルはオーナーが提示したClaude Code監査結果を、意味を変えずに要約・正規化した
> repository記録であり、逐語transcriptではない。以下の判定とfindingは監査者による。
> P3反映後の実装後正式監査を代替しない。

## 0. 監査方法

依頼書の「設計者の結論に同意することを前提にしない」に従い、read-only調査の各観測を
実装ソースと実走artifactに逐一照合した。

| 調査の主張 | 独立検証 | 判定 |
|---|---|---|
| `novelty_review`は最近傍cosine距離、identity無付与 | `aleph/critique/review.py:149-183`は`1.0 - best_sim`のみ返す | 一致 |
| L2 noveltyは候補内percentile、L6 `novelty_dist`と別量。cell系は`novelty=1.0/measured=None` | `aleph/explore/niche.py:88,223-224` | 一致 |
| fixationは文字2-gram Jaccard | `aleph/meta/poetics.py:134-157` | 一致 |
| 作品横断反復を検出しない既知反例 | `tests/test_fixation_check_first_case.py:56`が`False`を固定 | 一致 |
| disagreementはvalid scoreの母標準偏差、invalid除外 | `aleph/critique/review.py:121-146` | 一致 |
| w0009二次比較の「disagreement」はmax-min（別定義） | `scripts/run_w0009.py:857` | 一致 |
| perplexityは実際はmean logprob、`exp(-mean)`でない | `aleph/materia/ai_native.py:20-24`、review artifactのunit | 一致 |
| w0009: 6 call完了後の最後のstrict parse失敗で全score欠損`INCOMPLETE_PARSE` | `works/w0009/experiment/jury_reveal.json`、`events.jsonl:000008` | 一致 |
| `Budget`に予約・poolなし、precheck/provider間で残額を他callが消費可 | `aleph/core/budget.py` | 一致 |
| 閉幕の公開意思callが最後に拒否 | decisions event 13 | 一致 |
| `WorkSnapshot`は`stop_path`/failure category/終端理由を返さない | `aleph/core/work_snapshot.py:39-59` | 一致 |
| colophonに`author_models`はあるが`author_epoch`なし、`atlas_version=null` | `works/w0008/colophon.json` | 一致 |
| w0009 identityはad hoc 2 hash、corpus/embedder/版なし | experiment report、現Atlas meta/manifest | 一致 |
| `AtlasIdentity`/`InstrumentRecord`/`reserve_batch`は未実装 | repository search | 一致 |

監査者は、read-only調査が観測証拠と解釈を明示的に分け、台帳9計器の既知反例が
実artifact由来であることを確認した。設計は外部性・非遡及・反Goodhartの不変条件を
契約レベルで備え、**P0–P2の設計欠陥は発見されなかった**。

## Findings

### P3-1 — charge回復seamと予約超過の衝突

現行`Budget.charge()`は内部で`precheck()`を呼び、超過時に`BudgetExceeded`を送出する。
一方、設計はprovider実行後の実額超過をunreconciledとして記録し、実行済みcallを
「無かった」ことにしないと要求する。事前admission（拒否可能）と事後settlement/recovery
（記録を拒否せずunreconciled化）を別seamにし、回復注入を現行precheck送出経路へ通さない
ことを、設計本文と故障注入へ明記すべきである。

### P3-2 — charge_idレベルの冪等性が現行実装にない

現行`charge()`は`charge_id`を受け取るがdedupせず無条件appendする。crash resumeで同一行を
再生すれば二重計上になるため、同一`charge_id`のchargeはno-opとして既存行を返す受入条件を
追加すべきである。

### P3-3 — closing予約と将来runの終了分類境界が未定義

closing reservationによりplayer枯渇後も正常に短く完走できる設計は妥当だが、closing
admission自体の失敗、開始後のclosing喪失、player枯渇時にclosingが生存する場合の境界を
本文で固定すべきである。前二者は未開始またはresource interruption、最後だけを
complete_shortとする。

### P3-4 — 借用matrixがcode固定であることの明示不足

manifestはpoolを選ぶだけで、player→held-outだけを許す借用matrixは`Budget`のcodeに固定し、
outer loopがmanifestで緩和できないことを明記すべきである。manifestへ借用許可fieldを
注入しても非対称性が維持される故障注入を追加する。

### P3-5 — AtlasIdentityの出力hash厳格性

generated artifactのhashをidentityに含めるため、同一corpusからの独立再構築でも出力が
bit同一でなければ別identityとなり比較不能である。これは意図的な非遡及・実artifact単位の
比較だが、同一corpusなら比較可能という将来の誤解を避けるため明記すべきである。

### P3-6 — stop signalから四分類への写像表がない

`stop_path`とL7 `failure_category:*`を厳密に突合する一方、そのsignalから
`aesthetic_failure`、`resource_stop`、`publication_choice`、`safety_or_rights`への写像が
未記載である。少なくともbudget→resource_stop、品質床→aesthetic_failure、公開しない判断→
publication_choiceを固定すべきである。

## 依頼事項への総括回答

- `InstrumentRecord`は測定計算をdomainに残し、由来・比較・欠測・校正だけを隠すため合格。
- 9計器は実artifactの反例に基づき、novelty二義性、fixation分離、disagreement欠測偏り、
  mean logprob命名、parse reliabilityを正直に扱っている。
- `AtlasIdentity` payloadは必要十分。output hashで上流非決定性を推測せず、P3-5の注記だけを要する。
- Budget予約はcheck/use競合、crash、重複settle、実額超過を契約で網羅する。P3-1/P3-2は
  実装時のseam警告である。
- 非対称補充とowner-only不可視は外部性を弱めない。P3-4でさらに固定できる。
- juror逐次保存とatomic projectionはw0009型欠損の再発を防ぎ、部分scoreによる勝敗偽造を拒否する。
- termination/author_epochは既存seamを深くし、別の事実源を作らない。P3-6の写像表だけを補う。
- fixation校正はsealed fixture、provisional表示、定量精度非主張によりn=5の残余riskを開示している。
- 5A→5B→5Cは一方向依存で、過剰責務や追加分割の必要は認められない。

test greenと設計verdictは別である。本監査は施工前のread-only設計監査であり、実装は未着手。
findingはすべて非阻害のP3で、修繕・再監査を強制するP0–P2は発見されなかった。

`VERDICT: PASS`
