# ALEPH Phase 5C 正式監査 P2-1修繕 read-only 再監査

**監査者**: Claude Code (Opus 4.8) — 元正式監査と同一担当
**元candidate**: `fd9740f2595e5c5d0779661cb1cd67ea606827c2`
**修繕candidate**: staged tree `55960380567e5c040fb95cfbf9f77947644ee231`
**方式**: candidate・repositoryへの書込みなし。故障注入はすべて `/tmp/aleph-audit-p21` で実施

---

## 1. candidate固定（確認1–3）

```
git status --short   →  M README.en.md / M README.md / M aleph/pipeline.py
                        A reports/PHASE5C_FORMAL_MILESTONE_AUDIT_20260723.md
                        M tests/test_phase5_instrument_wiring.py
git write-tree       →  55960380567e5c040fb95cfbf9f77947644ee231   ✓一致
git diff --cached --check  →  違反なし
```

unstaged差分は無し（session開始時のsnapshotが示した `scripts/*.sh` 3件は WSL git では clean。`git diff -- scripts/` は空）。全作業の終了後も `write-tree` は `55960380…` のまま、statusも同一で、**candidate・repositoryは一切編集していない**（確認9）。

変更範囲は5ファイル、+192 / −10。`config/instruments.yaml`・`aleph/core/instruments.py` は無変更で、registry hash は `6bf77c9037…d707ce4`（元監査がsealed baselineと一致確認したもの）・9計器のまま。**既存testの改変・削除はゼロ**（tests差分は+42行の追加のみ）。

## 2. 修繕内容の照合

[aleph/pipeline.py:706-717](aleph/pipeline.py:706) — 終端record `input_refs` から `Budget.state_path` 由来の8行を除去。残る材料は

1. `works/<id>/seed.json`（run manifest本体）
2. `works/<id>/decisions.jsonl#run_completion=<ts>`（固定completion eventのcanonical hash）
3. `works/<id>/calls.jsonl`

の3件、いずれもwork単位。`identities` 側の `run_manifest` / `cost_envelope`（[pipeline.py:718](aleph/pipeline.py:718)）は保持されている。元監査 P2-1 の指示「work単位のrecordのidentity材料からrepository-global stateを外す」と正確に一致する。

回帰test [tests/test_phase5_instrument_wiring.py:175](tests/test_phase5_instrument_wiring.py:175) を修繕前treeへそのまま当てると **observably RED**:

```
E   AssertionError: assert 4 == 2
FAILED ...::test_terminal_reprojection_ignores_unrelated_shared_budget_state_changes
```

## 3. 独立故障注入（確認4・5）

施工者testとは別に書いた注入を `/tmp/aleph-audit-p21` の2 tree（`base`=fd9740f、`fixed`=staged tree）へ実行した。SimpleNamespaceではなく**実 `Budget`／`Router`／実 `config`** を使い、budget変動は「別workの実charge」で起こしている。

| 群 | base (fd9740f) | fixed (55960380) |
|---|---|---|
| **A** 同一環境で再投影 | 2 → 2 行 | **2 → 2 行** ✓ |
| **B** 無関係な共有budget chargeを挟んで再投影 | 2 → **4 行 DUPLICATE** | **2 → 2 行** ✓ |
| **D** work自身の `calls.jsonl` が変わって再投影 | 2 → 4 行 | 2 → 4 行 ✓（identityは依然binding） |
| **E** completion decision本文を改竄して再投影 | 2 → 4 行 | 2 → 4 行 ✓（同上） |

D・Eは陰性対照である。修繕が「identityを鈍らせて重複を消した」のではなく、**repository-globalな材料だけを外し、work単位証拠への束縛は保っている**ことを示す。

## 4. provenance / 意味の非弱化（確認6）

fixed treeの2 recordを実物で照合し、全項目一致した。

- `run.completion`: value=`complete_normal`、`measurement_status`=`observed`、`evidence_refs`=`[decisions.jsonl, seed.json]`
- `cost.reconciled_usd`: **value=`None`**、`measurement_status`=**`missing`**（0.0への差替えなし）、`confidence.reconciliation_status`=**`unreconciled`**、`unreconciled_breakdown`=`["provider statement missing"]`、`warnings`=`["provider statement absent; no reconciled amount claimed"]`、`identities.provider_pricing_date`=`missing-provider-statement`
- 両recordの `input_refs` は上記3件のみ、**全件がhashを保持**し、`budget` / `state/` を含むrefは0件
- `identities.run_manifest` / `identities.cost_envelope` は存置

修繕前treeにも `input_refs` へbudget refの存在を主張するtestは無く（`grep` 済み）、既存契約の緩和は起きていない。三面（provider明細／charge／call）が揃わない限り `missing/unreconciled` のままという性質は無変更である。

## 5. tests（確認7・8）

| 検証 | 元監査(fd9740f) | 本再監査(55960380) |
|---|---|---|
| Phase 5 focused | 82 passed | **83 passed, 24 deselected**（+1 = 新規回帰test） |
| `uv run pytest -q -m 'not local'` | 388 passed, 1 deselected | **389 passed, 1 deselected**（+1 = 同上） |
| `git diff --cached --check` | — | 違反なし |

