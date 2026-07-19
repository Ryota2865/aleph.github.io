# ALEPH Phase 2 — P2-1 Fix Re-audit

**監査日時**: 2026-07-19 (UTC) / **対象**: `main` @ `09f77c9`（worktree、コミット前変更）
**範囲**: 前回 FAIL の P2-1 の解消可否のみ（read-only、Phase 2 全体は再監査せず）

## Formal Verdict

**P2-1 は解消された。** 修正は最小・局所（`aleph/core/model_output.py:159-160` の2行追加）で、要求4項目すべてを満たす。リポジトリは変更していない。

## 修正内容と根拠

`parse_model_output` に scan-warning ガードが追加された：

```python
# aleph/core/model_output.py:159-160
if scan_warnings and fail_closed:
    return ModelOutput(None, raw, None, None, tuple(warnings))
```

`scan_warnings` の唯一の発生源は `_json_values` の `_DuplicateKey` 捕捉（`:79-81`）であり、duplicate key 検出時のみ発火する狭いガードになっている。候補走査（`candidates[0]` 採用）に到達する前に返るため、前回の「矛盾オブジェクトの内部/後続を救済して `ok=True`」経路が閉じている。

## 必須確認の結果

| # | 確認項目 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 外側 duplicate `publish` + 内部に schema 一致オブジェクトを持つ入力で fail_closed=True → value=None/ok=False | **PASS** | 前回 P2-1 の完全再現入力（`…"extra":{"publish":false,"reason":"y"}`）で `value is None and not ok` を実測 |
| 2 | duplicate-key warning が保持される | **PASS** | `warnings == ('duplicate JSON key: publish',)` |
| 3 | fail_closed=False の既存契約を不必要に変更していない | **PASS** | fail_closed=False では同入力で従来どおり先頭候補 `{'publish': False, 'reason': 'y'}` を返し duplicate warning も保持。clean multiple の先頭採用も不変 |
| 4 | 指定コマンド実行 | **PASS** | 下記 |

### Independent Verification（実行コマンドと結果）

- `TMPDIR=/tmp uv run pytest -q tests/test_model_output.py --capture=no` → **4 passed**（新規回帰 `test_duplicate_key_in_outer_object_fails_closed_even_with_later_valid_object` を含む）
- `TMPDIR=/tmp uv run pytest -q -m 'not local' --capture=no` → **284 passed, 1 deselected**（前回283 → 回帰テスト+1、退行なし）
- `git diff --check` → 空（exit 0）

回帰再現スクリプト（/tmp のみ、リポジトリ非変更）で9アサーション全通過：Req1–3、単純 duplicate 拒否、clean 単一で warning 無し（誤検知なし）、multiple の fail-closed 維持、fail_closed=False の先頭採用維持。

## Findings

新規所見なし（P0/P1/P2/P3 いずれもなし）。前回報告の P3-1〜P3-3（探索 caller の multi-JSON 歩留まり、テスト数の軽微な陳腐化、README 日英非対称）は本修正の対象外であり、非阻害のまま残存（PASS と両立）。

## Residual Risks

- ガードは `scan_warnings`（現状 duplicate-key のみ）全般に対して fail-closed 化する。将来 `_json_values` が別種の非致命 warning を足すと、それも fail_closed=True で拒否対象になる点は設計上の含意として認識しておくべき（現時点では該当なし・問題なし）。

VERDICT: PASS
