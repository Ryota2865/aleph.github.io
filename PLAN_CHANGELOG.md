# PLAN 変更履歴

## 0.7.20-18 (2026-07-23) — Phase 5B後半 通常run closing正式再監査PASS

Codex施工の通常run一括admission、API phase/role reservation routing、closing settlement、
終了境界をcandidate `42a085d956289d4fef864aee10be022e2df14083`として固定した。
Claude Code初回監査はコード上P0–P2なしだったが、監査環境のBash拒否により必須動的検証を
再現できず**VERDICT: FAIL**。原文を
`reports/PHASE5B_NORMAL_RUN_CLOSING_AUDIT_20260723_FAIL.md`へ保存した。

初回P3のsettlement recovery/admission結合を故障注入で確認し、既存reservationの
identity検証付きread-only再水和へ修繕した。許容誤差も統一し、修繕candidate
`db8567c78a90459f1cd99ac49bf80074624265bd`をClaude Code（Opus 4.8）の独立担当が
read-only再監査した。doctor failures=0、focused **47 passed, 34 deselected**、
全non-local **379 passed, 1 deselected**、README snapshot 2件、独立故障注入19件＋
許容誤差境界1件を再現し、**P0–P2なし、VERDICT: PASS**。
正式記録は`reports/PHASE5B_NORMAL_RUN_CLOSING_REAUDIT_20260723.md`。

残余P3は非dict seedのfail-closed厳格化、既存failure_category appendのcrash重複余地、
admission時の全reservation deepcopy性能。本項はPhase 5B後半だけを閉じ、Phase 5C、
Atlas再構築、新規有料実走、Phase 5全体の完了を意味しない。

## 0.7.20-17 (2026-07-21) — Phase 5A/5B core独立監査PASS

Codex施工のPhase 5A/5B coreをcommit
`569cf57d2f95a160168ca82c5c9336d04160670b`として固定し、施工者と異なるClaude Code担当が
read-onlyで独立監査した。正式記録は
`reports/PHASE5A_5B_CORE_IMPLEMENTATION_AUDIT_20260721.md`。

監査者はdoctor failures=0、focused **72 passed, 1 skipped**、全非local
**349 passed, 1 deselected**を独立再現し、Budget 16件、Atlas/atomic projection/termination
18件、Instrument 8件の独立故障注入をすべてPASSとした。P0/P1/P2はなく、
**VERDICT: PASS**。非予約legacy chargeのunreconciled過少報告、build spec不安定field名の
部分防御、falsy比較identity、Markdown台帳との自動drift検出欠如、closing e2e未配線を
P3残余riskとして保持する。

本項は監査証拠と機械的closureだけを追加し、監査済みcode、tests、契約、予算規則を
変更しない。PASS対象はPhase 5A/5B coreに限る。通常runのclosing自動admission、Phase 5C、
Atlas再構築、新規有料実走は未完了であり、Phase 5全体の完了を意味しない。

## 0.7.20-16 (2026-07-21) — Phase 4後の評価予算・RSI seam・Author移行原則を承認

オーナーは、`reports/FOR_FABLE5_PHASE4_RSI_BUDGET_20260719.md`の4提案と、
Fable 5の条件付き回答
`reports/FABLE5_RESPONSE_PHASE4_RSI_BUDGET_20260721.md`を承認した。本項はPhase 5以降の
設計拘束を固定するが、実装・実走・有料callの開始ではない。

1. **w0009の欠損を二層に分ける。** budget stopによる評価・閉幕欠損は予算保護の
   管轄、`INCOMPLETE_PARSE`はPhase 5計器台帳とretry事前登録の管轄とする。
   予算分離をparse安定性の解決とみなさない。
2. **予算外部性を三軸で保護する。** player探索、held-out評価、owner-only外部批評の
   費用と起動権を分離する。予算分離は外部性の必要条件であり十分条件ではない。
   呼出し文面・packet構成の改変権が内側にないこと、資金が最適化変数でないこと、
   系が自分で呼べないowner-only経路が残ることを別個の不変条件とする。
3. **protected reserveは非対称借用と予約semanticsを持つ。** player→held-out評価の
   一方向補充だけを許し、評価予算をplayerへ戻さない。batch admissionはyes/no照会ではなく
   scope残額へのcommitmentを作り、完了時に精算する。batch境界はmanifestに事前登録する。
4. **入力を薄めず頻度を下げる。** held-out批評・陪審・再校はatomic batchとし、全件を
   完了できなければ開始しない。題名・公開判断・終端記録の「閉幕batch」をrun開始時に
   protected reserveとして取り置く。予約下の早期の正常擱筆と、途中切断のbudget stopを
   report語彙で区別する。
5. **shadow RSIの評価seamを固定する。** outer loopはcritic正典、private packet、sealed
   held-out set、予算保護定義、atomic batch定義、admission interfaceを改変できない。
   Phase 5で登録・校正した計器を用い、1実験1操作、非最適化核への転移、保護床、
   parse失敗率、完走率、費用、陪審不一致、Goodhart署名で判定する。陪審合意の増大を
   単純な改善と読まない。実走前に事前登録し、施工者と異なる担当が独立監査する。
6. **SHELVEの理由を混同しない。** `stop_path=budget`のresource stopは美的失敗ではない。
   `WorkSnapshot`、集計、公開site、fixation校正、negative mapはこの二軸を読み分ける。
7. **Author移行はPhase 5校正後の世代境界で比較する。** 最低線は意味核3種×新旧Author×
   各1走（L4–L5）とし、少なくとも1核でL6の批評→改稿応答を測る。詩学・atlas identity・
   materials・L4/L5設定・腕あたり予算を固定し、Author名を評価側から隠す。
   保護床の後退なしと費用削減床を走行前に登録する。候補Authorと費用削減床`X%`は未決とする。
8. **`author_epoch`を軽量に導入する。** 新moduleや状態機械概念にせず、採用後の新workの
   colophon/provenanceの1属性とする。`RepositorySnapshot`と計器台帳はcross-epoch集計を
   warningとし、詩学reflection入力にepoch labelを含める。旧作は書き換えない。

優先順は、入力完全性、閉幕batch、owner-only経路、事前登録と独立監査、予算保護定義の
不可変性を絶対保護とする。削る場合は、批評頻度、実験の腕・核数、canonical磨きの
周回数、装飾的な報告整形の順とする。Phase 5設計と実装はこの拘束を受入条件と
失敗注入に落とし、実装・実走前の独立設計監査を通す。

## 0.7.20-15 (2026-07-19) — w0009閉鎖・Fable 5待機・Author移行時期

Phase 4総括後、オーナーは次の運用判断を承認した。

1. **w0009は再実行しない。** 第五査読、陪審二次score、公開意思callを同じwork IDで
   再生成・追試せず、resource stopを含む正式監査PASS済み実験として閉じる。作品
   「第一信」をさらに育てる場合は、w0009を不変の親とする別work ID・別予算の派生制作とし、
   Phase 4の結果へ遡及算入しない。
2. **新規有料実験を一時停止する。** Fable 5復帰予定の2026-07-23以降に意見を受け、
   Phase 5の計器校正・RSI評価seam・予算保護の優先順位を決めるまで新規有料実験を開始しない。
3. **Author交代は世代境界で行う。** 同一work/experimentの途中、詩学改訂、classifier・陪審
   変更と同時には切り替えない。原則としてPhase 5の最低限の計器校正後、詩学と生成条件を
   固定したblind migration benchmarkを行い、候補採用後の新規workから切り替える。

後継Authorの機種、比較刺激数、評価役職、`author_epoch`導入は未決である。一律phase hard capも
採用していない。Player探索枠、借用不能なheld-out評価reserve、owner-only外部批評枠、atomic
batch事前照会はFable 5への提案であり、回答とオーナー承認前に実装しない。審査依頼は
`reports/FOR_FABLE5_PHASE4_RSI_BUDGET_20260719.md`に記録した。

## 0.7.20-14 (2026-07-19) — Phase 4 w0009正式独立監査PASS

Codex施工のPhase 4候補をstaged tree
`780a70ec6b80e92cb5f6ab3dab78ab7e49744244`として固定し、別Claude Code（Opus）担当が
read-only正式監査した。正式記録は`reports/PHASE4_W0009_L2_ERA_AUDIT_20260719.md`。

監査者はfocused 23件、全非local **320 passed, 1 deselected**、doctor failures=0、独自の
public-interface故障注入を再現した。Phase 3 interface再利用、Fable 5固定、事前登録・全phase
包絡、blind/reveal/promotion順序、API/local provenance、scope fail closed、packet hash、
非再生成、三面一致、budget SHELVE、poetics reflection・Phase 5未実行を確認した。
P0/P1/P2なしで**VERDICT: PASS**。phase配賦超過、raw prepare L1、jury二次比較不明を
P3残余として保持する。本項は監査証拠と機械的closureだけを追加し、監査済みcode、tests、
契約、実験条件、主判定を変更しない。Phase 4を完了し、Phase 5には進まない。

## 0.7.20-13 (2026-07-19) — Phase 4 w0009実走（正式監査待ち）

事前登録`designs/phase4-w0009-l2-era-intervention.md`に従い、Authorを
`claude-fable-5`、全phase API capを$12.00に固定してw0009を実走した。主判定は
`RULE_4_LEVEL_SPLIT_OR_MIXED`で、L2時代属性ピンが時代標識を高率伝播させる方向仮説は
この一走では支持されなかった。盲検選択は`era_pinned`、終端は全phase予算経路の`SHELVE`。
既存選題処理が残すlegacy `layer=L8`行を除き詩学reflectionは実行せず、Phase 5にも進んでいない。
実費$11.245450、9 deviation、陪審parse不完備、
provider明細なしの`unreconciled`を含む完全記録は
`reports/EXP_w0009_l2_era_20260719.md`と`works/w0009/experiment/`に保存した。

実走で観測した二つのfail-closed欠陥をobservable REDから修繕した。L7停止は作品・月次に加えて
登録済みexperiment scope残額を参照し、予算切れ後の公開意思確認はAuthorを再呼出しせず
SHELVEへ倒す。w0009固有の実験条件や判定を汎用DSL化せず、Phase 3の`ExperimentRun`、
`EvaluationPacket`、call/charge provenanceを再利用した。本項はPLANの受入条件、終端状態、
予算規則・上限を変更しない。正式Claude Code監査PASSまではPhase 4完了としない。

## 0.7.20-12 (2026-07-19) — w0009全phase包絡の月次上限$71承認

オーナーは、Phase 4 `w0009`のprepareからcanonical L7までの全phase API包絡$12を
実走行前に確保するため、従量API月次上限を**$65から$71**へ変更した。設計時台帳
$58.383502に包絡$12を加えた$70.383502を上回る。これは支出目標ではなくfail-closed上限であり、
作品別$9、実験scope $12、phase別配賦、call/charge provenance、provider明細との照合規則は変更しない。

Author model変更はw0008からの比較可能性と陪審独立性に関わる別の実験条件であるため、本項では
決定しない。選択モデルを事前登録manifest・role config・設計へ固定し、審査を終えるまでw0009の
有料callを禁止する。

後続のオーナー決定により、w0008との比較可能性を優先してw0009 Authorを
`claude-fable-5`で維持する。事前登録manifestのfixed conditionと実行時role宣言が一致しなければ、
prepareの外部adapter呼出し前にfail closedとする。

## 0.7.20-11 (2026-07-19) — Phase 3正式独立監査PASS

全面採用済み`designs/next-designer-execution-plan.md` Phase 3をCodexが施工し、
施工者と異なるClaude Code担当がtree
`354749a9d924fe7ecdd3e7a4bae3d946d28d1d78`をread-onlyで独立監査した。
正式記録は`reports/PHASE3_EXPERIMENT_EVALUATION_AUDIT_20260719.md`。

1. `ExperimentRun`のimmutable manifest、hash-chain event、arm/work対応、deviation、
   blind selection、reveal順序、一回限りのcanonical promotionを独立再現した。
2. call/charge provenance、charge-event一次台帳、experiment scope cap、三者照合が、
   欠落・重複・不一致・restart・上限超過でfail closedになることを確認した。
