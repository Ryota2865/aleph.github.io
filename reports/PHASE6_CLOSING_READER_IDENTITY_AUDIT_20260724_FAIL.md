# ALEPH Phase 6 独立形式監査

## 1. 候補identityとread-only範囲の確認

| 項目 | 監査時実測 | 供給値 | 一致 |
|---|---|---|---|
| `git rev-parse HEAD` | `216a9b5c1d65b31b48d593fffbf374f961b0b69c` | 同 | ✓ |
| `git write-tree` | `14772732aa87d1cfde6afd9a25493686bbc213f6` | 同 | ✓ |
| upstream | `main...origin/main` | 同 | ✓ |
| unstaged/untracked候補変更 | なし（`--untracked-files=all`で0件） | なし | ✓ |
| `git diff --check` | pass | pass | ✓ |
| 監査終了時の再測定 | tree・status ともに不変 | — | ✓ |

候補13ファイルはhandoffの一覧と完全一致。監査中に候補は変化していない。

read-only遵守: リポジトリへの編集・staging・commit・レポート書込みを一切行っていない。監査用の注入testは `/tmp/aleph_audit_probe_*.py`、identity再現物は `mktemp -d /tmp/aleph-phase6-audit.*` にのみ書いた。`git write-tree` はobject DBへtreeを書くが、index・worktreeは不変（runbook §1が指定する手順）。

**注記（判定には影響しない）:** セッション開始時のharness gitスナップショットは `scripts/aleph_cycle.sh` / `scripts/doctor.sh` / `scripts/start_local_stack.sh` を unstaged modified として記録していたが、私の最初の実測時点で既にcleanだった。いずれも候補パス外であり、候補tree hashは私の初回・最終測定の双方で供給値と一致している。

## 2. 実行コマンドと独立再現結果

```bash
bash scripts/doctor.sh                      # failures=0 warnings=1 (git worktree: has local changes)
UV_CACHE_DIR=/tmp/aleph-uv-cache uv run pytest -q <focused 4 files>   # 27 passed
UV_CACHE_DIR=/tmp/aleph-uv-cache uv run pytest -q -m 'not local'      # 405 passed, 1 deselected
UV_CACHE_DIR=/tmp/aleph-uv-cache uv run python -m compileall -q ...   # OK
```

tokenizer identityの独立再現（`/tmp`へ出力、リポジトリ不変）:

```
af98a8928972c29a99be5604daff1afaff411a1ace658cfae1935500e1e799a0
cmp config/identities/reader-tokenizer.json <tmp>/reader-tokenizer.json → CMP_IDENTICAL
```

さらに **builderとは別のアクセス経路** でGGUFを独立読み出しし、3配列のdigestを自前で再計算した:

| 配列 | count | 独立sha256 | builder sha256 | 一致 |
|---|---|---|---|---|
| `tokenizer.ggml.tokens` | 248,320 | `4945f5f4…6ddfc7` | 同 | ✓ |
| `tokenizer.ggml.token_type` | 248,320 | `14217cb1…6eb8e0` | 同 | ✓ |
| `tokenizer.ggml.merges` | 247,587 | `e98d54c5…236f63` | 同 | ✓ |

`len(field.data) == len(field.contents())` で全要素被覆を確認、`field.contents(i)` と全体取得の値一致もsample検証済み。llama.cpp HEAD = `d77599234ea6e498775aeadbce665eece5bd98cd`（供給値と一致）。GGUFは単一16.8GBファイル、`split.*` field なし。`general.file_type=15` / `general.quantization_version=2` はGGUF内に存在するがidentityへ混入していない（設計§3どおり）。

構築suiteの再実行に加え、公開interfaceに対する独立故障注入を **60件以上** 実施した（後述）。

## 3. 受入契約の評価

`designs/phase6-closing-reader-identity.md` §4に対して:

