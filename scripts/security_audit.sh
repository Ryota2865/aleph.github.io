#!/usr/bin/env bash
# Read-only inventory of Python / Node.js / npm / PHP / Claude Code on the local
# WSL machine, compared against the October 2026 security releases.
# Never prints credentials. Changes nothing. See SECURITY_UPDATE_PLAN_2026-10.md.
#
# Usage: bash scripts/security_audit.sh            # WSL side only
#        bash scripts/security_audit.sh --windows  # also query the Windows host via cmd.exe
set -u

windows=0
case "${1:-}" in
  "") ;;
  --windows) windows=1 ;;
  -h|--help)
    printf 'Usage: bash scripts/security_audit.sh [--windows]\n'
    exit 0
    ;;
  *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac

# ---- fixed versions (2026-10-21 security releases) --------------------------
# Node.js: nodejs.org/en/blog/vulnerability/october-2026-security-releases
NODE_FIX_22=22.23.4
NODE_FIX_24=24.22.1
NODE_FIX_26=26.12.1
# CPython: 3.12.15 / 3.13.16 (2026-10-01 security fixes); 3.13.17 / 3.14.9 (2026-10-21, tarfile CVE-2026-114583)
PY_FIX_312=3.12.15
PY_FIX_313=3.13.17
PY_FIX_314=3.14.9
# PHP (php2shell CVE-2026-109618 / CVE-2026-109619)
PHP_FIX_82=8.2.35
PHP_FIX_83=8.3.36
PHP_FIX_84=8.4.27
PHP_FIX_85=8.5.12
UBUNTU_PHP83_FIX=8.3.6-0ubuntu0.24.04.13   # USN-8948-1 (noble keeps upstream 8.3.6)
# PyPI packages
BROTLI_FIX=1.2.1        # CVE-2026-111497 (Brotli OOB write)
PILLOW_FIX=13.0.0       # CVE-2026-112900 (EPS/Ghostscript argument injection)
LITELLM_BAD=1.107.0     # 2026-10-21 PyPI supply-chain compromise

failures=0
warnings=0
pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }
info() { printf 'INFO  %s\n' "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

# version_ge A B  -> true when A >= B (dotted numeric versions)
version_ge() {
  [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" == "$1" ]]
}

check_node_version() {  # $1 = label, $2 = version like v22.22.0
  local label=$1 v=${2#v}
  local major=${v%%.*}
  case "$major" in
    22) version_ge "$v" "$NODE_FIX_22" && pass "$label: v$v (>= $NODE_FIX_22)" || fail "$label: v$v < $NODE_FIX_22 (CVE-2026-111497 Brotli RCE etc.)" ;;
    24) version_ge "$v" "$NODE_FIX_24" && pass "$label: v$v (>= $NODE_FIX_24)" || fail "$label: v$v < $NODE_FIX_24 (CVE-2026-111497 Brotli RCE etc.)" ;;
    26) version_ge "$v" "$NODE_FIX_26" && pass "$label: v$v (>= $NODE_FIX_26)" || fail "$label: v$v < $NODE_FIX_26 (CVE-2026-111497 Brotli RCE etc.)" ;;
    *)  fail "$label: v$v is an end-of-life line (no October 2026 fix); move to 22/24/26" ;;
  esac
}

check_python_version() {  # $1 = label, $2 = version like 3.13.17, $3 = optional path
  local label=$1 v=$2 path=${3:-} fix=""
  case "$v" in
    3.12.*) fix=$PY_FIX_312 ;;
    3.13.*) fix=$PY_FIX_313 ;;
    3.14.*) fix=$PY_FIX_314 ;;
    3.15.*) pass "$label: $v (current line; confirm >= 3.15.1)"; return ;;
    3.10.*|3.11.*) warn "$label: $v (3.10 is end-of-life; 3.11 ends 2027-10; prefer >= 3.12 for this repo)"; return ;;
    *) warn "$label: $v (unrecognised line)"; return ;;
  esac
  local note=""
  [[ "$fix" == "$PY_FIX_312" ]] && note="; tarfile CVE-2026-114583 backport pending upstream"
  if version_ge "$v" "$fix"; then
    pass "$label: $v (>= $fix$note)"
  elif [[ -n "$path" ]] && dpkg -S "$path" >/dev/null 2>&1; then
    local pkg; pkg=$(dpkg -S "$path" 2>/dev/null | head -n1 | cut -d: -f1)
    warn "$label: $v < $fix but it is the distro package $pkg ($(dpkg-query -W -f='${Version}' "$pkg" 2>/dev/null)); Ubuntu backports fixes without changing the version: rely on 'apt pending' below and USN notices"
  else
    fail "$label: $v < $fix"
  fi
}