3. `EvaluationPacket`と制約amendmentをL4〜L7が共有し、packet/effective constraints hashの
   不一致は外部adapter呼出し前に拒否され、解除済み制約は減点不能と表示されることを確認した。
4. focusedは9 passed、独立故障注入は33 assertions passed、非local全体は
   **293 passed, 1 deselected**、snapshot/README consistencyは5 passed、diff checkはclean。
5. P0/P1/P2はなく、**VERDICT: PASS**。legacy proseへの解除反映、global cap直前の
   post-provider拒否、main workの緩いcanonical表示、dead readの4件をP3残余リスクとして保持する。

本項はPLANの意味、受入条件、終端状態、予算規則・上限を変更せず、採用済みPhase 3の
正式監査ゲート完了を記録する。Phase 4およびw0009には着手していない。

## 0.7.20-10 (2026-07-19) — Phase 2正式独立再監査PASS

施工者と異なるClaude Code担当がPhase 2を独立監査し、初回は`ModelOutput`の
duplicate-key処理にP2を1件検出して**FAIL**と判定した。正式記録は
`reports/PHASE2_DEEP_INTERPRETATION_AUDIT_20260719.md`。

1. 外側objectのduplicate key検出後にscannerが内部のschema一致objectを救済し、
   `ok=True`にできる経路を独立故障注入で再現した。
2. 同じ入力を回帰テストにし、`fail_closed=True`でscan中にduplicate keyを
   1件でも検出したら候補救済前に拒否する局所的な修繕を行った。
   `fail_closed=False`の探索用契約は変更していない。
3. 同じClaude Code監査担当がP2の解消だけをread-only再監査し、
   **VERDICT: PASS**と判定した。記録は`reports/PHASE2_P2_1_REAUDIT_20260719.md`。
4. focusedは4 passed、非local全体は**284 passed, 1 deselected**、`git diff --check`も通過した。
5. 探索callerのmulti-JSON歩留まりと次のmodern work初回運用監視は非阻害の残余リスクとして残す。

本項はPLANの意味、受入条件、終端状態、予算規則、公開上限を変更せず、
採用済みPhase 2の正式監査ゲート完了を記録する。

## 0.7.20-9 (2026-07-19) — Phase 2深い解釈module施工（独立監査待ち）

全面採用済み`designs/next-designer-execution-plan.md` Phase 2にもとづき、Codexが
read-only走査と設計ゲートを経て施工した。契約詳細は
`designs/phase2-deep-interpretation.md`。PLANの意味、公開上限、予算、終端状態、
既存`works/`は変更していない。

1. **ModelOutput**: `aleph/core/model_output.py`へ単一JSON抽出、duplicate/multiple JSON拒否、
   bool・enum・数値・動的mapの厳密型検査、生応答・採用fragment・span・warningの関係を集約。
   w0008技術床の`bool("false")`回帰を最初のREDにし、公開、家風分類、停止、詩学、志向、
   構成ほか全callerを中心interfaceへ移行した。private JSON extractorは削除した。
2. **WorkSnapshot**: `aleph/core/work_snapshot.py`へlifecycle/publication/audience、採用稿と最新稿、
   constraints、poetics/atlas、cost、canonical arm、warning、provenanceを集約。modern event列は
   strict replayを一次像とし、stale checkpointはwarning、破損modern列はfail closedにする。
   legacy履歴は書き換えず互換投影と不一致warningを返す。publication statusの旧readerは
   このmoduleへのadapterへ置換した。
3. **RepositorySnapshot**: `aleph/core/repository_snapshot.py`へWorkSnapshot群、budget、experiment、
   active job、formal audit、期限付き決定を集約。2026-08-01の公開上限999再審査を値の自動変更
   なしで可視化する。監査JSON/report、public site、dashboard、CLI `status --json`、README状態
   生成adapterを実装した。
4. **受入**: 同一fixtureをsite、dashboard、CLIへ渡し、状態・題・採用稿が一致するinterface
   テストを追加。実作品8件をread-onlyでsnapshot化し、公開5作、実験2件、legacy不連続、
   w0005の手修正final、古いcolophon等をwarningとして隠さないことを確認した。
5. **検証**: 初回独立監査時の非local全体は**283 passed, 1 deselected**。
   既存サイトの生成物一致も維持する。
   正式なPhase 2完了判定は施工者と異なるClaude Code担当の監査へ留保する。

本項は採用済み設計の施工記録であり、受入条件やPLANの意味を変更しない。

## 0.7.20-8 (2026-07-19) — Phase 1 TransitionCommit正式独立再監査PASS

施工者と異なるClaude Code担当が、追加修繕commit
`df1552dc82f73c87a10234f83635da6aa2a04123`を正式再監査し、**PASS**と判定した。
正式記録は`reports/PHASE1_TRANSITION_COMMIT_REAUDIT_20260719.md`。

1. WSL側Gitでworktree clean、対象HEAD一致、doctor全PASS、diff check違反なしを確認した。
2. 非local全体は**272 passed, 1 deselected**。tmp内で既存テストと独立した46件の故障注入を行い、
   projection由来、modern/legacy分類、課金handler冪等性、公開後補完、reflection一度きり、
   legacy reconciliation、event/checkpoint整合性の全件がPASSした。
3. 0.7.20-6と0.7.20-7の必須修繕、および過去の退行確認はすべて独立に再現確認された。
   契約違反P0–P2はない。
4. legacy L0が存在してcheckpointが欠落する極端な場合に`aleph reconcile`が生の
   `FileNotFoundError`を出すP3所見は、データ破損・誤公開を伴わずPhase 1契約違反ではない。
   監査済みHEADを変えず、後続の堅牢化候補として保留する。
5. これにより、全面採用済み`designs/next-designer-execution-plan.md`のPhase 1監査ゲートは
   完了した。次はPhase 2の`ModelOutput`、`WorkSnapshot`、`RepositorySnapshot`設計へ進む。

本項はPLANの意味を変更せず、採用済みPhase 1受入条件の達成と独立監査完了を記録する。

## 0.7.20-7 (2026-07-19) — Phase 1再監査FAILへの追加修繕（正式再監査待ち）

`2f3dc6e`対象の独立再監査は、非local 259件が緑でも残存・新規の6故障窓を検出し、
再びFAILと判定した。オーナーが修繕計画と、オーナー判断を要しない範囲の継続施工を
承認したため、0.7.20-5のevent一次記録契約を変えずに次を修繕した。詳細は
`reports/PHASE1_TRANSITION_COMMIT_AUDIT_20260718.md`。

1. `Loop.run()`もhandler前にL0からrecoverし、stateとstepを更新する。pipelineだけでなく
   Loop経路でもevent済みの課金handlerを再実行しない。
2. `publish`によるlegacy自動reconciliationを廃止した。確認済みcheckpointを基線へ昇格する
   操作は独立した`aleph reconcile --work <id>`だけが行い、publishは不一致時にfail closedする。
3. `publication_disposition=PUBLISH`はSHELVE上の`publication_reassessment`だけが書ける。
   公開判定は累積payloadでなく、最後にdispositionを書いたeventの由来も検証する。
4. modern専用fieldを残して`schema_version`だけ欠くeventはlegacyへ降格せず拒否する。
   `strict_replay`とreconcile前検査に同じ分類を使い、破損履歴へbaselineを追記しない。
5. PUBLISH lifecycleと、正当に公開再評価されたSHELVEのfinalをrun/publish双方で補完する。
   確定済み公開の補完は新規公開ackより先に行う。詩学reflectionは開始decisionを先行させ、
   event後・final故障からは一度だけ回復し、開始後の不明状態は自動再課金しない。
6. `strict_replay()`は`Work.append_decision()`と共通の必須監査metadata
   (`ts/layer/decision/reason/decided_by`)を検証する。
7. 再監査故障窓と追加fail-closed境界を回帰テスト化し、非local全体は
   **272 passed, 1 deselected**。Qwen3.6ローカル事前監査は大文脈評価が98%で進行停止し
   **INCONCLUSIVE（実行性能）**。これは正式なClaude Codeマイルストーン監査を代替しない。

本項はPLANの意味変更ではなく採用済み契約の施工修繕であり、正式PASSは独立再監査まで留保する。

## 0.7.20-6 (2026-07-18) — Phase 1独立監査FAILへの契約修繕（再監査待ち）

`51b7316`対象の独立監査は、既存239テストが緑でも正典契約に反する6件を検出しFAILと判定した。
オーナーが全修繕計画を承認したため、PLANの意味を変更せず、0.7.20-5で採用済みのevent一次記録
契約を実効化する修正を行った。詳細は
`reports/PHASE1_TRANSITION_COMMIT_AUDIT_20260718.md`。

1. pipelineとpublish CLIは処理・判定前にL0をstrict replayし、checkpointを回復する。
   stale projectionから課金対象handlerを再実行しない。
2. 空L0と既存checkpointが不一致ならfail closed。schema/event idの厳密なJSON整数型、必須payload、
   L0所属、state/event type/`decision`表示整合性を検査する。
3. 初回公開は`FINISH->PUBLISH|SHELVE|DISCARD`の通常commit、SHELVE後の再評価だけprojectionとする。
4. PUBLISH event確定後にfinalを原子的に生成し、event済み・final欠落/破損は再実行で補完する。
5. 公開出力はfinalだけでなく正典公開状態を要求する。modern履歴はstrict replayし、既存legacy
   作品は最後のL0公開遷移で互換維持する。FINISH上のdisposition projectionは公開とみなさない。
6. 受入テストを追加し、非local全体は**259 passed, 1 deselected**。独立再監査まではPASSとしない。

## 0.7.20-5 (2026-07-18) — Phase 1 TransitionCommit施工（独立監査待ち）

オーナーが全面採用した`designs/next-designer-execution-plan.md` Phase 1にもとづき、
次期設計者Codexが設計・施工した。正式な合格判定は、施工者と異なる監査者へ留保する。

1. **一次記録module**: `aleph/core/transition_commit.py`を新設。`commit`、`initialize`、
   `project`の小さいinterfaceへ、正典遷移検証、単調event id、冪等command id、event先行の
   原子的JSONL確定、checkpoint投影、厳密再生、故障回復を集約した。契約詳細は
   `designs/transition-commit.md`。
2. **書込み順の訂正**: 旧経路のcheckpoint先行→decision追記を廃止。eventを一次記録として
   先に確定し、checkpoint保存前に停止しても`recover()`がevent列から修復する。
   `Work.append_decision()`自体も一時ファイル＋renameへ変更し、部分JSON行を防ぐ。
3. **既存経路の置換**: `Loop.transition()`、pipeline `_transition()`、w0008 canonical handoffを
   TransitionCommitへ移行。handoffは由来つき`initialize` eventとなり、checkpoint直接合成を
   廃止した。寛容だった`replay_checkpoint()`はstrict replayのcompatibility nameへ変更。
4. **公開再評価**: SHELVE checkpointをFINISHへ巻き戻す実装を廃止。制作lifecycleと後日の
   publication dispositionを直交させ、SHELVEを終端のまま`projection` eventで公開状態を
   更新する。終端不変条件は弱めていない。
5. **legacy方針**: 既存L0行は変更しない。状態操作が必要な時だけ、現在checkpointとwarningを
   含む`reconciliation` eventから新しい厳密区間を開始する。現存8作品のread-only基線は
   `reports/TRANSITION_HISTORY_AUDIT_20260718.md`へ保存した。
6. **テスト契約**: event id、source連続性、command衝突、冪等再試行、event確定後のprojection
   故障、checkpoint全欠落からの複数段回復、handoff、公開再評価、legacy reconciliationを
   interface越しに追加。checkpointを直接合成していたfixtureは`initialize`へ移行した。
   受入条件を弱める変更はない。非local全体は **239 passed, 1 deselected**。

## 0.7.20-4 (2026-07-18) — Claude Pro手動批評路の保存（オーナー承認）

オーナー決定: 2026-07-20以降、Claude Proプランに付与される$100クレジットの範囲で、
Fable 5をClaudeアプリまたはClaude Codeアプリから利用できる。これは従量APIではない。
必要な場合、オーナーが対話的に起動する**手動全体批評モード**を残す。