| # | 受入条件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 算出reserve / closing batch / closing poolの一致が自動検証される | **達成** | `budget.py:1207-1226`。batch単位・pool単位の両方を1e-9で照合。私の注入でも `0.39` 改竄・pool 0.41 改竄とも拒否 |
| 2 | 価格・ceiling・課金軸・slot被覆の欠陥がprovider call前にfail closedする | **達成** | 18種の奇形manifestすべてがparse時に例外。RealDeps構築時（provider call前）に発火 |
| 3 | 配列順序またはllama.cpp revisionの変更でidentityが変わる | **達成** | scalar 7項目・配列3種の順序/要素数/item_type・model_ref・revisionのすべてで独立に確認。length-prefixにより `["ab","c"]` と `["a","bc"]` も分離 |
| 4 | artifact改変とalias不一致でverified identityを主張しない | **部分達成** | alias照合は完全一致（大小・空白差でも `unverified` へ倒れる）。素朴な改竄も拒否。ただし **hash再計算を伴う偽造は `verified` として通る**（P3-4） |
| 5 | 全non-local回帰がgreen | **達成** | 405 passed, 1 deselected |

停止条件: 必須metadata欠落時の発行停止 ✓（builder・`create()` 双方）。provider固有課金軸の包絡 ✓（cached input / reasoning / 固定call料の5軸manifestが正しく導出、必須token軸を弱めない）。formal完了の先取り主張なし ✓（PLAN_CHANGELOG・PROGRESS・設計いずれも「tests greenであってformal audit PASSではない」と明記）。

**しかし、継承済みPhase 5契約と本候補自身の文書上の主張に対して未達がある**（§4 P2-1・P2-2）。documentation/実装の整合は、この2点を除き一致を確認した（248,320 / 247,587 / identity値 / llama.cpp revision / 405 passed はすべて実測一致）。新規secret・credential・provider明細の追加なし。

## 4. 指摘

### P2-1 — v2必須gateは耐久しない。checkpoint述語が実質無条件

`aleph/pipeline.py:608`

```python
if self._run_budget_plan.version < 2 and not work.checkpoint.exists():
```

観測1（`/tmp/aleph_audit_probe_budget.py::test_probe_forged_checkpoint_bypasses_the_v2_new_run_gate`）— v1 manifestは新規workで正しく拒否される。その直後 `checkpoint.json` に **`{}`** を書くだけで受理される。**`not json at all`** という非JSON文字列でも受理される。述語は `Path.exists()` のみで、状態の妥当性・整合・admission済みかを一切問わない。

```
A7 forged empty checkpoint accepted; plan version = 1 closing_reserve = None
A7 non-JSON checkpoint also accepted; version = 1
```

観測2（`/tmp/aleph_audit_probe_budget3.py::test_probe_v2_gate_is_not_durable_across_a_real_first_checkpoint`）— 偽造すら不要である。`run_work()` は `pipeline.py:252-255` で admission 直後・**あらゆるprovider call前** に `recover()` を呼び、そこでcheckpointを実体化する。したがって初回runがL1以降のどこで落ちても、以後このworkは恒久的に「checkpoint有り」になる。その状態でseedをv1へ書き戻すと:

```
C1 checkpoint materialised by recover(); no provider call was made
C1 resumed plan version: 1 closing_reserve: None
C1 v1 resume admitted batches: ['closing-author', 'heldout-jury', 'player-author']
```

runはそのまま全外部callを **導出されていないclosing reserve** の下で実行する。

これは `PLAN_CHANGELOG.md` 0.7.20-24 項2の「v1は…新しいprotected normal runはv2以外を拒否する。**これによりlegacy互換を新規runの抜け道にしない**」および設計§2と直接矛盾する。抜け道は敵対的操作を要さず、正常運用（1回目のrunが中断→seed編集→再開）で到達する。tracer bullet 1の統治上の主張が実装されていない。

