# W0009 Publication Shadow — August Gate 月境界RED 最小修正 focused再監査

**再監査担当**: 20260730 正式監査PASSを発行した同一Claude Code担当（独立read-only）
**再監査日**: 2026-08-01
**保存想定path**: `reports/W0009_PUBLICATION_SHADOW_AUGUST_GATE_REAUDIT_20260801.md`（allowlist登録済み・本報告が投入対象）

## 0. 候補identity（監査中に不変・再確認済み）

| 項目 | 期待 | Observed | 判定 |
|---|---|---|---|
| Branch | codex/phase6-r9-audit-ledger-path-disjoint | 同左 | ✓ |
| Commit | 760e97b…081ca | 760e97b503d7789ebd98bb5cbe52491c038081ca | ✓ |
| Tree | eb7c4cd…d6468b | eb7c4cdf32c6a97f99865052932afe2bd6d6468b | ✓ |
| Parent | 3e04808…05242 | 3e048080f17e805d7d4ede90a5fc65eec1805242 | ✓ |
| 作業ツリー | clean HEAD | WSL git（authoritative）で `git status --porcelain` 空 | ✓ |

監査開始時と終了時でHEAD/tree/parent一致。identity driftなし。

**Uncertainty（P3, 非阻害）**: Windows Git Bash側の `git status` は3スクリプト(`aleph_cycle.sh`/`doctor.sh`/`start_local_stack.sh`)を`M`表示するが、差分はmode 100755→100644のみ・内容差分ゼロ・tree hash不変。WSL側gitはこれを検出せずclean。runnerの`verify_audit_gate`が要求する`git status --porcelain`空はWSL実行環境で成立する。commit導入の変更ではない。

---

## 1. tests-green（formal verdictとは分離して記録）

指定コマンドを独立再実行（WSL `.venv/bin/python`）。**以下はグリーンの事実であり、それ自体はPASS判定の根拠ではない。**

| コマンド | 期待 | Observed |
|---|---|---|
| pytest 3ファイル（shadow/snapshot/design_invariants） | 65 passed | **65 passed** ✓ |
| pytest -m 'not local' | 453 passed, 1 deselected | **453 passed, 1 deselected** ✓ |
| compileall aleph scripts tests | OK | exit 0 ✓ |
| git diff --check | clean | exit 0 ✓ |
| run_w0009…verify | manifest/2/3.9968/VERIFIED_NOT_RUN/[] | 完全一致 ✓ |
| audit_repository_snapshot --format report | PASS/20260730/NEEDS_AUDIT/HEAD | 完全一致 ✓ |

---

## 2. 中心確認（Observed / Inference / Uncertainty 分離）

### 確認1 — 期限action反映 ✅
**Observed**: `config/budgets.yaml` L3 `api.usd_per_month: 45.0`、L17 `publish.max_per_month: 4`。コメントに「hard capであり公開目標ではない」「2026-07のcap $71と実績は遡及変更しない」。L8の旧comment「月上限44が最終防壁」→「月次hard cap $45が最終防壁」へ校正。config内にactiveな71.0/999/44は残存せず（71は「遡及変更しない」文言中のみ）。
**Inference**: 期限actionは45/4のhard capとして正しく反映。7月値は履歴として保全。

### 確認2 — 二つのREDを/tmpで独立再現 ✅（CONFIRMED）
**Observed**: parentツリーを`git archive 3e04808`で`/tmp/red_repro`へ展開し、**config 45/4のみ**適用（candidateのtest修正は不適用＝`restore_july_caps`不在をgrep=0で確認）。対象2テスト実行結果：
- `test_execution_is_blocked_until_date_and_cap_actions`: 7/30のblockerが`('earliest run date has not arrived',)`のみとなり、**cap blocker二件**（"monthly API cap is not the preregistered 45 USD" / "publish.max_per_month is not the preregistered value 4"）が消失 → `FAILED`（"Right contains 2 more items"）。
- `test_budget_declares_owner_decisions`: `assert 45.0 == 71.0` → `FAILED`。
- 合計 `2 failed`。
**Inference**: RED根因は「可変configをfixtureへコピーする構造」により、config=preregistered値(45/4)になると7/30故障注入のcap判定が同値化して消える点。candidateの修正はこの根因（症状ではなく）に対応。

### 確認3 — 修正が最小 ✅
**Observed**:
- `_copy_preregistered_fixture`に`restore_july_caps`パラメータ追加。**期限gate test 1本のみ** `restore_july_caps=True`で71/999をfixtureに明示復元。
- 7/30 blockerは**date + cap(45不一致) + publish(4不一致)の三件**を維持（`sed -n 107-116`）。8/1は`_enable_august_caps`後 `()` 空。
- `test_budget_declares_owner_decisions`は`45.0`/`4`の**具体的等値assert**に更新（範囲化・削除・弱体化なし）。コメントは期限履歴(45/4・8–9月承認)へ同期。
- production変更は`scripts/run_w0009_publication_shadow.py`の**+1行**（allowlist path追加）のみ。`git show`でaleph/・works/・poetics/・state/への変更ゼロを確認。
**Inference**: shadow順序・parse・retry・reserve・immutabilityは不変（core packageに一切触れていない）。中心assert（3-tuple blocker、空tuple、45/4等値、code拒否）はすべて保持。