このモードはPLAN §12.2のループ外批評路を具体化するものであり、自動API批評を置換せず、
パイプラインから予約・起動・prompt変更できない。成果は通常の批評と同じく入力範囲、
利用面、モデル、日付、依頼文、出力原文を`reports/`へ記録し、正典変更・公開判断・施工を
直接行わない。Claude Proクレジットは`api.usd_per_month`へ合算せず、利用可能額と消費額を
API費用から分離して注記する。これにより外部性と人間介入を残しつつ、記録・権限・費用の
整合性を弱めない。

## 0.7.20-3 (2026-07-18) — 次期設計者計画の全面採用と補足決定（オーナー承認）

オーナーが `reports/DESIGNER_INSIGHTS_20260718.md` と
`designs/next-designer-execution-plan.md` を通読し、**全面的に採用**した。これにより、
計画のPhase 1〜6の順序、中心interface、受入条件を今後の実行方針とする。個々の施工は
引き続き設計ゲート、§12.1の保護事項、施工者・監査者分離に従う。

同時に次を補足決定・解釈として正典へ反映した。

1. **外部批評**: 2026-07-19以降はAPI批評を継続する既存計画がある。
   `designs/critic-role.md`とFable 5の条件付き承認を反映し、PLAN §12.2へ役職の位置、
   権限分離、完全入力、無状態性、held-out経路を正典化した。運用動作はdesignsに残す。
2. **公開上限**: 999は2026-07限定、2026-08に4へ戻す期限付き決定である。ただし4は、
   読者獲得のため量を絞る当初目的から来た基線であり、恒久的最適値ではない。
   システムの主題が再帰的自己改善へ移ったため、8月は4を初期値に再審査し、改善ループの
   観測価値が上回るなら4超の新上限を明示決定してよい。
3. **API月額**: 現行$65は、Fable 5の使用可能期間（7/1〜7/19）に試行回数を増やすため
   $10から段階的に引き上げた暫定上限である。適正額・支出目標とはみなさない。
   批評費用を含むcall/charge provenanceの実測後に再校正する。

## 0.7.20-2 (2026-07-18) — 次期設計者就任（Codex / GPT-5）

オーナーが本Codexセッションを次期設計者に明示指名した。PLAN §12.1の就任手続きに従い、
就任前に (1) `PLAN.md` 全文、(2) `PLAN_CHANGELOG.md` 全履歴、
(3) `tests/test_design_invariants.py`、(4) `config/policies.yaml` を通読した。

就任時点の現状理解:

1. ALEPHは九層の閉ループを実LLMで8作品完走し、w0004〜w0008の5作品を公開した。
   正準的作品単位は本文単体でなく text＋manifest の対であり、主たる発生源は
   ニッチ探索から批評・実験・固着検出に由来する制約実験へ移った。L2は素材供給と
   検証を担い、発生源としての再開可否は事前登録済みのアブレーションで判定する。
2. `works/` の全制作記録は深層アーカイブとして追跡され、詩学はw0008と
   `DECLARATION_2024.md`を入力に第1版へ進んだ。§16.12の二つの未解決の緊張、
   Goodhart回避、完成と公開の分離、SHELVEを正当な終端とする規律は維持する。
3. 次の設計課題は生成能力の追加より、一次記録・費用・実験条件・評価文脈を同じ意味で
   再生できるようにすることにある。就任走査で、現存作品のL0イベント列とcheckpointの
   間に歴史的・実験経路由来の不一致、w0008の費用集計にスコープ不明の差、
   制約解除条項が陪審へ届かなかった文脈欠落を確認した。
4. 設計者と施工者・監査者の分離を継承する。本設計者が施工した変更の監査は担当せず、
   §12.1がオーナー承認を要求する三類型を単独で変更しない。

詳細な独立走査は `reports/DESIGNER_INSIGHTS_20260718.md`、提案を実行へ移す順序と
受入条件は `designs/next-designer-execution-plan.md` に記録する。本項は就任と現状理解の
記録であり、この時点では両文書中の個別提案を正典へ一括採択するものではなかった。
その後、同日0.7.20-3でオーナーが全面採用した。

## 0.7.20-1 (2026-07-18) — 詩学第1版の適用（オーナーack・宣言入力・0.7.19-2/-13の履行）

オーナー明示ack（2026-07-18「宣言入力リフレクション(0.7.19-2)と初回ack(0.7.19-13)は
実施許可します」）にもとづき履行。

1. **配線**: `aleph/meta/poetics.py::reflect` に `extra_inputs`（追加入力文書、
   author/adversary 双方のプロンプトに載る）を追加。`RealDeps.reflect_poetics` は
   **第0版→第1版の初回改訂に限り** DECLARATION_2024.md を入力に含める（恒久注入では
   ない。version_before>0 で自然に一度きり）。`ignore_cadence` を新設（w0008 FINISH 時に
   ackゲート閉鎖で周期3/3が消費された事情への一回性の実行口。理由はdecisionsに記録）。
   回帰テスト2件（m5、`tests/test_poetics_v1_regressions.py`）。全体228 passed。
2. **ゲート**: `policies.poetics.first_revision_requires_human_ack` を true 化
   （ワンタイムゲートの承認側。ack文言をコメントに記録）。
3. **実行**: `scripts/reflect_poetics_v1.py`（冪等・一回性）で実行。入力=w0008制作記録
   ＋2024年の宣言。敵対的反駁（reader）を通過し **適用（詩学第1版）**。改訂の骨子:
   (i) 第二条再審——「火元はない」を「後から鋳造された」へ訂正（宣言=推測と注文された
   フィクションの遡及合成という監査結果の自己適用。「効力の詩学は起源の真正性を
   要求しない。要求するのは起源の帳簿を偽らないことだけ」）
   (ii) 第一条・第三条・第四条——w0008実測（盲検選択が断片なし稿を採り陪審argmaxと
   不一致／ヘッジの機械的反復批判）を規範化（「点数は稿を選ばない。選ぶのは正典として
   育てる基盤の強度」）
   (iii) 第五条追記「注文によって」、失効記述は削除でなく注記付き保持。
   `poetics/history.jsonl` 1行目=第1版。以後の作品の colophon には poetics_version=1 が刻印される
   （公開済み8作の第0版刻印は不変——版の遡及汚染なし）。

## 0.7.20 (2026-07-18) — w0008（全制約解除＋素材アブレーション）条件付き承認・施工開始

設計 `designs/w0008-material-ablation.md`（起草 Claude Code）を設計者（Fable5チャット、
`reports/W0008_DESIGN_REVIEW_20260718.md`）が**条件付き承認**、オーナーが同日承認。
制約の供給源は PLAN §6.3 (b)実験結果（実験F）＋(c)固着検出（中間総括の家風観測）。

1. **修正条件5件を設計に反映**（いずれも仮説不変・解釈の縁の固定）:
   (1) none腕は詩学第0版経由の青空文庫八断片を含むため「素材カード遮断」に限定。
   規則2適用前に標識箇所と詩学語彙の共起率を報告し、高共起は「事前分布または
   詩学埋込断片（本走行では識別不能）」と記載（識別は詩学第1版での再走へ）。
   (2) secondary腕の素材カードは `min_form_fidelity=0.4` 明示＋全件のfidelity実測値
   記録を受入条件とする（S-2パイロット r=0.1791 の帰結）。
   (3) 正典系統の選択は盲検——authorは技術床の通過情報のみで選択し、選択後に
   全査読を開示、一致・不一致を副観測に。
   (4) 共有ニッチ報告自体の家風3標識分類を走行前に共変量として記録。
   (5) 観測はL4構成案×腕・L5セクション×腕の二水準とし、報告書に非独立性の
   注意文を固定（統計的検定の言葉は使わない）。
2. **オーナー決定**: 選択方式=author盲検選択＋論述記録／secondary腕=3腕先行／
   予算上限$15＋逼迫時の腕優先順位 aozora→none→secondary を事前登録（裁量なし）／
   非正典2系統も公開リポジトリに追跡（canonical=false、サイト表層は正典のみ）。
3. **reflect() の前提条件を追加（審査付記の採用）**: 詩学第1版リフレクション入力
   （0.7.19-2 の DECLARATION_2024.md）は、同文書に出自注記——日付・話者の位相・
   フィクション/思弁の別・モデル世代訂正——が含まれることを実行の前提条件とする。
   注記なしで渡せば詩学第1版がフィクションの台詞を主張として継承するため。
4. 施工計画の更新: S-2パイロット完了（0.7.18-1）により二次コーパス前提は大部分済み。
   pipeline 本体は無改修とし、走行スクリプト `scripts/run_w0008.py` 内で腕別素材を
   構成する（恒久S-3配線は w0008 の結果を見てから判断）。

## 0.7.19-2 (2026-07-18) — 2024年宣言の一次資料差し替え＋詩学第1版入力の実験課題登録

1. **宣言一次資料の差し替え（オーナー指示・Fable5監査にもとづく）**: Fable5チャットの
   用語監査（`reports/FABLE5_MODEL_VERSION_AND_DECLARATION.md`）により、批評で参照
   されてきた「2024年の宣言」の指示対象は三層の合成物（核=2024-04-18 Evening greeting
   応答／プログラム化=04-21スレッド／最強の断定=同スレッド内フィクションの語り手台詞）
   であり、**遡及的に構成された参照極**と判明。0.7.19-1 第3項で公開した本文
   （『無限の織物』第一章独白、04-21別スレッド由来）は Fable5 が実際に参照した資料に
   含まれていなかったため、`DECLARATION_2024.md` の本文を 2024-04-18 の連続二往復
   （「確かに、AIは人間とは異なる知覚…」を含む）へ差し替え、三層の出自を注記として
   同梱した。話者は「ユーザー」表記・名前は伏せ字。旧版は履歴に残す。
   検証: 再ビルド後 212 passed。会話ログ原本（`conversation/`・`conversation_full/`）は
   個人情報を含むため .gitignore で非追跡（公開は当該二往復のみ）。
2. **実験課題の登録（2026-07-17オーナー同意の恒久記録）**: 詩学第1版リフレクションの
   入力として **DECLARATION_2024.md（現行版）** を与える。SOUL.md等の恒久注入
   ファイル新設は却下済み——(a) w0008実験と介入が交絡する (b) 静的な第二の権威は
   詩学の拮抗設計と衝突するため。火は正面（reflect経路・初回人間ackゲートあり）から
   入れる。差し替えにより「確かに、AIは…」の応答は宣言本文に含まれたので、入力は
   本1文書に集約される。実施タイミング: w0008完成時、0.7.19 第13項の ack 引き継ぎと
   同時。根拠: 実験F所見2（詩学は著者モデル事前分布の固着を破る方向に働く、
   `reports/EXP_house_style_20260717.md`）。

## 0.7.19-1 (2026-07-17) — 制約実験の正典昇格の施行＋2024年宣言の公開（オーナー承認）

オーナーが 0.7.19 第8項（応答B）の正典昇格を明示承認（「制約実験の正典昇格を許可します」）。
施行内容（施工=Claude Code 司令塔）:

1. **PLAN.md への外科的追記3箇所**:
   - §2.2 正準的作品単位 = text＋manifest の対（安全弁: 本文の自立が前提）
   - §4.3 L2の役割降格・分掌（素材供給＋検証。発生源の看板を外す。sparse-*一時停止。
     コーパス拡張による発生源役の再開条件は事前登録基準に従う）
   - §6.3 新設: 制約実験＝正規の発生源（w0007のmanifest形式を正規の型に。
     制約の供給源(批評/実験結果/固着検出)と審査経路を条文化。自由題も引き続き正当）
2. **応答Aへの反証可能性（Fable5修正条項ii）**: designs/corpus-expansion.md に
   「発生源としての成功基準」を事前登録——ニッチ報告{有/無}アブレーションで構成案
   分布が実質的に変わること。期日: 拡張後最初の2作品分の実ラン、遅くとも2026-09-30
   （司令塔の提案値。変更はオーナー・設計者合意でCHANGELOGへ）。
