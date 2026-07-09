#!/usr/bin/env bash
# ローカル推論スタックの起動（PLAN §2.3）。冪等: 既に起動中なら何もしない。
#
# 使い方: bash scripts/start_local_stack.sh
# 前提:
#   - ~/.local/bin/llama-swap が導入済み（github.com/mostlygeek/llama-swap）
#   - ~/llama.cpp/build/bin/llama-server が CUDA有効でビルド済み
#   - config/llama-swap.yaml のGGUFパスが実在する
#
# 起動後、127.0.0.1:8080 で OpenAI互換 /v1/chat/completions・/v1/embeddings に
# モデル名ベースで自動スワップしながら応答する。ログは state/llama-swap.log。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${REPO_ROOT}/config/llama-swap.yaml"
STATE_DIR="${REPO_ROOT}/state"
LOG_FILE="${STATE_DIR}/llama-swap.log"
PID_FILE="${STATE_DIR}/llama-swap.pid"
LISTEN_ADDR="127.0.0.1:8080"
LLAMA_SWAP_BIN="${LLAMA_SWAP_BIN:-${HOME}/.local/bin/llama-swap}"

mkdir -p "${STATE_DIR}"

is_up() {
  curl -s -o /dev/null -w "%{http_code}" "http://${LISTEN_ADDR}/v1/models" 2>/dev/null | grep -q "^200$"
}

if is_up; then
  echo "[start_local_stack] already running and responding at http://${LISTEN_ADDR}/v1/models — nothing to do."
  exit 0
fi

# 既存プロセスがpidファイルに残っているが応答しない場合は掃除してから起動し直す
if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    echo "[start_local_stack] stale process (pid ${old_pid}) is running but not answering health check; leaving it alone and aborting."
    echo "  確認: ps -p ${old_pid} / kill ${old_pid} で手動停止してから再実行してください。"
    exit 1
  fi
  rm -f "${PID_FILE}"
fi

if [[ ! -x "${LLAMA_SWAP_BIN}" ]]; then
  echo "[start_local_stack] llama-swap バイナリが見つかりません: ${LLAMA_SWAP_BIN}" >&2
  exit 1
fi

echo "[start_local_stack] starting llama-swap on ${LISTEN_ADDR} (config: ${CONFIG})"
nohup "${LLAMA_SWAP_BIN}" -config "${CONFIG}" -listen "${LISTEN_ADDR}" \
  >> "${LOG_FILE}" 2>&1 &
new_pid=$!
disown "${new_pid}"
echo "${new_pid}" > "${PID_FILE}"

echo "[start_local_stack] waiting for health check (pid ${new_pid})..."
for _ in $(seq 1 30); do
  if is_up; then
    echo "[start_local_stack] up: http://${LISTEN_ADDR}/v1/models"
    exit 0
  fi
  sleep 1
done

echo "[start_local_stack] timed out waiting for llama-swap to become ready. Check ${LOG_FILE}." >&2
exit 1
