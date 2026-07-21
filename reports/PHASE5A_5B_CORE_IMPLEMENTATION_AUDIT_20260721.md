# Phase 5A / 5B core 独立設計適合監査

## 1. candidate identity と worktree 確認

| 項目 | 値 |
|---|---|
| 指示書 SHA-256 | `0fa4738f…96d6` ✓ 一致 |
| HEAD | `569cf57d2f95a160168ca82c5c9336d04160670b` ✓ 対象commitと一致 |
| worktree (WSL git) | clean（`git status --short` 空） |
| `git diff --check efd927b..569cf57` | exit 0（whitespace/衝突マーカーなし） |
| 差分規模 | 20 files, +1900/−72、2 commits（`d1c9dca` 5A / `569cf57` 5B core） |

candidateは固定できました。WSL側gitが権威（Windows側の`M scripts/*.sh`はWSLでは未変更）。read-onlyを厳守し、repository・work・state・reportへの書込み、provider callは一切行っていません。故障注入はすべてWSLの一時ディレクトリで実行しました。

## 2. 独立実行した検証と結果

| 検証 | 結果 |
|---|---|
| `bash scripts/doctor.sh` | **failures=0 warnings=0** |
| focused pytest（9ファイル） | **72 passed, 1 skipped** |
| `uv run pytest -m 'not local'` | **349 passed, 1 deselected**（施工者記録と完全一致・独立再現） |
| `git diff --check` | クリーン |

独立故障注入（既存テストで保証されない境界、いずれも一時領域）：

- **Budget 16件全PASS**: 別instanceからのscope残額奪取拒否（cross-instance admission）、同一command+manifest→同一予約 / 異manifest→`ReservationConflict`、`charge_id`再生no-op、settle冪等 / 別command→conflict、実額>予約→chargeを保存し`unreconciled`（precheck例外で捨てない）、unreconciled後の次admission/reservation拒否、held_out不足→player借用成立、held_out不足かつplayer枯渇→拒否、player不足→借用不可拒否、closing不足→借用不可拒否。
- **Atlas / atomic projection / termination 18件全PASS**: artifact 1 byte改変を`verify`と`load()+verify`がfail closed、`identity.json` payload 1 byte改変→hash不一致、build_specへのtimestamp混入拒否、bit同一のみcomparable。3-slotの最後がparse失敗→`INCOMPLETE_PARSE`、call失敗/未記録→`INCOMPLETE_CALL`（いずれもmean/stddev不生成）、全valid→`COMPLETE`＋母標準偏差(`pstdev`)、未登録retry拒否、証拠衝突拒否、projection冪等、projection後record拒否。modern stop(`budget`)とL7(`aesthetic_failure`)不一致→warning発火かつ明示L7採用（隠さない）、`budget`→`resource_stop`。
- **Instrument 8件全PASS**: 台帳9件ロード、observed `0.0`受理（欠測と区別）、observed None拒否、missing-with-value拒否、`provisional`は`decision_value`不適格、必須identity欠落拒否、atlas identity不一致→`comparable=False`かつdelta None、同一identity数値→delta生成。

台帳整合: `config/instruments.yaml`の9計器 id/version/status を `designs/instruments.md` §3 と1件ずつ照合し、全一致を確認。

## 3. Findings

**P0–P2: none**

監査事項A–Fの各不変条件を、コード根拠と独立再現の両方で確認しました。予約会計（`spent + active commitments + requested <= cap` をledger/work/scope/poolの多層で維持）、非対称借用のcode固定（manifest側に借用fieldが存在せず注入不能）、事前admissionと事後settlement/recoveryのseam分離（reservation付きchargeは`precheck`送出経路を通らず`unreconciled`として保存）、atomic projectionの逐次硬化と部分証拠の非勝敗化、AtlasIdentityのbit同一性による比較単位化、termination四分類の単一写像共有とlegacy推定の`inferred`明示——いずれも設計に適合し、5A/5B coreが主張する保証に欠陥は見つかりませんでした。

## 4. P3 残余risk（非阻害）

1. **非予約(legacy)chargeのunreconciled不追跡**: `Router._invoke`の`except`は`budget.charge`が例外送出時に完了callをRouter call logのみへ`billing_status=unreconciled`で記録するが、Budget台帳の`_unreconciled_charge_ids`には入らない（`budget.py:492-498`のprecheck経路）。ただしこれはPhase 5前からの非予約経路であり、**保護batch(予約付き)経路は`precheck`を通らず必ずchargeとして保存されるため本監査scopeの不変条件は保持**。Budget側`status().unreconciled`が非保護callで過少報告し得る点のみ将来risk。
2. **build_spec不安定field拒否の部分性**: `_reject_unstable_build_fields`（`atlas_identity.py:75`）は`created/timestamp/absolute_path/index_dir`のキー名と、"path"を含むキーの絶対値のみ拒否。別名キー下のtimestampはpayloadへ流入し得る。設計はpayload構成をcaller責務とするため防御は多層の一つに留まる。
3. **`compare()`のfalsy比較identity扱い**: `if not a or not b`（`instruments.py:217`）は将来的に数値0やFalseの比較keyを「欠落」と誤報し得る。現行の全comparability keyは文字列identityのため無害。
4. **台帳↔registryの自動照合欠如**: `test_instrument_registry.py`はyaml側の9件・サンプルstatusを検証するが、`instruments.md`本文をparseして突合しない（期待値ハードコード）。現時点はmd/yaml一致だが、将来のdrift検知は手動監査依存。
5. **closing配線未実装によりclosing系受入(§13.9/§13.17)がe2e未実行**（下記5に整理、非阻害）。

## 5. 未実装境界の確認

以下が未実装であることを、コードと文書の両方で確認し、**完了済みと誤表示していない**ことを検証しました。
- 通常runのclosing reservation自動admission・終了配線・role別batch配線 — `PROGRESS.md:18`が「次のtracer bullet」と明示。`run.completion`は`provisional`で判定に非流用。
- Phase 5C（fixation sealed fixture校正、novelty等の実配線）、Atlas再構築とfull identity初回発行、新規有料実走 — `designs/phase5-instruments-atlas-budget.md:5`が「未着手」と明記。
- 設計文書・reportの状態行はいずれも本candidateを「Phase 5全体完了」ではなく「5A/5B core実装済み」に正しく限定。

したがってF.2の懸念（未実装を完了表示）は該当なし。今回範囲のP0–P2修繕のための追加分割は不要です。

## 6. 総括

観測: focused/全non-local/doctorが独立再現で全green、42件の独立故障注入が全PASS、台帳9件が整合、diff --checkクリーン、worktree clean。
推論: 5A/5B coreの各不変条件（記録fail-closed、比較拒否、Atlas fail-closed、予約会計と非対称借用、実行後保存、atomic非勝敗化、四分類単一写像、epoch警告）はコード根拠と再現の双方で成立。
解釈: 本candidateはPhase 5A/5B coreの設計契約に適合し、tests-greenとは独立にVERDICTを支持できる。残余はいずれもP3で、candidateの主張範囲を侵さない。
将来: closing配線・5C・Atlas再構築は未実装（正しく開示済み）であり、本PASSはそれらの完了・正式Phase 5完了を意味しない。

VERDICT: PASS