### P2-2 — 価格・slot identityが予約identityの外にある。manifest versionも同様

`aleph/core/budget.py:91-106`（`BatchSpec.canonical`）、`416-417`・`440-441`（予約identity）、`517-522`（admit）、`547-548`（`load_run_plan_reservations`）、`1069`（`protected_definition_version` 固定）

handoffの明示的な設問への回答は **「はい、誤って再利用される」**。

観測（`/tmp/aleph_audit_probe_budget3.py::test_probe_reprice_closing_within_same_cap_reuses_reservation`）— provider `fixture`→`openai`、model→`gpt-5.5`、pricing_version→`openai-2099-01-01`、課金軸配分も `output_tokens 1×0.6` から `input_tokens 600000×1e-6` へ全面変更。数値合計 0.6 USD と caller供給 `input_manifest_hash` のみ保持:

```
C2 same reservation id: True
C2 stored spec keys: ['atomic_projection','batch_id','charged_to','expected_slots',
                      'input_manifest_hash','ledger','max_amount','phases','pool',
                      'protected_definition_version','role','semantic_retries','work_id']
C2 stored spec has any pricing field: False
```

同根の第2の現れ（`test_probe_v1_and_v2_batchspecs_are_indistinguishable`）— `batches` が同一なv1 manifestとv2 manifestは `BatchSpec.canonical()` が完全一致する。v2でadmitしたrunに対しv1 planで `load_run_plan_reservations()` が成功する:

```
A2 v1 plan rehydrated against v2 admission: ['closing-author','heldout-jury','player-author']
A2 protected_definition_version: phase5-v1
```

`budget.py:1069` は v2 manifestに対しても `protected_definition_version="phase5-v1"` を固定書きしており、protected定義が変わったにもかかわらずversionが追随しない。

これは継承契約への違反である。`designs/phase5-instruments-atlas-budget.md` §6.1 は `BatchSpec` が manifest で固定すべきものとして「**expected slot数とslotごとのprovider/modelまたはdeterministic adapter**」「protected定義version」を明記し、§6.2不変条件2は「同じ `command_id`/manifest hash の再試行は同じ予約を返す」と定めている。Phase 6 はまさにその per-slot provider/model を追加しながら、`batches` の兄弟要素として予約identityの外へ置いた。結果として `load_run_plan_reservations()`（存在理由が「admitted run batch identity mismatch」の検出）の改竄検知境界に **seedの `closing_slots` と `version` が入っていない**。admitされた導出根拠はどこにも耐久化されず、PLAN §11の再現性要件（決定論的再開）を満たさない。

なお金額包絡自体は守られている（`test_probe_changed_closing_batch_max_is_refused`: closing batch max を 0.6→0.7 に上げると `ValueError: pool limits are immutable` で拒否）。したがって本件は超過支出には至らないが、「closing reserveは価格版に束縛されて導出される」という契約が admission 後に成立しない。

### P3（残置リスクとして保存すべき有用な観測）

