#!/usr/bin/env bash
# aleph run を呼び出し元セッションから完全に切り離して実行する。
# Claude Code / ターミナルの再起動でループが死なないようにするための起動口。
# 使い方: bash scripts/run_work_detached.sh w0001
# ログ: state/run_<id>.log(追記) / PID: state/run_<id>.pid
set -euo pipefail
cd "$(dirname "$0")/.."
work_id="${1:?usage: run_work_detached.sh <work_id> [extra aleph-run args...]}"
shift
extra_args=("$@")   # 追加引数(例: --force-audience "LLM 0.6 / 自分 0.25 / 人間 0.15")を aleph run に透過
log="state/run_${work_id}.log"
pidfile="state/run_${work_id}.pid"
if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
  echo "already running: pid $(cat "$pidfile")" >&2
  exit 1
fi
# setsid -f が必須: -f なしだと fork されず呼び出しセッションに残り、
# wsl.exe セッション終了時の掃除で殺される(sleep プローブで実証済み)。
extra_quoted=""
if ((${#extra_args[@]})); then
  extra_quoted=$(printf ' %q' "${extra_args[@]}")   # 各引数を安全に再クオート(空白含む配合比対応)
fi
setsid -f bash -c "echo \$\$ > '$pidfile'; exec uv run python -m aleph.cli run --work '$work_id'$extra_quoted >> '$log' 2>&1"
sleep 1
echo "detached: work=${work_id} pid=$(cat "$pidfile") log=${log}"
