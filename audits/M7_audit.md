VERDICT: FAIL

## Findings

1. `aleph/draft/revise.py:134` / `aleph/pipeline.py:276`: `LLMResponse.truncated` が改稿経路で使われていません。`RealDeps._author()` が `.text` だけを返すため、provider が `truncated=True` を立てても `revise()` には伝わらず、`revise()` も長さ `0.8` 未満だけでフォールバック判定しています。例えば max_tokens で切れた改稿が旧稿の85%長ある場合、文中終止のまま採用されます。`state/tasks/M7_experiments_spec.md:68` の「応答が truncated なら節単位改稿へフォールバック」に未達です。テストも `tests/test_m7_regressions.py:202` で短い文字列を返すだけで、truncated フラグ経路を検査していません。

2. `aleph/critique/review.py:293` / `aleph/critique/review.py:306` / `aleph/pipeline.py:104`: 最高スコア版をログには記録しますが、返り値と公開本文選抜は最新 draft のままです。`critique_revise_loop()` は `best_version` ではなく `version` を返し、`_finalize_publish()` は `work.latest_draft_version()` を final にコピーします。例えば v2 が最高点で v3 が劣化版の場合でも、PUBLISH 時には v3 が公開本文になります。`state/tasks/M7_experiments_spec.md:74` の「best_version を返り値/決定ログに記録し、公開・棚の本文選抜と一貫」に未達です。`tests/test_m7_regressions.py:273` はむしろ `final_version == 3` を期待しており、不具合を固定しています。

3. `state/tasks/M7_experiments_spec.md:155` / `PROGRESS.md:592`: 実験Cの受入条件が未達です。`reports/EXP_intent_attractor_*.md` は存在せず、PROGRESS も「実験C は中断」と記録しています。変更セットにスクリプトはありますが、契約で求められた20走の集計レポートがないため、M7完了条件を満たしていません。

4. `state/tasks/M7_experiments_spec.md:156` / `works/w0004/checkpoint.json:3` / `PROGRESS.md:596`: w0004 は終端状態ではありません。現在の checkpoint は `MATERIA` で、PROGRESS の「実行中」PIDも実プロセスとして確認できませんでした。`materials に anti_cliche カード、criteria に技法注入、decisions に owner-experiment` という完了条件のうち、少なくとも終端到達と後続成果物が未達です。

5. `aleph/pipeline.py:441` / `aleph/materia/ai_native.py:59`: LLM宛の anti_cliche 素材は1枚しか追加されません。仕様は `state/tasks/M7_experiments_spec.md:108` で「平均logprob最低の2文」を素材カードとして追加する契約です。現状の回帰テスト `tests/test_m7_regressions.py:327` は「1枚でも混ざる」ことしか見ないため、この逸脱を検出できません。

6. `aleph/materia/similarity.py:91`: `focus_vec` の候補制限が kNN 後のフィルタになっています。仕様 `state/tasks/M7_experiments_spec.md:30` は「候補チャンクを focus_vec 近傍上位に制限してから従来のkNN対探索」です。現実には full index で `knn_k` 件を取ってから `focus_allowed` を弾くため、focus 上位チャンク同士が互いの full-kNN に入らない場合、subset 内では成立する対を見逃します。素材の作品別生成が空振りし、旧来と同じ固定素材に近づくリスクがあります。

## Verification

- `export UV_CACHE_DIR="$PWD/.codex-audit-cache" XDG_CACHE_HOME="$PWD/.codex-audit-cache"; uv run pytest -q; rc=$?; echo "EXIT=$rc"; rm -rf "$PWD/.codex-audit-cache"; exit $rc`
  - PASS: `17 passed, 110 deselected`, `EXIT=0`

- `export UV_CACHE_DIR="$PWD/.codex-audit-cache" XDG_CACHE_HOME="$PWD/.codex-audit-cache"; uv run pytest -m 'not local' -q; rc=$?; echo "EXIT=$rc"; rm -rf "$PWD/.codex-audit-cache"; exit $rc`
  - PASS: `126 passed, 1 deselected`, `EXIT=0`

監査用 `.codex-audit-cache` は削除済みです。ソースファイルは編集していません。