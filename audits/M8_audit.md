VERDICT: FAIL

## Findings

1. **公開意思ゲートが作品本文を見ずに PUBLISH できる**  
   [aleph/meta/publication_gate.py](/home/ryota_tanaka/llm_literature/aleph/meta/publication_gate.py:33)  
   `_ask_publish_intent()` のプロンプトには `audience` しか入っておらず、作品本文・抜粋・タイトル・査読結果が渡されません。`PLAN_CHANGELOG 0.7.15` の「この作品を公開するか著者に問う」契約に対し、実際には同じ宛先配合なら異なる作品でも同一判断になります。  
   失敗シナリオ: 品質床を偶然超えた弱い作品と公開に値する作品がどちらも `自分 0.9 / 人間 0.1` の場合、著者は内容を見ないまま同じ publish intent を返し、前者も `PUBLISH` され得ます。

2. **`"publish": "false"` が `PUBLISH` と解釈される**  
   [aleph/meta/publication_gate.py](/home/ryota_tanaka/llm_literature/aleph/meta/publication_gate.py:43)  
   `bool(parsed.get("publish"))` は非空文字列を常に `True` にするため、LLM が JSON で `"publish": "false"` と返すだけで公開扱いになります。フォールバックの `"公開する"` 部分一致も、「公開するべきではない」を誤判定し得ます。同じバグは実験Eの集計にもあります: [scripts/exp_publish_framing.py](/home/ryota_tanaka/llm_literature/scripts/exp_publish_framing.py:67)。  
   実際に再現し、`{'publish': 'false'}` で `{'decision': 'PUBLISH', ...}` になりました。外部公開は不可逆寄りの操作なので、これは高リスクです。

3. **LLM審級の perplexity 実測が閉ループ本体に配線されていない**  
   [aleph/pipeline.py](/home/ryota_tanaka/llm_literature/aleph/pipeline.py:560)  
   `run_review()` は `reader_llm` が渡された時だけ perplexity を記録しますが、`RealDeps.critique_and_revise()` は `reader_llm=self._reader_llm` を渡していません。  
   失敗シナリオ: `--force-audience "LLM 0.7 / 人間 0.2 / 自分 0.1"` で通常の制作ループを走らせても、M8仕様の「LLM最大宛では reader_model の logprobs から perplexity 曲線を査読報告に載せる」は発火しません。追加テストは `run_review()` 直呼びだけを検証しており、実配線の欠落を捕まえていません。

4. **改稿指示蒸留が正当な欠落指摘を捨てる**  
   [aleph/critique/review.py](/home/ryota_tanaka/llm_literature/aleph/critique/review.py:182) / [aleph/critique/review.py](/home/ryota_tanaka/llm_literature/aleph/critique/review.py:199)  
   `"ありません"` を含む行を一律で空扱いにしているため、`結末への伏線がありません` や `人物Aの動機がありません` のような典型的な欠落指摘が改稿指示から消えます。  
   失敗シナリオ: scout が「伏線がありません」と減点要因を正しく抽出しても、author には渡らず、M8の「課題だけを残す」目的に反します。

## Verification

- `UV_CACHE_DIR="$PWD/.codex-audit-cache" XDG_CACHE_HOME="$PWD/.codex-audit-cache" PYTHONDONTWRITEBYTECODE=1 uv run pytest -m 'not local' -q -p no:cacheprovider`  
  PASS: `136 passed, 1 deselected in 5.67s`

- `UV_CACHE_DIR="$PWD/.codex-audit-cache" XDG_CACHE_HOME="$PWD/.codex-audit-cache" PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY' ...`  
  FAIL expected/reproducer: `{"publish": "false"}` が `PUBLISH` になることを確認。

- `UV_CACHE_DIR="$PWD/.codex-audit-cache" XDG_CACHE_HOME="$PWD/.codex-audit-cache" uv cache clean`  
  PASS: audit 用キャッシュ削除済み。Tracked files は汚していません。