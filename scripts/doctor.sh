#!/usr/bin/env bash
# Read-only ALEPH/WSL environment diagnostics. Never prints credentials.
set -u

network=0
case "${1:-}" in
  "") ;;
  --network) network=1 ;;
  -h|--help)
    printf 'Usage: bash scripts/doctor.sh [--network]\n'
    printf '  default: local checks only; --network also verifies GitHub API access\n'
    exit 0
    ;;
  *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac

failures=0
warnings=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

require_command() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "$1: $(command -v "$1")"
  else
    fail "$1: not found"
  fi
}

if grep -Eqi 'microsoft|wsl' /proc/version 2>/dev/null; then
  pass "runtime: WSL"
else
  warn "runtime: WSL was not detected"
fi

if [[ "$(id -un)" == "ryota_tanaka" ]]; then
  pass "user: ryota_tanaka"
else
  warn "user: $(id -un) (expected ryota_tanaka)"
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ "$repo_root" == "/home/ryota_tanaka/llm_literature" ]]; then
  pass "repository: $repo_root"
elif [[ -n "$repo_root" ]]; then
  warn "repository: $repo_root (canonical path differs)"
else
  fail "repository: not inside a git work tree"
fi

for command_name in git gh uv claude hermes; do
  require_command "$command_name"
done

if gh auth token >/dev/null 2>&1; then
  pass "gh local credential: present (value hidden)"
else
  fail "gh local credential: unavailable; run gh auth login in WSL"
fi

helpers=$(git config --get-all credential.https://github.com.helper 2>/dev/null || true)
if grep -q 'gh auth git-credential' <<<"$helpers"; then
  pass "git credential helper: gh auth git-credential"
else
  warn "git credential helper: gh helper not configured; run gh auth setup-git"
fi

if [[ "$network" -eq 1 ]]; then
  if account=$(gh api user --jq .login 2>/dev/null); then
    pass "GitHub API: authenticated as $account"
  else
    warn "GitHub API: unavailable; sandbox network permission may be required"
  fi
else
  pass "GitHub API: skipped (use --network)"
fi

if [[ -n "$repo_root" ]]; then
  branch=$(git branch --show-current 2>/dev/null || true)
  remote=$(git remote get-url origin 2>/dev/null || true)
  [[ -n "$branch" ]] && pass "git branch: $branch" || warn "git branch: detached or unknown"
  [[ -n "$remote" ]] && pass "git origin: $remote" || warn "git origin: missing"
  if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
    pass "git worktree: clean"
  else
    warn "git worktree: has local changes"
  fi
fi

llama_bin=/home/ryota_tanaka/llama.cpp/build-cuda129/bin/llama-server
gemma_model=/home/ryota_tanaka/models/gguf/gemma4/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf
qwen_model=/home/ryota_tanaka/models/gguf/qwen36/Qwen3.6-27B-Q4_K_M.gguf

[[ -x "$llama_bin" ]] && pass "llama-server: $llama_bin" || fail "llama-server: missing"
[[ -f "$gemma_model" ]] && pass "Hermes gemma4 model: present" || fail "Hermes gemma4 model: missing"
[[ -f "$qwen_model" ]] && pass "Hermes qwen36 model: present" || fail "Hermes qwen36 model: missing"

if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -Eq ':8081\b'; then
  warn "port 8081: listening; verify /v1/models before local worker use"
else
  pass "port 8081: free or not visible"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  if gpu=$(nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>/dev/null); then
    pass "GPU: $gpu"
  else
    warn "GPU: NVML unavailable; sandbox GPU permission may be required"
  fi
else
  warn "GPU: nvidia-smi not found"
fi

if [[ -n "$repo_root" ]]; then
  disk=$(df -h "$repo_root" 2>/dev/null | awk 'NR==2 {print $4 " free of " $2}')
  [[ -n "$disk" ]] && pass "WSL disk: $disk" || warn "WSL disk: unavailable"
fi

printf 'SUMMARY failures=%d warnings=%d network=%d\n' "$failures" "$warnings" "$network"
[[ "$failures" -eq 0 ]]