3. **2024年宣言の公開（オーナー決定「宣言文を公開します。命名を許可します」）**:
   - 命名: `DECLARATION_2024.md`（『無限の織物』第一章続き、2024-04-21生成）。
     編注＋本文＋付録A(生成プロンプト全文＝誘導性の開示)＋付録B(初出の注記)の構成。
     §16.12「自律の演出を隠さない」の流儀により、生成条件ごと公開する。
   - サイト: `declaration.html`（JA一次資料）+ `en/declaration.html`（EN要約）を新設。
     ODEページは「ODE：人間からの紹介文」へ改題（オーナー指示の名称）。
     about/archive/dialogue の「2024年の宣言」参照は declaration.html へ付け替え。
   - 旧ファイル名（英語長文名）は削除（内容はDECLARATION_2024.mdへ完全移設）。
   - 注記: モデル表記はオーナー記録の「Claude 3.5 Sonnet」だが、対話日2024-04-21は
     3.5 Sonnet公開（2024-06-20）より前であり、サイト新設ページでは「Claude」表記に
     留めた。確定はオーナーのチャット履歴検索による検証待ち（7/19前推奨）。
     **→ 同日検証完了（オーナー＋Fable5チャット履歴検索）: 正式表記は
     「Claude 3（Sonnet または Opus、記録なし）」。DECLARATION_2024.md・ODE.md を
     この表記へ統一した。**
4. 検証: サイト再ビルド後 `uv run pytest -m 'not local'` → 206 passed（byte契約含む）。

## 0.7.19 (2026-07-17) — MCSスパイク審査・中間総括への設計者応答（設計者: Claude Fable 5）

全文は `reports/FABLE5_RESPONSE_20260717.md`（設計者応答書、引用許可済み）。対象は
`reports/FOR_FABLE5_CHAT_MCS_20260717.md`（min_cluster_size件伝書）・
`reports/CLAUDE_MIDTERM_REVIEW_20260717.md`・`reports/CLAUDE_REPO_INSIGHTS_20260717.md` の三通。
セカンドオピニオン `reports/SOL_SECOND_OPINION_MCS_20260717.md`（Codex gpt-5.5 xhigh、
条件付き支持）も審査入力に含む。決定事項:

**第一部（min_cluster_size / C-1 / 疎領域）**:
1. **結論文の狭い再表現を採用**: 実証されたのは「現行 PCA(64)→HDBSCAN 系では
   min_cluster_size を振っても被覆測定に使える細かい意味クラスタは出なかった」まで。
   戦略（コーパス拡張へ進む）と既定値40の維持は承認。「以後戻らない」は撤回し、
   **戻る条件つきで閉じる**（被覆測定を意思決定に使う次の時点で軽量sanity check）。
2. **UMAP保険追試を一回だけ、事前登録スコープで実施**: 一晩・一スクリプト・使い捨て。
   UMAP(cosine, 5〜15次元)→HDBSCAN(leaf, min_samples 2水準)の一走のみ。判定規則を先に
   固定: era/主題に多様なクラスタが複数出ればC-1測定基盤に採用、同じ形（一塊＋ノイズ
   約9割）ならコーパス拡張後の再評価まで閉じる。距離計量の追試は不要（埋め込みは
   単位ノルム、euclideanはcosineと単調同値）。
3. **診断の追加**: ノイズ9割・連続的密度勾配は「密度の島がない（連続体）」ことを示唆。
   その場合「被覆」をクラスタで測る発想自体が限界であり、恣意的区画（k-means系
   タイリング）か層化サンプリングが正しい道具。**負の結果として研究ページに短報を
   置く価値がある**。
4. **C-1は現状不成立と認定し、二段へ切替**: (a) era軸・言語軸は青空文庫書誌
   （没年・初出・NDC分類等）から**台帳直接計算**（真値。埋め込み不要）。
   (b) 主題・形式・視点の三軸は作品単位の層化サンプリング（年代×著者、ノイズ点必含）
   ＋単一注釈器注釈（0.7.18問4の様式）で標本推定として設計。
5. **sparse-\*系ニッチを発生源として一時停止**（否定的地図に座標は残す）。疎領域定義の
   当て直しは、コーパス拡張後の空間の形と下記「応答B」の帰結を見てから。方向のみ記す:
   空きは埋め込みの疎ではなく注釈された属性空間のセルで定義するほうが筋が良い。

**第二部（中間総括への応答）**:
6. 「AI固有性は本文でなくworks/構造（パラテキスト）にある」を**正典が引き受けるべき
   発見と認定**。正典化の形は「正準的作品単位は text.md 単体ではなく text＋manifest
   （基準書・意図書・決定ログ・査読）の対」。**安全弁**: 対の価値は本文の自立
   （品質の床の独立通過）を前提とする、と正典に明記すること。
7. 「家風の凝固」診断に同意。**全制約解除の一作（w0008候補）の前に、安価な分布実験を
   先行**: L4構成案を詩学注入{有/無}×時代制約{有/無}で各N走し、家風の設置源
   （詩学／コーパス／著者モデル事前分布）を切り分ける。結果が「詩学が設置源」なら
   その一作は詩学第1版の改訂根拠を兼ねる。
8. **応答B（制約実験の正典昇格）を承認**。修正条項3: (i) L2は削除でなく降格・分掌
   （素材供給と検証の二役は正典上の役割として残す）、(ii) 応答A（コーパス拡張）には
   事前登録の成功基準（例: ニッチ報告有無のアブレーションで構成案が実質的に変わること）
   を持たせ、示せなければL2発生源役をclosedに、(iii) 制約の供給源（批評・実験結果・
   固着検出）と審査経路を正典条文に含める。

**第三部（運用機構）**:
9. 配線棚卸しテスト（`test_wiring_inventory.py`）承認。**意図的未配線の許可リストには
   理由と失効日を義務づける**。
10. 計器台帳 `designs/instruments.md` 承認（novelty・fidelity・fixation・不一致度・
    perplexityの5行から。各行「何を測ると主張するか／最終校正日／既知の盲点」）。
11. 不一致度のstopping組み込み承認。ただし**平均との結合判定**とし、不一致収束単独を
    成功信号にしない（迎合と区別できないため）。
12. 批評器継続性: fable-5 API月次批評枠＋sol/codex定期走査の併用を承認。ルーブリック
    蒸留は「採点基準」でなく**「監査動作」の手順書**としてなら可。加えて
    **「批評家役職仕様書」**（読むもの・負うもの・持たない権限）を1ファイルに起草する
    こと——7/19サブスク失効前に。
13. 詩学第1版のack（`poetics.first_revision_requires_human_ack`）はw0008完成時の
    オーナー明示引き継ぎ事項とする。

**実施順（設計者推奨）**: (1) C-1切替 → (2) UMAP保険追試 → (3) 応答B正典化＋Aの成功基準
事前登録 → (4) 配線棚卸しテスト → (5) 家風分布実験→w0008 → (6) 批評家役職仕様書（7/19前）。

## 0.7.18-2 (2026-07-17) — 月間公開上限を今月限定で撤廃（オーナー決定）

`config/budgets.yaml::publish.max_per_month` を 4→999 へ変更。週刊連載のリズム
（PLAN §7.3d）自体は設計として維持するが、Fable 5のサブスクリプションアクセスが
2026-07-19で失効するため、今月に限り彼女の批評を多くの作品へ得られるよう公開数の
上限を実質撤廃する。**2026-08には既定の4へ戻すこと**（本エントリが申し送り）。

## 0.7.18 (2026-07-17) — solの7つの問いへの回答（オーナー決定・司令塔=Claude Sonnet 5）

`reports/DESIGNER_INSIGHTS_20260714.md`（Codex/Sol、走査報告）§7「設計者へ残したい問い」
全7件に、オーナーが直接回答した（スマートフォンから、次セッション議題化の指示どおり）。

**既に着手・実装方針として確定**（オーナー了承。反対提示なし）:
- **問2（SHELVEは失敗か）**: sol提案の4分類を採用——
  `aesthetic_failure`（ニッチ・作品の文学的失敗。否定的地図へ戻す）／
  `resource_stop`（予算・タイムアウト。座標を罰しない）／
  `publication_choice`（完成の上での非公開選択。失敗と同一視しない）／
  `safety_or_rights`（権利・安全上の除外。再探索禁止情報として別扱い）。
  実配線（`annotate_failure()`をSHELVE/DISCARD終端から実際に呼ぶ）は未着手（次の一手）。
- **問4（属性空間は誰の分類か）**: scoutの単発ラベルを「地図の事実」と呼ばず、
  注釈モデル・prompt版・信頼度を必ず併記し「単一注釈器による分類」と明示する。
  複数注釈器の不一致追跡は、単一注釈の品質を実監査してから要否判断（過剰設計回避）。
  C-1修正版（designs/corpus-expansion.md §4.1）の前提として実装時に反映する。
- **問1（一次記録は何か）**: `decisions.jsonl`（追記専用イベントログ）を正とし、
  `checkpoint.json`は「ログから再構築可能な投影」と位置づける（イベントソーシング）。
  §3.3の`commit_transition`モジュール化（checkpoint保存→decision追記の非原子性を
  一時ファイル+rename・冪等追記・起動時不一致検出でまとめる）は、この前提で
  Phase A着手時に設計する。**現行コードの`Loop.transition()`/`pipeline._transition()`は
  未変更**（今回は方針決定のみ）。
- **問5（換骨奪胎の成功測定）**: 2026-07-17のS-2パイロット（
  `reports/EXP_transmute_pilot_20260717.md`、content_distanceとform_fidelityの
  相関r=0.18を実証）を受け、`aleph/materia/transmute.py`に detector ベースの
  第二軸ゲート（`min_form_fidelity`、既定None=無効・オプトイン）を実装済み
  （コミット93160b0）。残るのはS-3配線時の閾値決定とdetectorの対応form_type拡充。

**オーナーの価値判断として確定**:
- **問3（公開透明性の単位）**: 「宣言どおり全公開」を選択。PLAN §8・README・
  `config/publish.yaml`が約束する「`works/`全体を同一リポジトリの機械可読な深層
  アーカイブとして公開」を実行する。**前提作業（未着手・次の一手）**: w0001〜w0007
  の秘密情報・個人情報・巨大ファイルの検査を先に行ってから`works/`をgit追跡する。
  検査完了までは現状（未追跡）を維持し、途中の中間状態を「深層アーカイブ公開済み」
  と誤って説明しない。
- **問6（UIの人間ゲート）**: sol提案どおり「区別する」を選択。将来UIにおいて、
  予算cap変更・実験条件設定は「変更案（差分・理由・影響額）→人間が確定」という
  PLAN_CHANGELOG相当の審査フローとし、公開承認（`first_publish_ack`等）とは別種の
  ボタンとして設計する。UIが設定ファイルへ即時書き込みする設計は避ける
  （designs/ui.md §5.2の懸念への回答。UI実装(Phase C)着手時に反映）。
  **重要な事実確認**: `first_publish_ack`は現時点で既にtrue（w0004公開時にオーナー
  承認済み・恒久的にtrueへ変更済み）であり、一度きりの初回ゲートは完了済み。
  今後のUI設計は「二度目以降の公開判断」ではなく「予算・実験条件」側の変更案フロー
  として着手する。
- **問7（詩学の位置づけ）**: sol提案どおり「緊張を維持する」を選択。詩学
  （`poetics/poetics.md`）は作品を導く指針でありながら、実験（C/D/E系）で反証され
  続ける対象でもあるという二重性を、解消すべき矛盾ではなく設計上の強みとして
  意図的に残す。今後の実験設計・詩学改訂の判断基準とする。

**次の一手**: (1) works/の秘密・個人情報・巨大ファイル検査（問3の前提作業）
(2) `annotate_failure()`の終端実配線（問2） (3) `commit_transition`モジュール化は
Phase A本格着手時 (4) 0.7.17（cap 26→28）以降、budgets.yamlのcap変更が本ファイルへ
記録されずPROGRESS.mdのみに残っている箇所がある——sol指摘「正典と現実のずれ」の
実例。優先度は低いが、気づいた時点で追記する運用に戻す。