check_php_version() {  # $1 = label, $2 = version like 8.3.6
  local label=$1 v=$2
  case "$v" in
    8.2.*) version_ge "$v" "$PHP_FIX_82" && pass "$label: $v" || warn "$label: $v < $PHP_FIX_82 upstream; distro backport may still be patched (see changelog check)" ;;
    8.3.*) version_ge "$v" "$PHP_FIX_83" && pass "$label: $v" || warn "$label: $v < $PHP_FIX_83 upstream; distro backport may still be patched (see changelog check)" ;;
    8.4.*) version_ge "$v" "$PHP_FIX_84" && pass "$label: $v" || warn "$label: $v < $PHP_FIX_84 upstream; distro backport may still be patched (see changelog check)" ;;
    8.5.*) version_ge "$v" "$PHP_FIX_85" && pass "$label: $v" || warn "$label: $v < $PHP_FIX_85 upstream; distro backport may still be patched (see changelog check)" ;;
    *) fail "$label: $v is end-of-life (<= 8.1); php2shell is unfixed there" ;;
  esac
}

# $1 = python executable; checks brotli / pillow / litellm and .pth hooks
check_python_packages() {
  local py=$1
  [[ -x "$py" ]] || return
  local out
  out=$("$py" -I - <<'EOF' 2>/dev/null
import importlib.metadata as m, site, sys, os
def v(n):
    try: return m.version(n)
    except m.PackageNotFoundError: return ""
print("brotli", v("Brotli") or v("brotli"))
print("brotlicffi", v("brotlicffi"))
print("pillow", v("pillow"))
print("litellm", v("litellm"))
paths = set(site.getsitepackages() if hasattr(site, "getsitepackages") else [])
paths.add(site.getusersitepackages())
for p in sorted(paths):
    if not os.path.isdir(p): continue
    for f in sorted(os.listdir(p)):
        if f.endswith(".pth"):
            print("pth", os.path.join(p, f))
EOF
)
  [[ -n "$out" ]] || { warn "$py: could not introspect packages"; return; }
  while read -r key val; do
    case "$key" in
      brotli)
        [[ -z "$val" ]] && continue
        version_ge "$val" "$BROTLI_FIX" && pass "$py brotli $val" || fail "$py brotli $val < $BROTLI_FIX (CVE-2026-111497)" ;;
      brotlicffi)
        [[ -z "$val" ]] && continue
        version_ge "$val" "1.2.1.0" && pass "$py brotlicffi $val" || fail "$py brotlicffi $val < 1.2.1.0 (CVE-2026-111497)" ;;
      pillow)
        [[ -z "$val" ]] && continue
        version_ge "$val" "$PILLOW_FIX" && pass "$py pillow $val" || fail "$py pillow $val < $PILLOW_FIX (CVE-2026-112900 EPS/Ghostscript)" ;;
      litellm)
        [[ -z "$val" ]] && continue
        if [[ "$val" == "$LITELLM_BAD" ]]; then
          fail "$py litellm $LITELLM_BAD: compromised PyPI release (2026-10-21). Treat host as compromised; see plan §4.4"
        else
          info "$py litellm $val (not the compromised 1.107.0)"
        fi ;;
      pth)
        case "$(basename "$val")" in
          distutils-precedence.pth|_virtualenv.pth|uno.pth|easy-install.pth|*editable*.pth|__editable__*|*.egg-link) ;;
          *) warn "unexpected .pth hook (review contents): $val" ;;
        esac ;;
    esac
  done <<<"$out"
}

# ---------------------------------------------------------------------------
section "runtime"
if grep -Eqi 'microsoft|wsl' /proc/version 2>/dev/null; then pass "runtime: WSL ($(uname -r))"; else warn "runtime: WSL not detected ($(uname -r)); this script targets the local WSL machine"; fi
[[ -r /etc/os-release ]] && info "distro: $(. /etc/os-release && echo "$PRETTY_NAME")"
info "user: $(id -un)"
info "date: $(date -u +%Y-%m-%dT%H:%MZ)"

