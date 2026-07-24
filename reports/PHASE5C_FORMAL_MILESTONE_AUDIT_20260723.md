# ALEPH Phase 5C 正式milestone監査（read-only）

**監査者**: Claude Code (Opus 4.8) — 施工者Codexとは別担当（PLAN §12 クロス監査）
**candidate**: `fd9740f2595e5c5d0779661cb1cd67ea606827c2`（HEAD、worktree clean）
**baseline**: `8f8bd59d470d9c8db8cd927cbbf93ed8f9293896`
**方式**: candidate・repositoryへの書込みなし。故障注入はすべて `/tmp/aleph-audit-fd9740f` で実施

---

## 1. candidate固定

```
git status --short  →  (空)
git rev-parse HEAD  →  fd9740f2595e5c5d0779661cb1cd67ea606827c2
```

dirty HEADではなく commit SHA で固定済み。runbook §1の要件を満たす。

変更範囲（baseline→candidate）: 17ファイル、+1896 / −11。
**modified**: `PROGRESS.md`, [aleph/cli.py](aleph/cli.py), [aleph/core/artifacts.py](aleph/core/artifacts.py), [aleph/core/instruments.py](aleph/core/instruments.py), [aleph/critique/review.py](aleph/critique/review.py), [aleph/explore/atlas.py](aleph/explore/atlas.py), [aleph/pipeline.py](aleph/pipeline.py)。
**deleted**: なし。**既存テストの改変**: なし（新規3ファイルのみ追加）。`config/instruments.yaml` は無変更（registry hash据置）。

## 2. tests-green（formal verdictとは別評価）

| 検証 | 施工者報告 | 本監査の独立再現 |
|---|---|---|
| `bash scripts/doctor.sh --network` | — | `failures=0 warnings=0 network=1` |
| Phase 5 focused | 82 passed | **82 passed** ✓一致 |
| `uv run pytest -q -m 'not local'` | 388 passed, 1 deselected | **388 passed, 1 deselected** ✓一致 |
| `git diff --check`（working tree / baseline→candidate） | 違反なし | **CLEAN** ✓一致 |

tests-greenは再現した。これはverdictそのものではない。

## 3. 独立故障注入（`/tmp`のみ、59項目）

repositoryのモジュールを import して、施工者のtestとは別に書いた注入を実行した。

| 群 | 結果 | 主な確認 |
|---|---|---|
| Budget（受入7,8,14,15,16,17a） | 18/18 pass | player→held_out借用のみ成立（`{held_out:1.0, player:2.0}`）、player→他・closing→他は `BudgetExceeded`、manifestへの `borrow_from` / `borrowing_matrix` 注入は unknown key で拒否、再起動後もclosing commitment残存（active/2.0）、同一`charge_id`はspent・行数とも不増、予約超過の実行済みcallは `billing_status=unreconciled` で**保存**され次callを拒否、admission失敗時は予約もpool limitも残らない |
| AtlasIdentity / InstrumentRecord（受入1,2,3,4,13） | 25/25 pass | 7 artifactすべてで1 byte改変→`AtlasIdentityError: Atlas artifact hash mismatch: <name>`、`Atlas.load()`もfail closed、build_spec単独変更でidentity変化、`identity.json`偽造を拒否、timestamp混入を拒否、cross-Atlas / cross-epoch は `comparable=false` かつ `delta=None`、missing≠0.0、provisionalは `decision_value` 不可、retired計器は新規record不可、破損streamはfail closed |
| runtime配線（受入5,10,11,12） | 17/18 pass | 3 slot中末尾parse破壊→`INCOMPLETE_PARSE`（mean/argmax/scoresを出さない）かつ前2 slotのcall/charge/raw hashを保持、未登録retry拒否、review seamで `disagreement=2.0 (4,8のみ)` / `parse.reliability=2/3`、reader欠如時にlogprob行を捏造しない、実`works/w0009`は `resource_stop / stop_path=budget / inferred=False`、実`works/w0007`は `termination=None`（遡及推定なし）、`Budget`にowner-only interfaceなし |
| closing / 終了境界（受入9,14,17） | 13/13 pass | player枯渇＋closing生存→`complete_short`、正規settle→`complete`、closing外部settle→`resource_interrupted`、overageでunreconciled化したclosing→`resource_interrupted`、未admission→`resource_interrupted`（`complete`にならない）、terminal recoveryで `run_completion` decisionは1行のまま・`finish_run_budget` 再実行なし |

唯一の非passは「実works読取りで何も書かれない」で、原因はP3-4（後述、candidate由来ではない）。

## 4. 実データ read-only 確認

`AtlasIdentity.load` → `verify()` = **True**、`Atlas.load()` = **PASS**。