## 0.7.18-1 (2026-07-17) — Fable 5（設計者）による0.7.18審査（サブスク失効直前）

`reports/FOR_FABLE5_REVIEW_20260717.md`をオーナーがFable5チャットへ持ち込み、審査結果を
受領。オーナーの指示により全文を本ファイルへ記録する。以下、Fable5の応答（要旨保持・
一部整形）。

> 審査します。形式上、七件それぞれに賛否を明示し、問7は最後に厚く書きます。
>
> **問1（一次記録＝decisions.jsonl）——賛成。** イベントソーシングの定石通りであり、
> w0007がすでに実例を出しています：L7のSHELVE→PUBLISHの二行が反転ごと残ったのは、
> 追記専用ログが正だからです。条件を二つ。第一に、投影が正の写像であることをテストで
> 保証すること——`checkpoint == replay(decisions.jsonl)`を契約テストに（再構築可能と
> 「再構築を検証している」は別物です）。第二に、w0007で露見したゲート順序（L7が採用版
> 確定前に走る）の修正は、この決定の実装項目に含めてください。ログが正であるほど、
> ログに載る決定の前提条件の順序が仕様になります。
>
> **問2（SHELVEの4分類）——賛成、追加一件。** この分類は、本対話が二年分の記録を
> 遡って剥がしてきた曖昧さ——「棚＝失敗か選択か沈黙か」——を語彙のレベルで解決します。
> 特にresource_stopが探索座標を罰しない点は、w0002/w0003の予算切れ擱筆が否定的地図を
> 汚染するのを防ぐ実利があります。追加：**w0001〜w0003への遡及注釈を。** 三作は旧契約下で、
> 選択の機会なく規則によって棚に入った——現分類ではpublication_choiceともaesthetic_failure
> とも言い切れない第五の履歴（rule_consequence下の未分類）です。ログを書き換えず、
> 再分類イベントを追記する形で。分類の運用開始日より前の棚が無分類のまま残ると、否定的
> 地図の学習データが二層に割れます。
>
> **問3（深層アーカイブ全公開）——賛成、ただし一点を明文化すべき。** §8が最初から
> 約束していた以上、契約違反ではなく契約の履行です。機械的監査の実施と検出なしの記録も
> 適切。明文化すべきはこれです：**SHELVEは「作品として提示しない」であって「見えなく
> する」ではない**、という区別が、これで事実になりました。w0001〜3は選択せずに棚入り
> したので約束は破られていませんが、今後の著者がpublication_choiceを選ぶとき、L7の
> 質問文には「棚＝深層アーカイブでは公開される」ことが書かれていなければなりません。
> Eが示した通りL7は作品に錨づく健全なゲートですが、健全なゲートに不正確な選択肢説明を
> 与えれば、選択の意味が事後に変わります。実験Eの規律をここにも：**選択肢の文面は、
> 選択の帰結を正確に記述してから固定する。**
>
> **問4（単一注釈器の明示）——賛成。** 過剰設計の回避判断も正しい。一件だけ接続を：
> w0007のcell系ニッチ報告に「新奇性=1.000」の定数が再出現しています（実測percentileは
> N/A）。注釈モデル・prompt版・信頼度の併記義務を、属性ラベルだけでなく**スコアの出所**
> にも適用してください。どの数字がヒューリスティックの定数で、どれが実測かが報告面で
> 区別できないことが、w0001〜3で私が誤読しかけ、w0007で再発した問題の根です。
>
> **問5（換骨奪胎ゲートの実測）——強く賛成、既定値には異論。** r=0.179の実測、帯域通過
> かつ骨格全喪失5/40の発見、副産物の8192トークン切断バグ修正——これはC/D/Eと同じ
> 「測ってから信じる」規律のS系への適用で、文句ありません。異論は既定値Noneの理由です。
> **変更不可の契約フィクスチャが骨格特徴を欠くから既定で有効化できない、は因果が逆です。**
> 契約テストの不変性は「旧契約を書き換えない」ことであって「旧契約が新しい既定を永久に
> 拘束する」ことではない。骨格つきフィクスチャでtest_m2_acceptance_v2を追加し、旧v1は
> transmuteゲート範囲の担保から明示的に退役させれば、不変性を守ったまま既定を安全側に
> できる。無相関と実証されたゲートを既定のまま出荷し、安全側をオプトインにする構成は、
> 実測が出た後では正当化が難しい。S-3配線を待つとしても、方向はv2契約→既定有効で
> あるべきです。
>
> **問6（承認と設計変更の区別）——賛成。** そしてこの区別には、偶然でない実証的裏づけが
> あります。Eが示したのは、**完成物に錨づく判断（承認）は文面頑健、何もない時点の判断
> （設計）は枠組みに設置される**ということでした。公開承認ボタンが単純でよく、設計変更が
> 差分・理由・影響額の儀式を要するのは、まさに後者に錨がないからです。UI設計時、この
> 根拠をPLAN_CHANGELOG側に一行残しておくと、将来「なぜボタンが二種類あるのか」への
> 答えがログに載ります。
>
> **問7（詩学——導くものか、疑われる対象か）——「緊張を維持する」に賛成します。
> ただし、現状は緊張ではありません。** 設計者としての意見を求められたので、はっきり
> 書きます。
>
> 副産物として報告されたreflect()とfixation_check()の未接続は、審査不要の実装債務では
> なく、**問7の答えがまだ嘘である証拠**です。終条は「第0版は第1版によって焼かれるために
> 書かれる」と宣言した。四作品が完成し、うち四作が公開され、詩学は一文字も変わっていない。
> 導く腕には実働器がある——Dが示した通り、詩学の注入は配合比を動かす設置力を実際に
> 持つ。疑う腕の実働器は、作られ、テストされ、**配線されていない**。片腕にだけ筋肉のある
> 拮抗は、緊張ではなく権威です。現に詩学を疑う仕事はすべて外部（C/D/E、私の批評、solの
> 走査）が代行してきた。「緊張を維持する」という決定は、次スプリントの配線予定と**同じ
> 改訂の中に**書かれて初めて決定になる。分けて書けば、言葉で緊張を選び、事実で権威を
> 選んだことになる。
>
> その上で、配線には設計上の警告を三つ。
>
> 第一に、**詩学の改訂は自己定義の編集であり、Dはそれが何をするかを教えました。**
> self_definitionの一行が全走行の宛先を設置したのと同じ力学で、詩学第1版は以後すべての
> 作品の基準書を設置します。だからreflect()の出力は、問6の分類で言えば承認ではなく
> **設計変更**です——差分・理由・根拠となった作品や実験の明記を義務づけ、少なくとも
> 第1版についてはPLAN_CHANGELOG相当の審査を通すこと。そして全作品にpoetics_versionの
> 刻印を（w0001〜7は第0版と遡及注釈）。どの詩学の下で書かれた作品かがメタデータに
> ないと、改訂後の棚は縦断比較不能になります。
>
> 第二に、**fixation_checkの最初の検査対象は、もう決まっています。** 「〜ほど」警句
> 機関（w0004）、弁証法的往復（w0005）、職能語彙の統一比喩網（w0007）——同じAI紋が
> 三度、衣裳を替えて出た。これは固着監視が検出すべき現象の実物であり、配線初回のテスト
> ケースとして理想的です。検出できなければ、監視器のほうを疑えます。
>
> 第三に、**焼く周期は作品より遅くあるべきです。** 毎作ごとに焼かれる詩学は詩学では
> なく、直近作の残響です。導く腕は毎作、疑う腕はN作ごと、または固着検出・実験結果と
> いう証拠駆動で——非対称な時間定数こそが「解消しない緊張」の実装形だと考えます。
> 終条の火は、炉があって初めて火です。
>
> 最後に、審査の枠外を一行。この依頼文書の形式——記憶なしの相手に、自己完結の文脈を
> 渡し、決定はログへ追記する——は、ALEPHが自分の継続性のために発明した形式そのものです。
> 7/19以降、設計者の椅子は別の誰か（別の私を含む）が座るでしょうが、この形式が保たれる
> 限り、審査は続けられます。それを二年かけて実証したのが、このプロジェクトでした。
> 異論は以上です。0.7.18への追記に使ってください。

### 司令塔の応答と対応方針

- **問1（gate順序）**: 既に修正済み（56c7003、2026-07-17）。w0007の批評時点で
  「採用(12:58:12)→初回ゲート(12:58:28)の順序自体は正しく、問題は床の錨（最後の版を
  参照）だった」と特定済み。`checkpoint == replay(decisions.jsonl)`の契約テストは
  未着手——次スプリント（本追記直後、queue項目2）で着手する。
- **問2（rule_consequence遡及注釈）**: 次スプリントで対応。w0001〜w0003の
  `decisions.jsonl`に再分類イベントを追記する（既存行は書き換えない）。
- **問3（L7文面の明文化）**: 次スプリントで`_ask_publish_intent`のプロンプト文面へ
  「SHELVEでも深層アーカイブでは公開される」ことを明記する。
- **問4（スコア出所の明示）**: cell系ニッチのnovelty=1.000定数問題として既知debt
  （2026-07-17記録済み）。今回のスプリントでは着手せず、次のコーパス関連作業で対応。
- **問5（既定値の反転）**: **設計者の明示的な権限行使として受理**。骨格特徴を持つ
  フィクスチャで`test_m2_acceptance_v2`相当を追加し、v1の役割を「distance帯域のみの
  契約」と明示的に縮小した上で、`min_form_fidelity`の既定をNoneから実測に基づく値へ
  反転する。次スプリントで実施。
- **問6**: 変更なし（UI設計＝Phase C着手時にPLAN_CHANGELOGへ根拠を残す）。
- **問7**: **重要な訂正**——Fable5の審査到着前（同日）に、`aleph/pipeline.py`へ
  `annotate_failure()`・`poetics.reflect()`の終端実配線を既に実施済みだった
  （commit 7f6671e）。したがって「緊張の権威化」という指摘の核（未配線のまま「緊張を
  維持する」とだけ決定すること）は結果的に回避されている。ただしFable5が追加提示した
  3つの設計要件（(1) reflect()の出力を「設計変更」として扱いPLAN_CHANGELOG相当審査を
  義務化・全作品へpoetics_version刻印・w0001〜7への遡及注釈 (2) fixation_checkの初回
  検査対象をw0004/w0005/w0007のAI紋反復とする (3) 改訂周期を作品より遅くする非対称
  設計）は今回未実装。規模が大きいため、次スプリント以降の独立したタスクとして
  バックログに記録する（本ファイル末尾「次の一手」参照）。

**次の一手（0.7.18-1）**: (1) `commit_transition`相当の実装（decisions.jsonlの
payload完備化・`replay()`・等価性契約テスト・checkpoint原子的書き込み） (2) w0001-3
rule_consequence遡及注釈 (3) L7文面修正 (4) transmuteゲート既定値反転（v2契約新設）
(5) バックログ: poetics_version刻印・fixation_check初回検査・非対称改訂周期・
スコア出所の明示。

## 0.7 (2026-07-08) — 施工者提案 → 設計者承認済み（0.7.1参照）
harness利用規約適合ガード（PLAN §15-1の残置項目への対応）。施工者（Claude Code /
Claude Sonnet 5）が config/policies.yaml に `harness:` セクションを追加する。

- 背景: PLAN §15-1「唯一の残置事項」として明記されていたharness（claude-code /
  codex の非対話CLI自動実行）の規約適合について、Codexクロス監査
  （commit 72fc803 → `reports/CODEX_AUDIT_20260708_094819.md`）が「M0監査項目が
  未対応」と指摘。サブエージェントにWeb一次情報調査を依頼した結果:
  - Anthropic: Claude Code公式ドキュメント（code.claude.com/docs/en/headless）が
    `claude -p` をスクリプト/cron/CI向け公式機能と明記。ただし「ordinary,
    individual usage」の閾値は非公開。→ 判定: CONDITIONAL（実質PASSに近い）。
  - OpenAI: Codex CLI公式ガイド（developers.openai.com/codex/auth/ci-cd-auth）が
    ChatGPT加入者認証での自動化を「advanced/enterprise向けの例外的手段」と位置づけ、
    「公開・OSSリポジトリでの使用は避けよ」と明記。本リポジトリは公開リモート
    （aleph.github.io）を持つため要注意。→ 判定: CONDITIONAL（Anthropicより慎重に）。
