#!/usr/bin/env bash
# ローカル推論スタックの機能検証（PLAN §2.3 / M0受入のlocal項目）。
# start_local_stack.sh 起動後に実行。スワップ時間・埋め込み次元・VRAMを実測する。
set -uo pipefail

BASE=http://127.0.0.1:8080
SCOUT="gemma-4-26B-A4B-it-qat-UD-Q4_K_XL"
READER="Qwen3.6-27B-Q4_K_M"

echo "== 1) embeddings (bge-m3) =="
t0=$(date +%s)
dim=$(curl -s -m 300 "$BASE/v1/embeddings" -H 'Content-Type: application/json' \
  -d '{"model":"bge-m3","input":"文学的な生態系の空き地を探す。"}' \
  | grep -o '"embedding":\[[^]]*\]' | head -1 | tr ',' '\n' | wc -l)
echo "dim=$dim ($(( $(date +%s) - t0 ))s)"

echo "== 2) scout chat (first load timing) =="
t0=$(date +%s)
out=$(curl -s -m 600 "$BASE/v1/chat/completions" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$SCOUT\",\"messages\":[{\"role\":\"user\",\"content\":\"「アレフ」の作者は?名前のみ\"}],\"max_tokens\":16}")
echo "elapsed=$(( $(date +%s) - t0 ))s"
echo "$out" | head -c 300; echo

echo "== 3) swap to reader (swap timing) =="
t0=$(date +%s)
out=$(curl -s -m 600 "$BASE/v1/chat/completions" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$READER\",\"messages\":[{\"role\":\"user\",\"content\":\"say ok\"}],\"max_tokens\":4}")
echo "swap_elapsed=$(( $(date +%s) - t0 ))s"
echo "$out" | head -c 200; echo

echo "== 4) bge-m3 still resident after swap? =="
t0=$(date +%s)
code=$(curl -s -o /dev/null -w '%{http_code}' -m 60 "$BASE/v1/embeddings" -H 'Content-Type: application/json' \
  -d '{"model":"bge-m3","input":"persistence check"}')
echo "http=$code embed_elapsed=$(( $(date +%s) - t0 ))s (数秒以内なら常駐維持)"

echo "== 5) VRAM =="
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader

echo "== 6) ALEPH_LOCAL=1 pytest -m local =="
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ALEPH_LOCAL=1 uv run pytest -m local -v 2>&1 | tail -8