- **P3-1** `budget.py:131` — `unit_ceiling` に巨大int（`10**400`）を与えると `OverflowError: int too large to convert to float` になり、文書化された `ValueError` 契約から外れる。fail-closedではある。
- **P3-2** `budget.py:996` — closing batchが deterministic slot のみで構成される場合、`max_amount > 0` 制約により表現不能（`batches[2]: max_amount must be finite and >0, got 0.0`）。設計§2はdeterministic slotを0 USDの完了条件として登録すると述べており、external slotと混在するbatchでしか成立しない。
- **P3-3** `closing_slots` / `closing_reserve` は parse 以降どこからも参照されない。実際に実行されたslotが登録被覆と一致するかのruntime検証はない。また `pipeline.py:760` の `run.completion` の `closing_batch` identityは `batches` のclosing項目のみをhashし、価格付きslotを含まない（同742の `run_manifest` identityは全体を含むため、比較identityの分離自体は保たれる）。
- **P3-4** `tokenizer_identity.py:142-145` — artifactの自己hashは、hashを再計算しない改竄にのみtamper evident。偽造scalar + 再計算hashは `verified` として読み込まれる（`D2 forged scalar: forged`）。実効的な完全性の根拠はartifactではなくgit履歴にある。
- **P3-5** `tokenizer_identity.py:117` / `pipeline.py:665` — 再hashしたartifactの `tokenizer_metadata.scalars` を登録キー名のJSON配列にすると `set(scalars)` 比較を通過し、`TypeError: list indices must be integers` を送出する。pipelineのexcept節は `(OSError, ValueError, json.JSONDecodeError)` のみを捕捉するため、設計上の `unverified` フォールバックではなくrun crashになる。
- **P3-6** `scripts/build_reader_tokenizer_identity.py:35-40` — `git rev-parse HEAD` はtracked worktreeのdirty状態を検査しない。実測では llama.cpp に15件のdirty entryがあるが全て untracked（`.txt` / `uv.lock`）でtokenize実装への影響はなく、現行identityは忠実である。ただしtracked sourceを改変した状態では同一identityが発行され、比較不能なmeasurementを比較可能と主張しうる。
- **P3-7** builderは単一GGUFパスを読む。現行modelは単一ファイル（`split.*` field なし）のためsplit GGUFは未検証。またhash対象GGUFがllama-serverの実配信ファイルであること、`--llama-cpp-root` が実ビルドバイナリの出所であることを束縛する仕組みはない。
- **P3-8** `pipeline.py:656-661` — identity artifactのパスとaliasが単一固定。`reader_small` 等の他readerにverified identityの経路がない。

## 5. 残置リスクと未検証項目

- 有償provider callを一切実行していないため、reservation→charge→settle の実費経路と v2 導出上限の突合は未検証（本tracer bulletの範囲外・handoff指定どおり）。
- `semantic_retries` は導出上限をスケールしない（retries=0/3 いずれも reserve 0.6）。上限は予約残額で fail-closed に抑止されるため過剰支出には至らないが、retry前提のslotは上限をmanifest側で明示的に包絡する必要がある。この束縛はコードで強制されない。
- PROGRESS.mdの「doctorはfailures=0（NVML sandbox警告のみ）から開始した」の *開始時点* の状態は現時点で再現不能（現在の警告は `git worktree: has local changes`）。failures=0 は再現済み。
- Phase 5全体の再監査は行っていない（handoff指定）。継承契約は §6.1/§6.2/§6.3 の該当箇所のみ参照した。
- `PROGRESS.md` に `/home/ryota_tanaka/models/...` の絶対パスが1件増えるが、既存 `audits/` `reports/` に同種の記載が複数あり新規の秘密露出ではない。

**PASSの側の証拠として保存すべき積極的所見:** 導出・被覆・fail-closedの検証は堅牢である。18種の奇形入力（負/浮動小数ceiling、負/inf/bool単価、軸名重複・空白、kind改竄、非closing batch参照、slot重複、未知field、空slots/axes、version 3 / True / 2.0）がすべてprovider call前に拒否された。5軸（input/output/cached input/reasoning/固定call料）manifestが必須token軸を弱めずに正しく導出される。金額包絡はadmission後不変。tokenizer identityは全登録fieldに対し感度があり、GGUFからのbyte-identicalな再現と独立経路でのdigest一致が取れている。

## 6. 判定

P2を2件確認したため、`PLAN.md` §12 および `designs/formal-audit-runbook.md` の基準によりFAILとする。P2-1・P2-2は同一の根――**v2で追加した価格・slot・version情報が、予約identityにも耐久state にも入っていない**――から生じており、修復はこの一点に集約できる見込みである。P3群はrunbook §3の通り、修復後のPASSにおいて残置リスクとして明示保存されたい。

VERDICT: FAIL