# ---------------------------------------------------------------------------
section "Python interpreters"
declare -A seen_py=()
for cand in python3 python python3.12 python3.13 python3.14 python3.15; do
  p=$(command -v "$cand" 2>/dev/null) || continue
  real=$(readlink -f "$p")
  [[ -n "${seen_py[$real]:-}" ]] && continue
  seen_py[$real]=1
  v=$("$real" -c 'import platform;print(platform.python_version())' 2>/dev/null) || continue
  check_python_version "PATH $cand -> $real" "$v" "$real"
done
if command -v uv >/dev/null 2>&1; then
  info "uv: $(uv --version 2>/dev/null)"
  while read -r line; do
    [[ -z "$line" ]] && continue
    ver=$(sed -nE 's/^cpython-([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' <<<"$line")
    path=$(awk '{print $2}' <<<"$line")
    [[ -n "$ver" ]] && check_python_version "uv-managed $path" "$ver" "$(readlink -f "$path" 2>/dev/null)"
  done < <(uv python list --only-installed 2>/dev/null | grep -v '^$')
else
  warn "uv: not found (this repository is driven with uv)"
fi
for d in "$HOME/.pyenv/versions"/*/; do
  [[ -d "$d" ]] || continue
  vdir=$(basename "$d")
  [[ "$vdir" =~ ^3\.[0-9]+\.[0-9]+$ ]] && check_python_version "pyenv $vdir" "$vdir"
done
if [[ -x .venv/bin/python ]]; then
  v=$(.venv/bin/python -c 'import platform;print(platform.python_version())' 2>/dev/null) && check_python_version "repo .venv" "$v"
fi

section "Python packages (brotli / pillow / litellm / .pth hooks)"
for real in "${!seen_py[@]}"; do check_python_packages "$real"; done
[[ -x .venv/bin/python ]] && check_python_packages "$(readlink -f .venv/bin/python)"
for t in "$HOME/.local/share/uv/tools"/*/bin/python; do [[ -x "$t" ]] && check_python_packages "$t"; done
if compgen -G "/tmp/.pc_once_*" >/dev/null || [[ -e /tmp/remote_code_loader.lock ]]; then
  fail "LiteLLM 1.107.0 indicator present in /tmp (.pc_once_* or remote_code_loader.lock)"
else
  pass "no LiteLLM 1.107.0 indicators in /tmp"
fi

# ---------------------------------------------------------------------------
section "Node.js / npm"
found_node=0
if p=$(command -v node 2>/dev/null); then
  found_node=1
  check_node_version "PATH node ($(readlink -f "$p"))" "$(node -v 2>/dev/null)"
  command -v npm >/dev/null 2>&1 && info "npm: $(npm -v 2>/dev/null) (bundled with the Node above; updating Node updates npm)"
fi
for d in "$HOME/.nvm/versions/node"/*/; do
  [[ -d "$d" ]] || continue; found_node=1
  check_node_version "nvm $(basename "$d")" "$(basename "$d")"
done
for d in "$HOME/.local/share/fnm/node-versions"/*/ "$HOME/.volta/tools/image/node"/*/; do
  [[ -d "$d" ]] || continue; found_node=1
  check_node_version "version-manager $(basename "$d")" "$(basename "$d")"
done
if dpkg -s nodejs >/dev/null 2>&1; then
  found_node=1
  check_node_version "apt nodejs" "$(dpkg-query -W -f='${Version}' nodejs 2>/dev/null | sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/')"
fi
[[ "$found_node" -eq 0 ]] && info "node: not installed in WSL"
if command -v npm >/dev/null 2>&1; then
  globals=$(npm ls -g --depth=0 --parseable 2>/dev/null | sed -n '2,$p' | xargs -rn1 basename | tr '\n' ' ')
  [[ -n "$globals" ]] && info "npm globals: $globals"
fi

# ---------------------------------------------------------------------------
section "PHP"
if p=$(command -v php 2>/dev/null); then
  v=$(php -r 'echo PHP_VERSION;' 2>/dev/null)
  check_php_version "PATH php ($p)" "$v"
  if dpkg -s php8.3-cli >/dev/null 2>&1 || dpkg -s php8.3-common >/dev/null 2>&1; then
    pkgv=$(dpkg-query -W -f='${Version}' php8.3-common 2>/dev/null || dpkg-query -W -f='${Version}' php8.3-cli 2>/dev/null)
    if dpkg --compare-versions "$pkgv" ge "$UBUNTU_PHP83_FIX"; then pass "apt php8.3 $pkgv >= $UBUNTU_PHP83_FIX (USN-8948-1)"; else fail "apt php8.3 $pkgv < $UBUNTU_PHP83_FIX (USN-8948-1 not applied)"; fi
  fi
  if zgrep -qE 'CVE-2026-10961[89]' /usr/share/doc/php*/changelog.Debian.gz 2>/dev/null; then
    pass "php changelog mentions CVE-2026-109618/109619 (php2shell fix present)"
  else
    warn "php changelog does not mention CVE-2026-109618/109619 (non-apt build or unpatched)"
  fi
  for svc in php8.1-fpm php8.2-fpm php8.3-fpm php8.4-fpm php8.5-fpm apache2 nginx; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then warn "service $svc is active: web-facing PHP must be restarted after the update"; fi
  done