増分がちょうど新規test 1件で、既存の落ち・skip・deselect増加は無い。

## 6. README機械同期の独立検証

`RepositoryReader(...).snapshot().readme_status_markdown()` を隔離tree上で実行し、生成blockを両READMEの `repository-snapshot` blockとバイト比較した。

```
README.md    machine-synced: True
README.en.md machine-synced: True     （n_formal_audits = 22）
```

21→22は `reports/*AUDIT*.md` を数える [aleph/core/repository_snapshot.py:221-223](aleph/core/repository_snapshot.py:221) の実出力であり、手書き値ではない。

## 7. Finding

**P0: なし。P1: なし。P2: なし。**

### P3-A — 未修繕P3-2との相互作用で、silent duplicationがfail-closed例外に変わる

修繕前は「共有budgetが動いた」ことがidentityを変え、元監査 P3-2（recovery時に `stop_path` が変わると同一id・別payloadになる、[aleph/pipeline.py:416-421](aleph/pipeline.py:416)）の衝突を**偶然マスクしていた**。P2-1修繕でそのマスクが外れる。実測:

```
                                        base        fixed
G budget変更・stop_path同一        →  4 rows      2 rows    ← P2-1修繕の効果
I budget変更・stop_path変更        →  4 rows      InstrumentError: measurement id collision
H budget同一・stop_path変更        →  InstrumentError（両tree同一、既知のP3-2）
```

**判断: 修繕を阻害しない。** 静かな重複行より fail-closed が正しい方向であり、Iで顕在化するのは修繕が新たに作った欠陥ではなく元監査が既に記録済みのP3-2そのものである。ただしP3-2の到達頻度は上がり、例外は `_finish_run_budget` の try/except（行読取りのみを覆う）を素通りして `run_pipeline` の外へ抜けたままである。P3-2の修繕は本依頼のscope外として拡張していない。

### P3-B — 修繕treeの `reports/` と `PROGRESS.md` が修繕を反映していない

staged treeは `reports/PHASE5C_FORMAL_MILESTONE_AUDIT_20260723.md` を原文のまま追加する一方（依頼どおり）、同じtree内で P2-1 が修繕済みであることを示す記載がどこにも無い。`PROGRESS.md` は無変更で、最新entryは施工者検証（step 11–12）のままである。結果として、このtreeを読む者は §6 P2-1 と §8「最初のprotected実走前に修正すべき実在の欠陥として記録する」を**未修繕の生きた欠陥**と読む。報告中の focused 82 / non-local 388 も現treeでは83 / 389である。

**判断: 測定の正しさには影響しない文書整合の問題**（P3）。原文保存という要件と両立させるなら、追記型の `PROGRESS.md` entry で「fd9740f の P2-1 を `55960380` で修繕、再監査記録は別artifact」と繋ぐのが筋である。

### 元監査の未修繕P3の阻害有無（scope拡張なし）

| 所見 | P2-1修繕を阻害するか |
|---|---|
| P3-1 review seam `measured_at` | しない。review seam専用で終端seamと材料を共有しない |
| P3-2 `stop_path` 衝突 | しない（上記P3-Aで詳述。マスクが外れるだけ） |
| P3-3 `identity.json` 不在で計器無言停止 | しない。`_instrument_recorder is None` で終端seamごと素通りする経路であり、identity材料と独立 |
| P3-4 `WorkReader.snapshot()` の touch | しない。mtimeのみでcontent非変更、`input_refs` は全て content hash |
| P3-5 索引再ハッシュ / P3-6 append の O(n²) | しない。性能のみ |

## 8. 判定

修繕は元監査P2-1の指摘に正確に対応している。repository共有 `budget.json` のhashは終端record `input_refs` から除かれ、identity材料はrun manifest・固定completion event・当該workのcalls.jsonlというwork単位の3件だけになった。独立に書いた実Budget/Router故障注入で、無関係な別workのcharge後の再投影が2行のままであること（B）、同一環境の再投影も2行のままであること（A）を確認し、同時にwork自身の証拠が変われば依然identityが変わること（D・E陰性対照）も確認した。`cost.reconciled_usd` は value=None / `missing` / `unreconciled` / warnings / `provider_pricing_date=missing-provider-statement` を保持し、`run.completion` のprovenanceも無変更で、三面照合が揃わない限り金額を主張しない性質は弱められていない。registry hashとinstrument定義は据置、既存testの改変はゼロ、focused 83 passed・非local 389 passed で増分は新規回帰test 1件のみ、その回帰testは修繕前treeで `assert 4 == 2` として observably RED である。README日英の件数はRepositorySnapshotの実出力とバイト一致する。candidateとrepositoryは監査中一切変更していない。P0・P1・P2は無い。P3-Aは既知P3-2のマスクが外れるという想定内の帰結で修繕を阻害せず、P3-Bは文書整合のみで測定の正しさに影響しない。

VERDICT: PASS
