#!/usr/bin/env bash
# ALEPH の発火(1サイクル): ローカルスタック起動 → 新規作品 → 閉ループ実行(切り離し)。
#
# 使い方:
#   bash scripts/aleph_cycle.sh              # 新規作品を作って回す
#   bash scripts/aleph_cycle.sh w0003        # 既存作品を(チェックポイントから)再開する
#
# 進行確認:
#   tail -f state/run_<id>.log               # 実行ログ
#   tail works/<id>/decisions.jsonl          # 状態遷移と各層の意思決定
#   uv run python -m aleph.cli status        # 予算3系統
#
# 停止: kill $(cat state/run_<id>.pid)  (チェックポイントから再開可能)
# 注意: 予算上限(config/budgets.yaml)に達すると擱筆または precheck 停止する。
#       月初にAPI台帳が自動でリセットされる。無人常駐はしない(PLAN §15-1)。
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/start_local_stack.sh

if [[ $# -ge 1 ]]; then
  work_id="$1"
else
  work_id="$(uv run python -m aleph.cli new 2>&1 | grep -o 'w[0-9]\{4\}' | head -1)"
  echo "[aleph_cycle] created ${work_id}"
fi

bash scripts/run_work_detached.sh "${work_id}"
echo "[aleph_cycle] running. watch: tail -f state/run_${work_id}.log"