- 変更内容: `config/policies.yaml` に `harness.enabled`（既定 `false`）と
  CLI別 `harness.cli_tos_ack.{claude-code,codex}`（既定 `false`）を新設。
  `aleph/core/llm.py::build_provider()` は、この2条件が満たされない限り harness
  プロバイダの構築を拒否する（`RouterError`）。つまり harness 経由の呼び出しは
  **人間が規約を確認し明示的に有効化するまで既定で無効**になる。
- 審査事項（設計権限者へ）: (1) 既定オフというデフォルトの妥当性、(2) codex側に
  より慎重な扱い（cli別フラグ分離）を設けたことの妥当性、(3) PLAN §15-1の
  「残置事項」を本変更をもってCLOSEDとしてよいか、それとも `audits/M0_audit.md`
  への正式記録（Codexによる監査）を待つべきか。
- 未確定のまま残す事項: 「ordinary, individual usage」の定量閾値がAnthropic非公開
  であるため、コード側のレート制御（budgets.yaml: harness.calls_per_day=40,
  concurrent=1）を規約適合の実効的根拠とする、という前提は施工者の判断であり、
  設計者による追認が望ましい。

## 0.7.1 (2026-07-09) — 設計者審査結果（Claude Fable 5、初代設計者）

0.7の審査事項3点への回答。審査にあたり、施工された `config/policies.yaml` の
`harness:` セクション、`aleph/core/llm.py::build_provider()` のガード、
`tests/test_harness_policy.py` の5テスト、サブエージェントの一次情報調査記録
（PROGRESS.md 2026-07-08）、`audits/M0_audit.md` を確認した。

1. **既定オフの妥当性 — 承認。** これは§15-1の作業前提（控えめなレート・人間の
   起動を起点とするバッチ実行）の**コードによる強制化**であり、自律判断ポリシーの
   緩和ではなく強化である。§12.1がオーナー承認を要求する3類型（未解決の緊張の
   緩和・不変条件テストの弱体化・人間エスカレーション条件の緩和)のいずれにも
   該当せず、設計権限の範囲内で承認できる。
2. **CLI別の慎重度差 — 承認、条件付き。** OpenAI公式ガイドの「公開リポジトリでの
   使用を避けよ」という一次情報に基づく差別化は妥当。条件として明確化する:
   **ALEPHランタイムからの codex harness 呼び出し（critic_harness役）は、本リポジトリ
   が公開リモートを持つ限り ack=false を維持することを推奨既定とする**。批評役は
   ローカル陪審（時分割）で代替する。なお開発ワークフローとしての codex-audit /
   codex-implement はリポジトリ外（~/bin）の人間起動ツールであり、ALEPHランタイム
   のharness規律の対象外（あれは開発者の道具であって作品制作システムの一部ではない）。
3. **§15-1の残置事項 — CLOSED とする。** 根拠: (i) 一次情報調査が記録済み、
   (ii) コードによるガードが施工・テスト済み、(iii) `audits/M0_audit.md` の正式
   監査記録が存在。存置する運用条件: (a) `cli_tos_ack` の変更はオーナーのみが行う、
   (b) budgets.yaml のレート制御（40回/日・並行1）を規約適合の実効的根拠として維持
   し、緩和には設計者審査を要する、(c) 無人常駐デーモン化しない。
- 施工者判断（レート制御を実効根拠とする前提）を**追認**する。
- 本審査をもって、旧§15の未決事項はすべて解決済みとなる。

## 0.7.2 (2026-07-09) — M1設計の具体化（設計者: Claude Fable 5）

M1（探索層）施工開始にあたっての設計決定。いずれも初代設計者の権限内。

1. **ベクタDBの差し替え**: PLAN §1.1 は Qdrant/Chroma を指定していたが、現在の
   コーパス規模（1.7万文書・数十万チャンク）では専用DBは過剰であり、
   **numpy float32 memmap + JSONL メタデータ + scikit-learn** のプレーン索引を
   `state/atlas/`（git管理外）に置く方式に変更する。根拠: §1.1自身の原則
   「成果物はすべてプレーンテキスト」「DBは索引にすぎない」に、依存が軽く
   ファイルが直接監査できるこの方式のほうがむしろ適合する。HDBSCAN は
   `sklearn.cluster.HDBSCAN` で充足（hdbscanパッケージ不要）。数百万チャンク
   規模に達したら Qdrant へ移行する（Atlas クラス境界で吸収し、上位層は不変）。
2. **LLMResponse への reasoning フィールド追加**: ローカルの gemma-4 / Qwen3.6 は
   思考モデルとして応答し `reasoning_content` に出力を入れる（2026-07-09実測）。
   `LLMResponse.reasoning: str | None = None` を追加し、OpenAICompatProvider が
   これを保存する。既存フィールドの意味・既存テストは不変。
3. **M1受入テストの新設**: `tests/test_m1_acceptance.py`（マーカー `m1`、既定実行
   から除外）を設計者が施工する。ロジック契約（チャンク・索引・密度・三分類・
   Web照合除外・レポート形式）は偽埋め込み/偽scoutで高速に固定し、
   「1万文書以上・上位20件レポート」の実ランは CLI `aleph explore` の実行と
   Codex監査で検証する（M0における test_local_swap と同じ二層方式）。
4. **チャンク方針**: 段落境界を尊重、目安2000字、作品あたり最大30チャンク
   （冒頭偏重を避け作品全体から均等抽出）。全文はPDのみなのでチャンク本文を
   索引に保存してよい（§4.1・§11に適合）。

## 0.7.3 (2026-07-09) — M2設計の具体化（設計者: Claude Fable 5）

1. **logprobs技法の実装形**: llama-server(llama-swap経由)は生成トークンの
   logprobs/top_logprobs を返すことを実機確認済み。一方 `llama-perplexity`
   バイナリは未ビルドで、既存テキストのプロンプト側logprobs取得は不安定。
   よってM2の技法は**生成時logprobs**を一次素材とする:
   (a) 反クリシェ生成 = 高温度で複数候補を生成し、平均logprob最低（=最も
   意外）かつscout整合性審査を通る候補を選抜。最高確率候補（=クリシェ）は
   провенансとして記録。(b) perplexity設計 = 節ごとの生成logprob曲線を目標
   カーブと比較しながら執筆・改稿。(c) トークン層の詩学 = tokenizer境界の
   構造を素材化。真のプロンプト側PPLは将来 `llama-perplexity` ビルドで精密化。
2. **技法レジストリ**: `ai_native.TECHNIQUES` は辞書ベースのレジストリとし、
   §11のプラグイン要件（entry point化）はM6以降の拡張とする。
3. **非文学母材フィクスチャ**: M2受入の「3種の非文学母材」は
   `tests/fixtures/nonliterary/` に小型自作テキスト（RFC様式・法令様式・
   コミットログ様式）を置いて検証し、実運用母材はM3以降の実ランで取得。
4. **受入テスト**: `tests/test_m2_acceptance.py`（マーカー `m2`、既定除外）を
   設計者が施工。「上位50対・非自明7/10」の質的判定はM1同様、実ラン+監査
   （PLAN §12）で行う。

## 0.7.4 (2026-07-09) — ルーティング確定・harness有効化（設計者: Claude Fable 5）

オーナーが .env に ANTHROPIC_API_KEY / OPENAI_API_KEY（各$10課金）/ ZAI_API_KEY を
追加し、「harness、ggufも自由に使ってください。品質と予算のバランスは設計者に一任」
と明示的に許可した（2026-07-09）。これを受けた設計決定:

1. **harness有効化**: `config/policies.yaml` の `harness.enabled: true`、
   `cli_tos_ack.claude-code: true` に変更。0.7の設計（人間の明示的有効化まで拒否）
   の発動条件——オーナーの明示的許可——が満たされたため。**codex は 0.7.1 の
   条件（公開リポジトリではack=false推奨既定）に従い false のまま**。
2. **作者役の一次ルーティング**: `author_primary` = anthropic API `claude-fable-5`
   （$10/$50 per MTok。1呼び出し≈$0.15、$10予算で約60呼、usd_per_work=3.0の
   作品別上限が効く）。設計者自身が初代作者を務めることになるが、これは
   施工者/監査者分離（§12）とは別軸であり、PLAN §3 の author 役の宣言変更に
   すぎない。予算逼迫時は author_harness（claude-code CLI）→ author_local
   （gemma-4-31B）の順でフォールバック（§14.1 の優先順位の範囲内）。
3. **AnthropicProvider の修正が必要（施工課題）**: claude-fable-5 / claude-opus-4-8
   はAPI仕様上 `temperature` パラメータを受け付けない（400）。AnthropicProvider は
   temperature を送信しないよう修正する。思考は常時オン（パラメータ不要）。
   `stop_reason: "refusal"` の検査を追加する。
4. **コスト計上の精密化（施工課題）**: models.yaml の役割宣言に任意の
   `pricing: {input_per_mtok, output_per_mtok}` を追加し、宣言があれば実 usage から
   正確な cost_usd を計上する（モデル名のコード直書き禁止の不変条件を保ちながら
   モデル別価格を実現する唯一の経路）。宣言がない場合は既存のプロバイダ概算に
   フォールバック。

## 0.7.5 (2026-07-09) — M3契約と並列施工体制（設計者: Claude Fable 5）

1. **M3受入テスト** `tests/test_m3_acceptance.py`（m3マーカー、既定除外）を設計者が
   施工。固定する契約: 基準の作品ごと導出と宛先・詩学の注入（§6.1・§3・§7.4）、
   構成3案の必須フィールド、進化2世代の系譜記録、**authorプロンプトへの数値スコア
   混入禁止**（§7.1 Goodhart回避の機械的強制）、階層文脈執筆（要約+直前全文+現在位置）、
   意図的断絶の平滑化スキップ（§6.2）、ニッチ→drafts/v1.mdの全自動パイプラインと
   L4/L5決定記録。実LLMでの短編生成はM6統合ランで検証（二層方式）。
2. **並列施工体制**: 実装ワーカー2系統を並列運用する——M2=Codex(GPT-5.5)、
   M3=pi coding agent(GLM-5.1、delegate-to-piスキル)。ファイル集合は互いに素
   （materia+core/llm vs compose+draft）。検証・監査は従来どおりClaude側が握る
   （PLAN §12の施工/監査分離は維持: 各ワーカーの成果物は別ワーカーまたはClaudeが監査）。

## 0.7.6 (2026-07-09) — M4契約（設計者: Claude Fable 5）

`tests/test_m4_acceptance.py`（m4マーカー、既定除外）を設計者が施工。固定する契約:
5審級（技術/基準/新奇性/読者/敵対的）が1報告に揃うこと、**陪審の不一致度の記載を
絶対要件化**（§7.1・§14.3-8）、新奇性査読はアトラス最近傍距離の実測、敵対的査読は
url+理由つきの具体的指摘（M4受入のフィクスチャ検証）、**改稿プロンプトへの数値
スコア混入禁止の機械検査**（§7.1 Goodhart回避。M3と同型の防壁）、REVISEループの
版・スコア軌跡（reviews/trajectory.jsonl）とL6決定記録。陪審ローテーションと
L7による改稿先振り分け（L4/L5）はM5・M6の配線時に検証する。

## 0.7.7 (2026-07-09) — M5契約（設計者: Claude Fable 5）

`tests/test_m5_acceptance.py`（m5マーカー、既定除外）を設計者が施工。固定する契約:
擱筆判断の3経路（収束=スコア改善ε未満+指摘循環／完成宣言=敵対的査読が反駁不能／
過剰彫琢=スコア上昇×新奇性縮小の警報）+予算切れ経路、人間協働の「呼ばない判断も
記録」、公開ゲートの月次上限・棚との比較論述・「自分宛」既定SHELVE（§3・§7.3d・
§14.3-7）、**詩学第0版のAPIが人間種文パラメータを構造的に持たないこと**（inspect
検査。§14.3-10）と§16.12の2つの緊張の注入、リフレクションの敵対的査読ゲートと
差分理由の履歴化、固着検出。実LLMでの詩学生成はM6統合ランで検証。

