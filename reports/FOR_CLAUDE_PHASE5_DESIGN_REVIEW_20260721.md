# Claude CodeへのPhase 5実装前独立設計監査依頼

状態: 使用済み。2026-07-21に`VERDICT: PASS`を受領。candidate欄は未記入だったため、
実装前設計ゲートの判定として記録し、実装後正式監査とは分離する。結果は
`reports/PHASE5_PREIMPLEMENTATION_DESIGN_AUDIT_20260721.md`。
設計者: Codex（sol）
監査者: 施工者と異なるClaude Codeセッション

---

あなたはALEPH Phase 5の実装前独立設計監査者です。リポジトリをread-onlyで調査し、
候補を変更しないでください。

## 候補identity

- branch: `main`
- candidate: `<STAGED_TREE_OR_COMMIT>`
- worktree status: `<STATUS_AT_FREEZE>`

## 必読

1. `PLAN.md`。特に§7.1、§7.3、§7.4、§11、§12、§12.1、§12.2、§16。
2. `PLAN_CHANGELOG.md` 0.7.20-16。
3. `designs/next-designer-execution-plan.md` Phase 5。
4. `reports/FABLE5_RESPONSE_PHASE4_RSI_BUDGET_20260721.md`。
5. `reports/PHASE5_READ_ONLY_INVENTORY_20260721.md`。
6. `designs/instruments.md`。
7. `designs/phase5-instruments-atlas-budget.md`。
8. 必要に応じて既存実装と実走artifact。少なくとも
   `aleph/core/budget.py`、`aleph/core/work_snapshot.py`、`aleph/core/evaluation.py`、
   `aleph/explore/atlas.py`、`aleph/explore/niche.py`、`aleph/critique/review.py`、
   `aleph/meta/poetics.py`、`scripts/run_w0009.py`、w0008/w0009のexperiment artifact。

## 依頼事項

次を独立に検証してください。設計者の結論へ同意することを前提にしないでください。

1. read-only調査の観測が実装・実artifactと一致するか。観測、推論、解釈が混同されていないか。
2. `InstrumentRecord`のinterfaceが、計器ごとの異なる測定実装を無理に統合せず、
   由来・比較・欠測・校正だけを小さなinterfaceに隠しているか。
3. 計器台帳の初期9計器は、主張範囲、反例、盲点、比較identityを誠実に表すか。
   特にnoveltyの二義性、fixationの二計器分離、disagreementの欠測偏り、
   mean logprob/perplexityの名称、parse reliabilityを査定すること。
4. `AtlasIdentity`のpayloadは比較可能性に必要十分か。timestamp/path除外、input/build/output hash、
   legacy partial identityの扱いが再現性と非遡及原則を両立するか。
5. 既存`Budget`を予約で深くする設計は、check/use間競合、crash/restart、重複settle、
   provider後の実額超過を誠実に扱うか。
6. player→held-outだけの非対称補充、closing予約、owner-only不可視は、
   外部性三軸を弱めていないか。outer loopが予算保護定義を変更できる穴がないか。
7. juror slotの逐次硬化とatomic aggregate projectionは、w0009の全score欠損を再発防止しつつ、
   部分scoreによる勝敗の偽造と未登録再生成を防ぐか。
8. `WorkSnapshot.termination`と`author_epoch`の追加は既存seamを深くし、別の事実源を作らないか。
   resource stopと美的失敗を集計・site・negative map・fixationで分けられるか。
9. fixation初回校正のsealed fixtureと採用ゲートは、少数標本への過度な適合と
   「引用への変換=解決」という循環を防ぐか。
10. tracer-bullet順、受入条件、故障注入は実装者が裁量で保護定義を弱められない精度か。
11. Phase 5に含めすぎている責務があるか。分割すべき場合は、どのseamで分けても
    外部性と受入条件を失わないかを示すこと。

## 報告形式

- findingはP0–P3で分類し、必ずfile/line証拠、壊れる不変条件、最小修正案を示す。
- P3は非阻害の残余riskとして分ける。
- tests greenと設計verdictを混同しない。この段階では施工は未実施である。
- 末尾は必ず次のどちらか一行で終える。

`VERDICT: PASS`

または

`VERDICT: FAIL`