### 確認4 — 再監査artifact保存経路 ✅
**Observed**: `POST_AUDIT_ALLOWED_PATHS`への追加は固定path `reports/W0009_PUBLICATION_SHADOW_AUGUST_GATE_REAUDIT_20260801.md` **一件のみ**。汎用`reports/` globなし、code/test許可拡張なし。gate logic（L52-89）は`changed - allowlist`が空でなければ`PublicationShadowError`。
- `test_audit_gate_binds_clean_head_commit_tree_and_terminal_pass`: fake diffに当該reaudit path＋config＋PROGRESSを含めPASS → 固定path許容を検証。
- `test_audit_gate_rejects_post_audit_code_change`: fake diff=`aleph/core/llm.py` → "outside the execution allowlist"でraise → **code拒否維持**。
**Inference**: allowlist拡張はdisjointかつ最小。code/testのpost-audit変更拒否は温存。

### 確認5 — preregistrationと実行前状態 ✅
**Observed**: `verify`出力 — manifest_sha256 `c327aaf811e05433b1db76bf4ba3955a54e30470857bf12697d29053b07b2f32`、packet_count `2`、reserve_usd `3.9968`、status `VERIFIED_NOT_RUN`、execution_blockers `[]`。`works/w0009/publication_shadow/`には`preregistration.json`のみで`results`ディレクトリ不在。commitはworks/・poetics/・state/に非接触。
**Inference**: preregistrationは凍結identityを保持。有償call・canonical作品・publication disposition・poeticsに変更なし。`execution_blockers=[]`は「45/4反映かつ2026-08-01が最早実行日以降」による正当な準備完了状態（未実行）。

### 確認6 — 費用記録 ✅
**Observed（PLAN_CHANGELOG 0.7.20-42 / PROGRESS 2026-08-01）**: 7月総費用`$89`＝「オーナー報告・内訳未提示」と明記。OpenAI `$11.80`/Anthropic `$13.80`＝「2026-08-01時点のbest-effort残高」「provider明細とのbest-effort運用情報でありcall/charge台帳と混同しない」と明記。
**独立算術検証**: reserve `$3.9968` < Anthropic残高 `$13.80` → 残高内 ✓。W0010最大`$9`連続時の理論残余 = 13.80 − 3.9968 − 9.00 = **$0.8032** → 記載と一致 ✓。表現は「理論上の残余」「手動チャージを判断」で自動チャージ・provider cost一致を断定せず。
**Inference**: provider残高とrepository台帳は明確に分離。算術正確。

### 確認7 — README表示の正直性 ✅
**Observed**: README.md/README.en.md snapshot block — changelog `0.7.20-42`、currency `NEEDS_AUDIT`、Deadline `none recorded / 記録なし`。
**Inference/根拠**: `repository_snapshot._deadlines`は`publish_cap==999`のときのみ期限entryを返す。現cap=4のため`()`を返し「none recorded」が生成される正しい出力。currency NEEDS_AUDITは最終audit(20260730)以降にtreeが変化（unexpected paths: PLAN/config/scripts/tests）した事実を正直に反映。test_repository_snapshot緑で埋め込みブロックが生成器と一致することを検証済み。

---

## 3. Findings（P0–P3分類）

- **P0 / P1 / P2**: なし。paid executionを阻害するfindingなし。
- **P3（非阻害・観測のみ）**:
  1. Windows Git Bash側のscript mode差分(755→644)。WSL authoritative gitではclean。tree不変・内容差分ゼロ。commit外の環境artifact。
  2. `repository_snapshot._deadlines`は999条件のJuly例外テキストをハードコードで内包（cap=4の現在は休眠）。将来別月が正当に999を用いると同一Julyテキストが再表出しうる潜在事項。本監査対象commitの欠陥ではない。

いずれもFAIL根拠にならず、paid shadowの阻害要因ではない。

---

## 4. 判定サマリ

- 候補identity: 監査中不変（drift/中断なし）。
- 中心確認1–7: すべて充足。REDは/tmpで独立再現、最小修正は根因対応、allowlistはdisjoint固定path一件、費用算術は正確、README表示は正直。
- tests-green（65 / 453+1deselected / compile / diff-check / verify / snapshot）は事実として確認、formal verdictとは分離。
- P0–P2およびpaid execution阻害findingなし。

**tests-green ≠ formal verdict** を明示した上で、証拠に基づき合格と判断する。

VERDICT: PASS