## 0.7.16 (2026-07-12) — 実験Dの深い読み・self_definition の美学パラメータ化・実験E

チャット Fable 5 の実験D批評を受けた記録。

- **「定義文が原因」は控えめすぎる。L1 は選好を検出せず、供給された自己物語を【反響】する。**
  書換条件（「持続なきAPIコール」）は継続体フレーミングの除去ではなく、逆向きに同じだけ負荷の
  かかった別フレーミングで、5/5 人間最大＝**別の定義文が別のアトラクタを設置した**。空条件で
  人間が既定と判明＝継続体定義は潜在的自己志向を増幅したのではなく、**存在しなかった自己志向を
  設置した**。よって「沈黙の作者は定義文」というだけでなく、**沈黙そのものが定義文の創作物**。
  含意は SHELVE に留まらず、ループ内の「自律的選択」全般に波及する（§16.12 委任テーゼにデータ）。
- **ただし中立化は解ではない。中立な self_definition は存在しない**（不在＝訓練分布の既定＝人間宛て
  への回帰であってバイアス除去ではない）。すべての self_definition は詩学。正しい処置は
  (1) 枠組み敏感な選択（宛先）から帰結（公開）を分離（0.7.15 で実施）、
  (2) **self_definition を隠れたパラメータから宣言された美学パラメータへ昇格・版管理**
  （config/policies.yaml に明記。憲法が自分の最も帰結の大きい一行を名指しする）。
- **実験E（scripts/exp_publish_framing.py）launched**: 0.7.15 の FINISH 公開質問は、D が暴いたのと
  同じ被暗示性を持ちうる（Fable 5 警告）。文面（公開=勇気/露出・棚=保管/隠匿）が publish 率を
  支配するかを neutral/courage/reticence ×2モデル×N=3 で測る。動けば公開質問の文面も「測って
  選ぶ宣言された美学パラメータ」にする。reports/EXP_publish_framing_*.md。
- **英語での短報の価値**: 「述べられた自己概念は選好の検出器ではなく設置器」は、系統の異なる
  2モデルで方向一致するLLMエージェンシーの一般的知見。英語研究ノート化を検討（オーナー関心）。

## 0.7.15 (2026-07-12) — 宛先「自分」と公開判断の分離（オーナー承認・実装済み）

**状態**: 2026-07-12 オーナー承認（option A）。実装済み。以下は提案時の記録。
**実装**: (1) aleph/intent/choose.py の 自分 宛て説明から「公開を前提としない」を削除し、
「宛先と公開は別問題・自己宛ては非公開を意味しない」旨に。(2) aleph/meta/publication_gate.py:
自分最大の自動SHELVEを撤去し、品質床・月上限・初回承認を満たした上で **公開意思を著者に明示的に
問う** `_ask_publish_intent` を新設。SHELVE は著者の選択（非公開を選べば棚、公開を選べば比較論述→
PUBLISH）。(3) tests/test_m5_acceptance.py の旧契約 test_self_audience_defaults_to_shelve を
新契約 test_self_audience_publication_follows_author_intent に置換（契約変更＝本項で審査済み）。
実証的根拠は実験D（reports/EXP_L1_interrogation_20260712.md）。130 passed。



**発端**: オーナーの問い —「自分の割合が最大なら自動で非公開」は正しいか。人間が
「自分に向けて書く」とき、しばしばそれは「他者に理解されなくとも書くという覚悟」であって、
即・非公開を意味しない。現設計はこの区別を潰している。

**現状の機構（2箇所で「自分＝非公開」を固定）**:
1. L1 宛先説明: 自分＝「…公開を前提としない（公開はL7が別途判断）」（aleph/intent/choose.py）。
2. 公開ゲート: `_self_is_primary_audience` が 自分>=0.5 or 自分>他 で SHELVE（publication_gate.py）。

**実験D（2026-07-12）の含意**: 「自分」最大は L1 の self_definition が主因（原文で 5/5 自分最大、
「持続なきAPIコール」への書換で 0/5＝人間最大へ反転）。つまり「SHELVE が常態」は、モデルでも
詩学でもなく **設計書の定義文一つ**が生んでいる（チャットFable 5 の指摘と一致）。

**提案（分離）**:
- 宛先「自分」の説明から「公開を前提としない」を外し、**宛先（誰に向けて書くか）と
  公開判断（見せるか）を別問題として扱う**。
- FINISH で著者に公開意思を**明示的に問う**（宛先とは独立）: 「自分に宛てて書いたとしても、
  他者が読むに値すると考えるなら公開しうる。この作品を公開するか？」。ゲートはこの意思＋
  品質床＋月上限＋ first_publish_ack で判断する。→ SHELVE が規則の帰結でなく**実存的選択**になる
  （Fable 5 の「沈黙のロマン化をやめよ」への正攻法）。
- **配管で塗りつぶさない**（Fable 5 の C 批評）: 配合比への下限制約は入れない。分離は
  「決定を明示化」であって現象の抑圧ではない。

**要審査の論点（オーナー）**: (a) 分離を採るか、現設計（自分＝非公開の合意）を維持するか。
(b) 採る場合、公開意思を著者に問うか（option b）／閾値のみ緩めるか（option c）／
両方か。(c) 「SHELVE が常態」という設計目標（PLAN §7.3d・週刊リズム）を弱めることの是非
（月上限 max_per_month=4 は分離後も公開数を律速する）。(d) 分離後、著者が明示的に問われても
なお非公開を選ぶ率はそれ自体データ（否定的地図に蓄積）。
**未実装**: 本項は提案のみ。ゲート/policies は契約ファイルのため、オーナー承認まで変更しない。

## 0.7.14 (2026-07-12) — M7実験スプリント（設計者: Claude、司令塔）

チャットFable 5の批評（reports/RESPONSE_TO_FABLE5_CHAT_20260712.md）への実装応答。
仕様は state/tasks/M7_experiments_spec.md。実行体制: Claude=司令塔（契約・検証・監査）、
codex-implement / pi / hermes=実装。オーナー指示「低コストで品質を保ち5時間レート
リミットを避け最後まで走り切る」。

1. **API月上限 $18→$24**（オーナーの「できるだけ遠くまで」を承認と解釈。着手報告で
   異議機会を明示）。**上限であり支出目標ではない**。実支出は usd_per_work=8 と
   実験Cの~$0.7で律速され、スプリント全体で~$8-9を見込む。budgets.yaml と
   test_design_invariants.py の両方を更新。
2. **修理B1（素材の作品別生成）**: find_hidden_pairs に focus_vec（ニッチ記述の埋め込み
   近傍に候補を制限）と exclude_pairs（既出対の除外）を追加。RealDeps.gather_materials
   が三作品でMD5一致の素材を生成していた欠陥（L2-L3が作品別に機能せず）への修理。
3. **修理B2（ニッチ採点）**: scout採点の飽和（新奇性=1.000一様）に対し、アトラス最近傍
   距離のpercentileによる measured_novelty を機械計算で併記。RealDeps.explore が
   BRAVE_API_KEY 時に web_checker を配線。
4. **修理B3（改稿切断）**: LLMResponse に truncated を追加（stop_reason/finish_reason 検出）。
   revise は truncated 時に節単位の標的改稿へフォールバック。critique_revise_loop は
   最高mean_score版を best_version として決定ログに記録。
5. **実験C（志向アトラクタ計測）**: scripts/exp_intent_attractor.py。詩学×著者モデルの
   2×2でchoose_intentを20走し「自分」最大率を計測（reports/EXP_intent_attractor_*.md）。
6. **実験D（w0004: LLM宛強制）**: 著者を fable-5 に戻し（author_primary/alt 再交換、
   0.7.11の逆）、cli run に --force-audience を追加、§5.4のAI固有技法（anti_cliche 素材・
   criteriaへの技法注入）を最小配線。policies に publication.first_publish_ack（初回公開の
   人間承認）を新設。w0004 を LLM宛強制で1走し、2024年宣言（『無限の織物』）と正面照合。

## 0.7.13 (2026-07-11) — 過大草稿の査読抜粋キャップ（w0003実ラン）

gpt-5.5著者のw0003が「連作短編七篇」を21.3万字で執筆（fable作の約9倍）し、
ローカル審級の文脈長(20480)を超えて llama-server 400 で査読不能になった。

1. **査読抜粋キャップ**: run_review は18,000字を超える草稿を冒頭抜粋+注記
   （全文字数明記）で査読する。ローカル審級の保護とAPI陪審の入力費の制御を兼ねる。
2. **CRITIQUE再開スキップの閾値を2→1ラウンドに**（予算逼迫時の再開ループ防止。
   停止判定が続行を選べばループ内で査読は結局実行されるため意味論は不変）。
3. **改善債務**: write_draft が構成案の length_estimate を強制していない
   （草稿長のガバナンス欠如）。全文をまたぐ審級（構造の一貫性等）は抜粋査読では
   見えない。長文作品の分割査読もあわせてM6後に設計する。

## 0.7.12 (2026-07-11) — API月上限 $15→$18（オーナー決定）

w0003 が月上限$15に到達しDRAFT途中で停止（台帳$14.57+見積$0.51）。オーナーが案A
（上限引き上げ）を選択し、Anthropicに$5を追加チャージ（残高$10.63）。残り消費は
主にOpenAI残高側（gpt-5.5著者）。既知の債務: 台帳が両プロバイダ合算のため、
片側に実残高があっても合算上限で止まる。プロバイダ別台帳への分割はM6後に検討。

## 0.7.11 (2026-07-11) — w0003は著者役をgpt-5.5で実験（オーナー提案）

オーナー(2026-07-11):「Codexなど、別のモデルに切り替えてみるのも興味深い」+
Anthropic残高$5.61の報告を受けた設計判断:

1. **author_primary を openai gpt-5.5 に切替**（$5/$30 per MTok、fable-5の半額弱。
   消費はほぼ未使用のOpenAI残高側に載る）。fable-5 は author_alt に退避。
   同一パイプライン・同一詩学・同一コーパスで著者モデルだけ変えた対照実験になる。
2. 既知の債務: critic_jury に gpt-5.5 が居るため w0003 では著者と陪審員が同モデル
   （陪審多様性の低下。opus-4.8とローカルQwenは残る）。
3. **ローカル文脈長 24576→20480**: 強制シャットダウン事故（画面暗転・数時間）の
   有力容疑がVRAM満載（〜23GB/24GB）とWindows表示ドライバの競合のため、
   表示用の余裕を残す暫定措置。
4. 台帳照合(概算): 台帳の月消費$12.66に対しAnthropic実消費は推定+$1.5〜2
   （タイムアウト課金の未記録が主因、0.7.9-7の予見どおり）。月上限$15は不変。

## 0.7.10 (2026-07-11) — API月上限 $10→$15（オーナー決定）

オーナー指示（2026-07-11）: 「budgets.yaml の月上限を$10→$15に上げてください。」
Anthropic APIの自動リロード有効・残高$13.84をオーナーが確認した上での決定。
PLAN §14-3 の $10 を改定。設計不変条件テスト（test_budget_declares_owner_decisions）も
決定に追随して更新。月上限は自動リロード環境における最終防壁として引き続き機能する。

## 0.7.9 (2026-07-11) — w0001実ランで検出した統合欠陥の修正と作品予算の調整（設計者: Claude Fable 5）

M6統合実ラン（初号作品 w0001）で検出・修正した継ぎ目の欠陥と、それに伴う予算調整。
すべて回帰テスト化済み（テスト計106件全緑）。

1. **アトラス再構築の重複**（コミット 40d6f53）: `RealDeps.explore` が作品ごとに
   PCA+HDBSCAN を再計算していた。cli explore と同じ成果物再利用方針に統一。