- identity: `8ab3e51a4d8c64bdbb456b2dc7dbea9bdf4fe71f60888eda997203c4c59827ca`（報告と一致）
- labels/density 95,690、style 95,690×9、label集合 `{-1:86137, 0:9106, 1:153, 2:242, 3:52}`、non-noise cluster **4**
- registry 9計器、hash `6bf77c90…d707ce4`。sealed baseline 8 record の `registry_hash` と一致
- sealed fixture 5件すべて存在（w0004/w0005/w0007/w0008 quotation/w0008-w0009 backstage反例）、`sealed:true`, `purpose:calibration_evaluation_only`, `prohibited_uses:[classifier_training, prompt_tuning, label_revision_from_evaluation_results]`

**plain index の同一性**（報告の主張を独立検証）:

```
manifest.json    12f98717…d046e22   source == new
chunks.jsonl     10398555…2e5415b1  source == new
embeddings.npy   3f573315…56896664  source == new
```

**不変性**: `git diff baseline..candidate -- works audits` は空。`audits/` 無変更。`state/atlas/` 全ファイルの mtime は 2026-07-10〜07-17（07-23の再構築で未接触）。既存 `works/` 配下に `measurements.jsonl` は1件も存在しない。新規 provider call・新作生成・corpus再取得なし（新規scriptに `requests/httpx/openai/anthropic/Router/subprocess` の参照なし、`calls.jsonl` の差分なし）。

## 5. 17受入条件の照合

1–17すべて、施工者報告とは独立の証拠で **満たされている**（§3・§4の各行が対応証拠）。11については実w0007にmodern terminationがないため登録fixtureで `aesthetic_failure` 境界を検証する扱いを妥当と判断する（推定値を実作へ書き戻していない点が重要）。

## 6. Finding

### P2-1 — 終端recordのidentity材料にrepository共有の可変ファイルが混入し、recoveryで重複行が出る

[aleph/pipeline.py:718-724](aleph/pipeline.py:718) が `state/budget.json`（`Budget.state_path`、[aleph/core/budget.py:143](aleph/core/budget.py:143)、CLIでは全work共有）のハッシュを `input_refs` に入れる。`measurement_id` はこの `input_refs` から導出されるため（[aleph/core/instruments.py:185-189](aleph/core/instruments.py:185)）、終端recordの同一性が**当該workと無関係な予算活動**に依存する。

独立注入（`/tmp`）:

```
A 同一環境で再投影            : 2 → 2 行   OK
B 共有budget.jsonが動いた後   : 2 → 4 行   DUPLICATE（measured_at・value は同一）
```

`reports/PHASE5C_INSTRUMENT_WIRING_20260723.md` の「terminal recoveryで同じcompletion/costを再投影しても2計器2行のままである」は、共有台帳がbyte同一のときにだけ成立する。実運用では他workのcharge/settleで容易に破れる。

影響の限度: 値は両行とも `complete_normal` で虚偽ではなく、`run.completion`(文字列)・`cost.reconciled_usd`(missing) はいずれも `compare()` で非比較となり誤差分も生まない。重複課金・二重settleが起きないことは§3で独立確認済み。既存workは `measurements.jsonl` を持たないため既存データへの影響はゼロである。

**判断**: milestoneをFAILにするほどの誤測定ではない（値の捏造でも受入条件の破綻でもない）。ただし Phase 6 で最初のprotected runがmeasurementを書く前に修正すべき欠陥として記録する。work単位のrecordのidentity材料からrepository-global stateを外すのが筋の修正である。

### P3-1 — review seam recordが呼出しごとに新しい`measured_at`を取るため、同一版の再査読が比較可能な別recordになる

[aleph/pipeline.py:655](aleph/pipeline.py:655) の `"measured_at": _now_iso()` により、`critique_revise_loop`（常に `version = 1` から開始、[aleph/critique/review.py:590](aleph/critique/review.py:590)）が同じv1を再査読すると新しい `measurement_id` で行が増える。独立確認:

```
同一 measured_at で再投影   : 3 → 3 行（冪等）
新しい measured_at で再投影 : 3 → 6 行
compare(同一草稿の2回計測)  : comparable=True, delta=0.0
```

`subject_ref` も `identities` も同一なので、台帳不変条件3（比較identity不一致にdeltaを作らない）では捕まらない。juror scoreが確率的な実runでは、**同じ草稿を測り直しただけ**の差がdeltaとして出る。終端seamが `existing["ts"]` を再利用して冪等性を確保している（[aleph/pipeline.py:405-424](aleph/pipeline.py:405)）のと対照的で、review seamには同じ保護がない。

### P3-2 — recovery時に`stop_path`が変わると終端seamが`InstrumentError`で落ちる

[aleph/pipeline.py:418-422](aleph/pipeline.py:418) は保存済みdecisionから `category`/`ts` を読む一方、`stop_path` は生きた `ctx` から渡す。`stop_path` は `confidence` に入り `measurement_id` には含まれないため、両者が食い違うと同一id・別payloadとなり `measurement id collision` が送出される。注入で再現:

```
C stop_path を変えて再投影 : InstrumentError -> measurement id collision: 5fcf86bc…
```

再開後にclosingを喪失して `ctx["stop_path"]="closing_lost"`（[aleph/pipeline.py:341](aleph/pipeline.py:341)）になる経路が該当する。fail closedではあるが、`_finish_run_budget` の try/except は行読取りしか覆っておらず、例外は `run_pipeline` の外へ抜ける。

### P3-3 — `identity.json`が無い索引を指すと計器配線が無言で無効化される

[aleph/pipeline.py:626-641](aleph/pipeline.py:626)。`identity_path.is_file()` が偽なら `_instrument_recorder` は `None` のままで、warningもdecision記録も残らずrecordが一切作られない。設計 §5.3 と受入5は legacy/partial identity を **warning** にすることを求めている。`state/` は `.gitignore` 対象（[.gitignore:9](.gitignore:9)）で、CLI既定が `state/atlases/phase5c-…-v1` に切り替わった（[aleph/cli.py:243](aleph/cli.py:243), [aleph/cli.py:258](aleph/cli.py:258)）ため、別環境では「計測なしで走り切る」状態になりうる。

### P3-4 — read-onlyのはずの`WorkReader.snapshot()`が既存workのevent ledgerをtouchする

`WorkReader.snapshot()` → `_canonical` → `ExperimentRun.open()`（[aleph/core/work_snapshot.py:506](aleph/core/work_snapshot.py:506)）→ [aleph/core/experiment.py:145](aleph/core/experiment.py:145) の `run.events_path.touch(exist_ok=True)`。独立probe:

```
w0007 {"added": [], "removed": [], "changed": []}
w0009 {"added": [], "removed": [], "changed": ["experiment/events.jsonl"]}
```

内容はHEADと同一（`git diff --quiet` 通過）で、変わるのは mtime のみ。同関数は `manifest.json` 不在時には **書込み**も行う（[aleph/core/experiment.py:141](aleph/core/experiment.py:141)）。**candidate由来ではない**（`work_snapshot.py`・`experiment.py` はbaselineから無変更）が、受入5「既存workを書き換えない」を読取り経路が構造的に保証していない点として記録する。

### P3-5 — 索引読込みごとに約894MBを再ハッシュする

[aleph/pipeline.py:634-635](aleph/pipeline.py:634) は `RealDeps` 構築のたびに `AtlasIdentity.verify()` を呼び、`embeddings.npy` 391MB・`chunks.jsonl` 501MB を含む全artifactをSHA-256する。正しさの問題ではないが、`run`/`publish` の起動コストとして記録する。

### P3-6 — `InstrumentRecorder.append`がstream全体を毎回読み直す

[aleph/core/instruments.py:259-273](aleph/core/instruments.py:259)。追記のたびに既存全行を parse・canonicalize するため計測数に対してO(n²)。1 workあたりの行数が小さい現状では問題にならない。

**P0/P1: なし。**

## 7. 残余リスク（欠陥ではない設計上の帰結）

- `atlas_meta.json` は `created` timestamp を含み、これがartifact hashに入る。設計 §5.2 は「identity一致＝bit同一artifactの再利用」と明言しており整合的だが、結果として**同一入力からの独立再構築は原理的に別identityになる**。novelty値は将来にわたり再導出できず、保存artifactの保全がそのまま比較可能性の前提になる。
- cluster数4は現行PCA64/eom構成の粗さの再現であり、corpusの均質性の証拠ではない（施工者報告の記述に同意する）。
- `cost.reconciled_usd` はprovider明細adapter不在のため観測値を出せない。0でなく `missing/unreconciled` として保存する選択は台帳不変条件4に適う。
- reader tokenizer は `provider-default:<model>:unverified` であり、cross-run比較の根拠にできない。
- house-style classifier の model/prompt と人間label合意床、semantic retry既定値、closing予約金額、次Atlas corpus拡張、Author候補と費用削減床は引き続きowner判断。

## 8. 判定

Phase 5C step 9–12 の実装は、17受入条件すべてを独立再現で満たす。sealed fixation fixture/baselineは封印済みで再生成可能、full Atlas identityは実artifactに対してverifyし、`Atlas.load()` は7 artifactいずれの1 byte破損でもfail closedする。runtime `InstrumentRecord` 配線は parse失敗を0点に偽装せず、provider明細欠如を欠測として保存し、resource stopを美的失敗へ落とさない。既存 `state/atlas`・`works`・`audits` は内容が一切変更されておらず、provider callも新作生成も混入していない。P0・P1は無い。P2-1は最初のprotected実走前に修正すべき実在の欠陥として記録するが、値の捏造でも受入条件の破綻でもなく、既存artifactへの影響はない。

VERDICT: PASS