else
  info "php: not installed in WSL (php2shell affects mod_php / php-fpm; CLI-only hosts are low exposure)"
fi

# ---------------------------------------------------------------------------
section "Claude Code"
if p=$(command -v claude 2>/dev/null); then
  real=$(readlink -f "$p")
  info "claude: $(claude --version 2>/dev/null | head -1) at $real"
  case "$real" in
    *node_modules*) warn "claude is the npm install (runs on the Node above): update Node, then prefer the native installer (claude install)" ;;
    *) pass "claude is the native build (bundled runtime); run 'claude update' to pick up the latest" ;;
  esac
else
  info "claude: not installed in WSL"
fi

# ---------------------------------------------------------------------------
section "network exposure"
if command -v ss >/dev/null 2>&1; then
  exposed=$(ss -ltnH 2>/dev/null | awk '$4 ~ /^(0\.0\.0\.0|\*|\[::\]):/ {print $4}' | tr '\n' ' ')
  if [[ -n "$exposed" ]]; then warn "listening on all interfaces: $exposed (llama-swap/llama-server should bind 127.0.0.1)"; else pass "no service listens on 0.0.0.0/:: in WSL"; fi
  if ss -ltnH 2>/dev/null | grep -Eq ':(8080|8081)\b'; then info "local inference ports 8080/8081 in use (verify bind address above)"; fi
else
  info "ss not available; skip listener check"
fi

# ---------------------------------------------------------------------------
section "apt pending security updates"
if command -v apt >/dev/null 2>&1; then
  pend=$(apt list --upgradable 2>/dev/null | grep -iE '^(php|python3|nodejs|libnode|openssl|libssl|brotli|libbrotli|curl|libcurl|zlib)' | cut -d/ -f1 | tr '\n' ' ')
  if [[ -n "$pend" ]]; then fail "apt upgrades pending for: $pend (run sudo apt update && sudo apt upgrade)"; else pass "no pending apt upgrades for php/python/node/openssl/brotli/curl (apt cache may be stale: run sudo apt update first)"; fi
fi

# ---------------------------------------------------------------------------
if [[ "$windows" -eq 1 ]]; then
  section "Windows host (via cmd.exe)"
  cmd=/mnt/c/Windows/System32/cmd.exe
  if [[ -x "$cmd" ]]; then
    winq() { "$cmd" /c "$1" 2>/dev/null | tr -d '\r'; }
    wn=$(winq 'node -v')
    [[ -n "$wn" ]] && check_node_version "Windows node" "$wn" || info "Windows node: not on PATH"
    wp=$(winq 'python -c "import platform;print(platform.python_version())"')
    [[ -n "$wp" ]] && check_python_version "Windows python" "$wp" || info "Windows python: not on PATH"
    wpy=$(winq 'py -0p')
    [[ -n "$wpy" ]] && info "Windows py launcher: $(tr '\n' ';' <<<"$wpy")"
    wphp=$(winq 'php -r "echo PHP_VERSION;"')
    [[ -n "$wphp" ]] && check_php_version "Windows php" "$wphp" || info "Windows php: not on PATH"
    wc=$(winq 'claude --version')
    [[ -n "$wc" ]] && info "Windows claude: $wc" || info "Windows claude: not on PATH"
  else
    warn "cmd.exe not reachable at $cmd (WSL interop disabled?)"
  fi
fi

printf '\nSUMMARY failures=%d warnings=%d\n' "$failures" "$warnings"
[[ "$failures" -eq 0 ]]