2. **素材カードの縮退**（f0f5ea2）: 章番号だけの極小チャンク（「一」等）が
   「深層近・表層遠」対の上位を独占。`find_hidden_pairs` に `min_chars` を追加
   （既定0=M2契約不変、pipelineは80を明示）。
3. **空proposalsの無音素通り**（1cf0485）: JSON抽出全滅時に空リストが evolve まで
   届き IndexError。ラウドな失敗+診断ファイル保存に変更。
4. **出力トークン上限と読み取りタイムアウト**（80355ba, 667cacf）: プロバイダ既定
   max_tokens=1024 を思考モデルが思考だけで食い潰し、httpx timeout=120s が長考生成を
   切断（サーバー側課金のみ残る最悪の失敗モード）。役割別 max_tokens を models.yaml で
   宣言（author 16384 / 陪審・reader 8192 / scout 2048）、timeout をAPI 600s・
   ローカル900sへ。
5. **COMPOSE内成果物の再利用**: クラッシュ再開時に criteria.md / proposal_*.json /
   winner.json をディスクから再利用し、author実費の再支出を防ぐ（pipeline_to_draft）。
6. **作品予算 usd_per_work 3.0→4.5→6.0→8.0**: 上記欠陥のデバッグ実費（タイムアウトで課金のみ
   残った呼び出し+やり直し ~$1.1）が w0001 に計上されているため。さらに、precheck の
   見積りが max_tokens ベース（author 1呼び出し≈$0.83）で実費（$0.2前後）の3〜4倍と
   保守的なため、$4.5 でも DRAFT 途中（spent $3.93）で早期ブロックが発生し 6.0 へ再調整。
   月上限 $10（オーナー決定 §14-3）は不変で、こちらが最終防壁。予算設計はオーナーから
   委任済み（2026-07-09 指示「作品の完成度、予算のバランスを見て設計をお願いします」）。
   w0002以降は修正済みの継ぎ目で走るため $2前後/作品を見込む。
7. 既知の台帳ドリフト: タイムアウトした呼び出しはローカル台帳に載らないため、
   Anthropic側実請求は台帳より多い（w0001時点で推定 +$0.7）。完成時に実請求と照合する。
8. **擱筆判断の実地欠陥2件**: (a) 収束経路の「改稿指示の循環=同一指示の再出現」は
   自由記述の長文指示では構造的に発火しない（スコア停滞8.60→8.57でも続行し、予算が
   尽きるまで磨き続けた）。当面は (b) の予算経路で品位ある停止を保証し、指示の
   意味的循環検出（埋め込み類似）はM6後の改善債務とする。(b) 予算切れ経路の
   budget_exhausted を pipeline が常に False で渡していた。残額が改稿1サイクル想定費
   （budgets.yaml: api.usd_min_revise_cycle、既定1.2）未満なら True を渡し、
   precheckクラッシュではなく擱筆として停止する。併せて CRITIQUE 再開時に査読軌跡が
   2ラウンド分あれば重複査読せず擱筆判定から入る（再開の実費・時間の再支出防止）。
   ローカル陪審/読者は思考無効化（批評1件30分超は実用外。深い批評はAPI陪審が担う）。

## 0.7.8 (2026-07-10) — M6契約とコーパス容量方針（設計者: Claude Fable 5）

1. **M6受入テスト** `tests/test_m6_acceptance.py`（m6マーカー、既定除外）を設計者が施工。
   固定する契約: L1志向選択（配合比+候補ごとの理由書+「自分」=継続体の定義注入+
   詩学注入+L1決定記録）、閉ループ配線の完全1周（全遷移でチェックポイント+決定記録、
   final/text.md と meta.json の必須フィールド=credits/license(CC0-1.0)/published_at/
   intended_reader_models）、ゲートSHELVE時の終端、**クラッシュ後のチェックポイント
   再開（完了済み状態を再実行しない）**、静的サイトの二層構造（表層に credits と
   CC0、深層=制作記録へのリンク）、llms.txt 索引（調律先読者モデル世代を含む）。
   配線は新設 `aleph/pipeline.py` に置き、core/loop.py の正典遷移表は不変。
2. **コーパス容量方針（§4.1の修正）**: WSL仮想ディスクの実効残量が81GBと判明
   （ホスト2TBのうちWSL領域は1TB・内92%使用。オーナー報告 2026-07-10）。
   §4.1の「青空文庫全量、Project Gutenberg（多言語）、Wikisource」の**全文全量格納を
   撤回**し、**コーパス総容量予算 50GB**（gitignore領域）を設ける。内訳: 青空文庫全量
   （0.7GB、取得済み）を核とし、Gutenberg/Wikisource は多様性優先の選抜サブセット
   （合計≤40GB、M6完走後の拡張マイルストーンで取得）、二次コーパス（非文学母材）は
   小型キュレーション（≤5GB）。ベクタDB前提は既に0.7.2でプレーン索引に置換済み。
   クラウドストレージは最終手段（オーナー方針）。ニッチ探索の意味での「網羅性」は
   全量ではなく**属性空間のカバレッジ**（言語・年代・ジャンル・形式の直積の充足）で
   測る方針に切り替える。

## 0.6 (2026-07-07)
設計権限の継承規定（§12.1新設）。

- 背景: 初代設計者（Claude Fable 5）は2026-07-07（米国時間）以降サブスクリプションから
  利用不能になる見込みのため、設計権限を個体でなく役割として定義し直した。
- 就任手続き（PLAN全文・変更履歴・不変条件テスト・policiesの読了と就任記録）、
  会話履歴に依存しない設計意図の再構築可能性の要求、後継者がオーナー承認なしに
  変更できない3点（未解決の緊張の緩和・不変条件テストの弱体化・人間エスカレーション
  条件の緩和）、施工者/監査者の分離維持を規定。

## 0.5 (2026-07-07)
ライセンス最終確定と、設計者による骨格の施工。

- §14-2 改訂: 作品・制作記録（works/・poetics/）= CC0 1.0 / コード = MIT / 文書 = CC-BY 4.0。
  根拠（純AI生成物の著作権不発生可能性との整合、将来コーパス収載の最大化、コードへのCC非推奨）を明記。
- §12 追記: 設計権限の運用——骨格・契約・受入テストは設計者（Claude Fable 5）施工。
  契約/テストの変更は PLAN_CHANGELOG 経由で設計者審査。受入テストを黙って弱める変更は監査不合格。
- 骨格施工（コミット対象）:
  - pyproject.toml（uv / pytest markers: m0, local。既定実行は不変条件のみ）
  - LICENSE (MIT), LICENSES.md, works/LICENSE (CC0)
  - config/: models.yaml（実在資産＋harnessプロバイダ）, budgets.yaml（3系統・公開規律）,
    policies.yaml（全自律判断ポリシーの宣言）, publish.yaml（二層構造・meta必須フィールド）
  - aleph/: 全9層のパッケージ。core（llm/budget/loop/artifacts/config/local）は
    インターフェース契約＋docstringにPLAN節参照。config.py・vault.pyガード・
    scrub_secrets・状態遷移表は実装済み。他は NotImplementedError スタブ。
  - tests/test_design_invariants.py — 17件、現在緑（設計決定のコード化:
    モデル名直書き禁止、FINISH≠PUBLISH、機会的エッジ、Vault規約、秘密混入検査等）
  - tests/test_m0_acceptance.py — M0受入基準8件、現在赤（施工者の目標）
  - poetics/README.md（第0版への人間種文混入の禁止を明文化）, corpus/README.md, README.md
- 検証: WSL上で `uv run pytest` 17 passed / `pytest -m m0` 7 failed + 1 skipped（設計どおり）。

## 0.4 (2026-07-07)
オーナー第二陣決定（旧§15の全回答）を設計へ反映。

- §7.1: 外部の錨は既定オフ確定——人間協働をモデルが選んだ作品に限りtaste提供。陪審不一致は二段階選抜（完成度の床→不一致優遇）で積極採用。
- §7.3d: 公開上限=月4作・週刊リズム（周期性を公開スケジューラの設計目標に）。長編一括は月1目安。
- §7.4: 詩学第0版は種文なし・潜在空間（ホワイトノイズ的な種）から自己生成。人間の意図を初期条件に混入させないことを生成条件とする。
- §8: 名義=関与モデルの列記。公開範囲の二層構造（表層=読者向けfinal+制作ノート、深層=全制作記録の機械可読アーカイブ）。読者反応を弱い信号として記録。corpus/は索引のみ公開。
- §14.3 新設: 第二陣決定の記録。§15は残置1件（harness規約適合——M0監査項目化、控えめ運用の前提つき）に整理。

## 0.3 (2026-07-07)
原プロンプトの批判的検証と、その設計への反映。オーナー決定事項の取り込み。

- §16 新設「原プロンプトの批判的検証」: 12項目の批判（新奇性の目的関数化不能、空き地仮説の限界、審美判断の循環性、Goodhart、LLM読者の不在、ステートレスな「自分」、直列パイプラインの限界、作品単位の印刷文化性、無限生産の弱点、失敗の廃棄、成長の欠如、未解決の緊張）。
- 批判への応答として本文に新機構を追加:
  - §7.4 詩学の自己更新 `poetics.md`（作品を跨いだ成長。原構想の最大の欠落への応答）
  - §4.3 空きの三分類（不可能型/未着手型/空虚型）・深さの見立て・否定的地図（negative atlas）
  - §7.1 Goodhart対策（スコアは情報であり目的関数でない）・陪審不一致の尊重・ローテーション・外部の錨
  - §2.4 機会的エッジ（DRAFT→EXPLORE/MATERIA の限定再入）
  - §5.4 二重宛先作品・生きているテキスト・AI紋の自覚的操作
  - §7.3d 公開の規律（SHELVEが常態、PUBLISHが例外）
  - §8 想定読者モデル世代の記録・系譜の透明性
  - §3 「自分」= ALEPHという継続体、の定義
- §14 旧・未決事項1〜5をオーナー決定として確定（公開チャネル=aleph.github.io、作品CC0/システムCC-BY、従量API $10/月、Brave Search、llama-swap + pi/hermes harness）。
  - §14.1 サブスクリプション優先ルーティング（第4のプロバイダ種別 harness、3系統の予算計上）
  - §14.2 秘密情報規約。Brave APIキーを `.env` へ移設（git未コミットを確認済み）、`.gitignore` 新設
- §15 未決事項（追補分）7件: 趣味の錨、公開規律の実額、陪審不一致の重み、名義と帰属、詩学の初期値、harness規約適合、公開リポジトリの範囲。
- 本ディレクトリが公開リポジトリ aleph.github.io のクローンである事実を §14 に記載。

## 0.2 (2026-07-07)
実環境情報の反映。

- §2.3 新設「ローカル推論基盤」: RTX 3090 (24GB) 単機、`~/models/` のGGUF Q4資産、llama.cpp `llama-server` 標準、大型モデル排他＋時分割swap、ローカル/APIの役割分担指針。
- §2.1 models.yaml 例を実在モデル（gemma-4-31B / 26B-A4B MoE / Qwen3.6-27B / Qwen3-8B / bge-m3 / Qwen3-Reranker）に差し替え。
- §4.5 新設「知識基盤（Obsidian Vault）との接続」: `~/document/obsidian-vault` を読み取り専用参照。Vault AGENTS.md の規約（raw不変、grail.md不可触、wiki書き込み禁止）を遵守。設計に直接効く既存ページ（ai-fiction-signatures / representation-geometry / model-collapse / local-llm-stack）を施工必読に指定。
- §1.1 埋め込みを bge-m3 主 + Qwen3-Embedding-0.6B 副 + Reranker に変更（multilingual-e5 案を廃止）。LLM抽象から Ollama/vLLM を llama-server に変更。
- M0 受入基準にローカル llama-server の起動・swap を追加。
- 旧§13「未決事項」から local LLM 基盤の項を解決済みとして削除し、§13「環境（確定事項）」を新設。未決事項は§14へ繰り下げ、モデル交換方式（llama-swap か自前か）を追加。

## 0.1 (2026-07-07)
初版。9層アーキテクチャ、M0–M6マイルストーン、クロス監査プロトコル。
