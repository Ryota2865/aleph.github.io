# 2026年10月 セキュリティアップデート対応計画（ローカル WSL / Windows 機）

作成日: 2026-10-24。対象: ALEPH を動かしているローカル機（Windows + WSL Ubuntu、RTX 3090）。
調査スクリプト: `bash scripts/security_audit.sh [--windows]`（読み取り専用、資格情報は出さない）。

この文書は運用文書であり、`PLAN.md` の設計正典を変更しない。

---

## 0. 結論（先に読む）

1. **Claude Code のクラウドセッションからはローカル機に到達できない。** 本セッションは
   Anthropic 管理のコンテナ（hostname `vm`, Ubuntu 24.04, root）で動いており、WSL も Windows も
   見えない。ローカル機の「現状調査」と「適用」は、ローカルで動くセッションで行う（§6）。
2. 優先順位は **PHP（公開 Web SAPI があれば即日）→ Node.js（Brotli RCE）→ Python ランタイムと
   パッケージ（Pillow / brotli / tarfile）→ サプライチェーン確認（LiteLLM 1.107.0）→ Claude Code 更新**。
3. この機の典型的な露出は小さい（PHP は CLI 用途が中心と推定、llama-swap は 127.0.0.1 バインド）。
   それでも Node.js と Python は「悪意ある入力を復号する側」が刺されるので、開発機でも更新する。
4. **参考: クラウド側コンテナ自体の実測**（`scripts/security_audit.sh` を本コンテナで実行）:
   PHP は Ubuntu パッチ済 (8.3.6-0ubuntu0.24.04.13)、Python 3.13.17 は最新、
   **Node v22.22.0 は未修正（< 22.23.4）**、システム Pillow 12.3.0 は未修正。これは Anthropic 側の
   イメージの問題で、利用者が直せるものではない（§6 の判断材料）。

---

## 1. 調査で確定した事実（一次情報と二次情報を区別）

| 対象 | 修正版 | 主な CVE / 深刻度 | 悪用状況 | 根拠 |
|---|---|---|---|---|
| **PHP** 8.2/8.3/8.4/8.5 | 8.2.35 / 8.3.36 / 8.4.27 / 8.5.12（2026-10-21）。Ubuntu 24.04 は php8.3 `8.3.6-0ubuntu0.24.04.13`（USN-8948-1） | CVE-2026-109618（multipart 解析中の OOM 処理不備→メモリ破壊）、CVE-2026-109619（致命的エラー後の次リクエストで UAF）。CVSS4 9.2、未認証 RCE。「php2shell」 | 公開前日に詳細が漏洩。watchTowr は探査・攻撃試行を観測。被害成功の公的確認はまだ無い | JPCERT at260033、IPA 注意喚起、Ubuntu USN-8948-1、Tanium/Tenable FAQ |
| 〃 影響範囲 | mod_php と php-fpm で RCE 検証済み。CLI SAPI への影響は資料に無し（未検証） | 8.1 以下は EOL で公式修正なし（ソースのバックポートのみ） | — | 同上 |
| **Node.js** 22/24/26 | 22.23.4 / 24.22.1 / 26.12.1（2026-10-21） | 10 件。High 4 件: CVE-2026-111497（Brotli デコーダ OOB write → RCE）、CVE-2026-105483 / 106069（TLS ホスト名検証バイパス）、CVE-2026-105482（dns.resolve の NUL 切り詰め）。eMudhra 中間 CA 失陥に伴う証明書ブロックも同梱 | 二次情報では野外悪用の報告なし | nodejs.org 公式ブログ（直接取得済） |
| 〃 EOL | Node 20 以下と 25 は修正なし。EOL 系列はセキュリティリリース時「常に影響あり」扱い | — | — | 同上 |
| **npm** | npm CLI 単独の 10 月アドバイザリは見つからなかった。npm は Node に同梱なので Node 更新で追従 | — | npm **レジストリ上のパッケージ**（toml-node 等）やマルウェアパッケージは別件 | GitHub Advisory DB |
| **Brotli（上流）** | 1.0.10 / 1.1.1 / 1.2.1 | CVE-2026-111497、CVSS4 9.2。Python `Brotli` ≤1.2.0 と `brotlicffi` 1.2.0.x も該当（requests/httpx/aiohttp が自動ロード）。修正: `Brotli>=1.2.1`, `brotlicffi>=1.2.1.0`。Bun 1.4.4 も修正 | OpenAI のエージェントが発見（防御側の AI 発見） | Aikido、GHSA-9v8h-qqgm-4m35 |
| **CPython** | 3.12.15 / 3.13.16（2026-10-01、ssl 入力検証 CVE-2026-19553、zipfile CVE-2026-15310、tarfile フィルタ CVE-2026-82049 / 87910）。3.13.17 / 3.14.9 / 3.15.1（2026-10-21、tarfile `tar_filter` パストラバーサル CVE-2026-114583、Medium） | 3.12 系への 114583 バックポート（3.12.16）は確認できず | 悪用報告なし | python.org ダウンロードページ、公式 changelog |
| **Pillow** | 13.0.0（2026-10-16） | CVE-2026-112900: EPS ファイル名が Ghostscript 引数として解釈される（引数注入→コマンド実行）。2.6.0〜12.3.0 が該当。13.0.0 は Python 3.10 サポート終了 | — | Debian tracker、GHSA-w889-685w-c8fh |
| **LiteLLM**（サプライチェーン） | 1.107.0 のみ悪性（PyPI で約 2 時間公開、2026-10-21）。全 wheel に資格情報窃取の `.pth` フックと RAT | 侵害済み判定: `litellm==1.107.0` を入れた/該当 Docker タグを pull した機。`/tmp/.pc_once_*`、`/tmp/remote_code_loader.lock`、site-packages 直下の不審 `.pth`（`cook.pth` 等） | **uninstall では駄目**。クリーン再構築と全資格情報ローテーション | LiteLLM 公式 incident、Datadog、Aikido |

ALEPH リポジトリ自体の依存（`uv.lock`）は httpx / numpy / scikit-learn / pyyaml で、**brotli・Pillow・litellm を含まない**。
ただしローカル機にはこれ以外の venv や `uv tool`、グローバル pip があり得るので、機械全体を調べる。

---

## 2. 「無検閲 LLM による脆弱性発見と自動攻撃」という前提の評価

AGENTS.md の方針に従い、観測・推論・解釈を分けて記す。

- **観測（出典あり）**: (a) CrowdStrike が 2026-10-21/22 に、AI エージェントを武器化した 4 つの未報告
  アクターを公表。健康・政府・SaaS が標的で、ある侵入では約 20 分で横展開と DC 資格情報取得。
  使われたのは Claude Code を使う監督/実行エージェント構成や、中国発オープンソースの
  ペンテスト用エージェント ARTEX。CrowdStrike は「4 者とも商用 AI の安全制御を回避した」と述べる。
  (b) Brotli の CVE-2026-111497 は OpenAI のエージェントが発見した（ベンダー側）。
  (c) PHP2Shell は漏洩後に探査が急増したが、発見者が LLM だという一次情報は無い。
- **推論**: 今回の一斉リリース（PHP・Node・Python・Brotli が同じ週）は、AI 支援の脆弱性発見が
  **防御側（ベンダー・研究者）で**加速していることと整合する。攻撃側の自動化は「無検閲モデル」よりも
  **商用モデルのガードレール回避＋オープンソースのエージェント枠組み**として観測されている。
- **解釈**: 前提は方向として正しいが「無検閲 LLM」は主語として狭い。実務上の含意は同じで、
  (1) 公開から悪用までの時間が短くなった、(2) 開発機でも「復号・解析する側」（Node の fetch/zlib、
  Python の tarfile/Pillow）が入口になる、(3) サプライチェーン（LiteLLM 型）は AI 開発者を狙う。
- **この機への意味**: ALEPH はローカル推論（llama-swap/llama-server）と GitHub Pages 生成が主で、
  公開 Web サービスは持たない。露出は「ダウンロードした物を開く」「ビルド時に依存を取る」系に集中する。

---

## 3. 現状把握（ローカルで実行）

WSL のリポジトリ直下で:

```bash
bash scripts/doctor.sh                  # 既存: WSL/gh/uv/GPU 診断
bash scripts/security_audit.sh --windows  # 新規: 版の棚卸し + 修正版との比較 + IoC
```

出力は PASS / WARN / FAIL / INFO。FAIL が 0 になるまで §4 を回す。
スクリプトが見るもの: PATH と uv・pyenv・`.venv` の Python、各 Python の brotli / pillow / litellm と
`.pth` フック、`/tmp` の LiteLLM 指標、PATH と nvm/fnm/volta/apt の Node、npm グローバル、PHP の
apt 版と changelog の CVE 記載、稼働中の php-fpm / apache2、Claude Code の導入方式、0.0.0.0 待受、
apt の保留更新、`--windows` で Windows 側の node / python / php / claude。

Windows 側を直接確認する場合（PowerShell）:

```powershell
node -v; npm -v; py -0p; python --version; php -v; claude --version
winget list --id OpenJS.NodeJS; winget list --id OpenJS.NodeJS.LTS; winget list --id Python.Python.3.13
```

---

## 4. 実施計画

原則: 1 系統ずつ、更新前に版を記録、更新後に `security_audit.sh` を再実行、最後に ALEPH の検証
（`uv run pytest -m 'not local' -q`）で回帰を見る。ローカル推論サーバ（port 8080/8081）が動いている間は
停止・差し替えをしない（AGENTS.md）。

### 4.1 PHP（露出があれば最優先、無ければ apt の通常更新で十分）

```bash
sudo apt update && sudo apt install --only-upgrade 'php8.3*' libapache2-mod-php8.3
zgrep -E 'CVE-2026-10961[89]' /usr/share/doc/php8.3-common/changelog.Debian.gz   # 記載があれば適用済
systemctl is-active php8.3-fpm apache2 nginx   # active なら restart
```

- Ubuntu は上流版番号 8.3.6 を保つので `php -v` では判定できない。changelog かパッケージ版
  `8.3.6-0ubuntu0.24.04.13` 以上で判定する。
- Windows 側に PHP があれば 8.3.36 / 8.4.27 / 8.5.12 の zip に差し替え。8.1 以下は削除。
- 公開 Web を持たず CLI 専用なら緊急性は低いが、同じ apt 更新で済むので一緒に当てる。

### 4.2 Node.js / npm（WSL と Windows の両側）

```bash
# nvm の場合（推奨: 24 LTS へ寄せる）
nvm install 24.22.1 && nvm alias default 24.22.1
nvm ls                      # 22.x は 22.23.4 以上に、20.x / 18.x は uninstall
nvm uninstall 20            # 例
# NodeSource/apt の場合
sudo apt update && sudo apt install --only-upgrade nodejs
# 共通
node -v && npm -v
npm ls -g --depth=0         # グローバル npm パッケージを新 Node 側へ再インストール
```

- Windows 側: `winget upgrade OpenJS.NodeJS.LTS` または nvm-windows で `nvm install 24.22.1 && nvm use 24.22.1`。
- npm CLI 単独の修正はないが、Node に同梱される npm は Node 更新で追従する。
  グローバルの `@anthropic-ai/claude-code` が npm 版なら、Node 更新後に §4.5 でネイティブ版へ移す。
- Brotli の修正は Node 本体に埋め込まれているため、npm パッケージ `brotli` を上げても意味がない。

### 4.3 Python ランタイム

- **apt の python3.12 / 3.13**: 版番号は固定（3.12.3 のまま）。`apt upgrade` で USN を取り込むのが対応。
- **uv 管理の Python**（`uv python list --only-installed`）: `uv python install 3.13.17`（または 3.14.9）、
  `uv python uninstall 3.13.16` 等で旧版を外す。リポジトリは `requires-python >= 3.12` なので 3.13 推奨。
  `.venv` を作り直す場合は `uv sync --all-extras` → `uv run pytest -m 'not local' -q`。
- **pyenv** があれば同様に 3.13.17 を入れて `pyenv global` を切り替える。
- Windows 側 Python は python.org の 3.13.17 インストーラ（3.12 系は 3.12.15 が最後のバイナリ無し
  ソースのみ、なので Windows は 3.13 系へ）。
- 3.12 系の tarfile CVE-2026-114583（Medium）はバックポート待ち。`tarfile.extractall(filter="data")` を
  信頼できない tar に使う処理が無いか確認し、あれば 3.13.17 で動かす。

### 4.4 Python パッケージとサプライチェーン

```bash
# 各 venv / uv tool で
uv pip install --upgrade 'Brotli>=1.2.1' 'brotlicffi>=1.2.1.0' 'pillow>=13.0.0'   # 入っている場合のみ
# LiteLLM 侵害の確認（security_audit.sh も見る）
pip show litellm 2>/dev/null | grep -i '^version'
ls -la /tmp/.pc_once_* /tmp/remote_code_loader.lock 2>/dev/null
find ~ -path '*site-packages/*.pth' -newer /etc/hostname 2>/dev/null   # 10/21 前後に増えた .pth
```

- `litellm==1.107.0` を入れた、または 10/21 の該当 Docker タグ（`v1.107.0`, `latest`, `main-latest`,
  `main-stable`）を pull した形跡があれば、**その環境はクリーン再構築し、到達可能だった全資格情報
  （GitHub トークン、API キー、SSH 鍵、クラウド鍵）をローテーション**する。uninstall では消えない。
- ALEPH は litellm を使わない（llama-swap に httpx で直接接続）。他プロジェクトの venv を疑う。
- 以後の予防: `uv lock` による固定（本リポジトリは既に `uv.lock`）、`pip install` 直打ちを避ける、
  新規依存は公開 48 時間後に採用する運用（供給網攻撃は数時間で取り下げられることが多い）。

### 4.5 Claude Code 本体

- WSL: `claude --version` と `command -v claude`。パスに `node_modules` が含まれれば npm 版
  （WSL の Node 上で動く）。Node を更新した上で、`claude install` でネイティブ版へ移行し、
  `npm uninstall -g @anthropic-ai/claude-code` で二重導入を解消。ネイティブ版は `claude update`。
- Windows 側も同様に `claude update`。
- Claude Code が読む `~/.claude`、`gh` 資格情報（`~/.config/gh`）は LiteLLM 型の窃取対象。§4.4 で
  侵害が疑われる場合はこれらもローテーション対象。

### 4.6 周辺（同じ日にまとめて）

- `sudo apt update && sudo apt full-upgrade`（OpenSSL / curl / zlib / libbrotli）。
- Windows Update と、Node・Python・PHP 以外の開発ツール（Git for Windows、Docker Desktop があれば）。
- llama-swap / llama-server のバインドが `127.0.0.1` のままか（`scripts/start_local_stack.sh` は
  127.0.0.1:8080 固定。`ss -ltn` で 0.0.0.0 待受が無いことを確認）。
- `gh auth status`（WSL）で不要なスコープ・古いトークンが無いか。

### 4.7 完了判定

1. `bash scripts/security_audit.sh --windows` が `failures=0`。
2. `uv run pytest -m 'not local' -q` が緑（ALEPH の回帰なし）。
3. 更新前後の版を `PROGRESS.md` ではなくこの文書の末尾「実施記録」に日付付きで追記（設計正典を汚さない）。

---

## 5. 想定工数とリスク

| 作業 | 目安 | リスク / ロールバック |
|---|---|---|
| PHP apt 更新 | 5 分 | 低。CLI 用途なら影響なし |
| Node 24.22.1 へ移行 | 20〜40 分 | グローバル npm パッケージの再導入。旧版は `nvm` に残して切り戻し可 |
| uv Python 3.13.17 + venv 再作成 | 10〜20 分 | `uv.lock` 固定で再現可能。pytest で確認 |
| パッケージ更新（brotli/pillow） | 5 分 | Pillow 13 は Py3.10 非対応（本機は無関係） |
| LiteLLM 侵害調査 | 10 分（該当なし）〜 数時間（該当あり: 再構築と鍵ローテ） | 該当時は最優先に昇格 |
| Claude Code ネイティブ化 | 10 分 | 設定は `~/.claude` に残る |

---

## 6. Claude Code 実行環境の提案（クラウドか、ローカルか）

**推奨: 用途で分ける。**

- **この機のメンテナンス（§3〜§4）はローカルで動くセッションで行う。** 選択肢:
  1. Claude Desktop アプリ（Windows）からローカルセッションを開く。
  2. WSL の端末でリポジトリ直下に入り `claude`（通常の対話）または `claude remote-control` を起動。
     後者は Claude Code アプリ（Web / モバイル）からそのセッションに接続できるので、今と同じ UI で
     「ローカル機に届くセッション」が得られる。
  いずれも **sudo が要る手順（apt）は Claude に実行させず、提示されたコマンドを自分で打つ** 運用を推奨。
  権限モードは既定（都度確認）。`bypassPermissions` は使わない。
- **リポジトリの通常作業（サイト生成・批評追加・PR）はクラウドのままで良い。** 隔離コンテナで
  動くため、ローカルの資格情報や GPU に触れないこと自体が安全側に働く。
  ただし §0 の通り、クラウドイメージの Node が 22.22.0 で未修正だった。クラウド側で `npm install` を
  伴う作業や外部 URL から取得した圧縮データを Node で扱う作業は、イメージが更新されるまで避けるか、
  ローカル側で行う。この点は Anthropic 側の更新待ちで、利用者側の設定で変えられない。
- **ローカル専用に寄せる判断をする場合**: 利点は到達性と GPU・llama-swap の直接操作。欠点は
  ホスト資格情報（`~/.config/gh`、SSH 鍵、`~/.claude`）がエージェントの到達範囲に入ること。
  その場合は AGENTS.md の WSL 規約（WSL ユーザで実行、Windows Git 状態と混ぜない、
  `gh auth git-credential` を使い `.git-credentials` を作らない）をそのまま守る。
- 本セッションから実行できたのは、スクリプト・計画の作成とクラウドコンテナ自身の棚卸しまで。
  ローカル機の実測値は §3 を実行して初めて得られる。

---

## 7. 継続運用（月次）

- `sudo apt update && apt list --upgradable` と `bash scripts/security_audit.sh` を月初に実行。
- Node は偶数 LTS（24 → 26）を追い、EOL 系列を残さない。`nvm ls` で確認。
- `uv self update`、`uv python list` で古いインタプリタを掃除。
- 購読: nodejs.org/en/blog/vulnerability、python.org security announce、php.net、JPCERT/CC 注意喚起。
- 修正版の番号（§1 表）が変わったら `scripts/security_audit.sh` 冒頭の定数を更新する。

---

## 8. 出典

一次情報:
- Node.js 公式: https://nodejs.org/en/blog/vulnerability/october-2026-security-releases
- Python 公式ダウンロード（3.13.17 / 3.14.9, 2026-10-21）: https://www.python.org/downloads/source/
- Python 3.13.16 リリース: https://www.python.org/downloads/release/python-31316/
- Python ブログ（3.10.22〜3.14.8, 10/1 セキュリティ修正）: https://blog.python.org/2026/10/python-31022-31117/
- PHP ニュース: https://www.php.net/archive/2026.php
- Ubuntu USN-8948-1: https://lists.ubuntu.com/archives/ubuntu-security-announce/2026-October/011433.html
- Ubuntu CVE-2026-109618: https://ubuntu.com/security/CVE-2026-109618
- JPCERT/CC 注意喚起 at260033: https://www.jpcert.or.jp/at/2026/at260033.html
- IPA 事前準備のお願い: https://www.ipa.go.jp/security/security-alert/2026/pre-alert20261021.html
- LiteLLM 公式インシデント: https://docs.litellm.ai/blog/security-incident-oct-21-2026
- Debian tracker CVE-2026-112900 (Pillow): https://security-tracker.debian.org/tracker/CVE-2026-112900
- CrowdStrike Agentic AI campaigns: https://www.crowdstrike.com/en-us/resources/reports/agentic-ai-attack-campaigns/
- CrowdStrike ARTEX: https://www.crowdstrike.com/en-us/blog/unknown-threat-actor-uses-artex-to-target-south-korean-finance/

二次情報（整合確認に使用）:
- watchTowr PHP2Shell: https://watchtowr.com/intelligence/php-remote-code-execution-php2shell/
- Tenable FAQ: https://www.tenable.com/blog/php2shell-cve-2026-109618-cve-2026-109619-frequently-asked-questions-about-critical-php-remote
- Tanium: https://www.tanium.com/blog/php2shell-responding-to-cve-2026-109618-and-cve-2026-109619
- piyolog: https://piyolog.hatenadiary.jp/entry/2026/10/21/174516
- Aikido (Brotli / Python packages): https://www.aikido.dev/blog/python-packages-vulnerable-node2shell-brotli-cve-2026-111497
- Datadog (LiteLLM): https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-docker/
- Aikido (LiteLLM): https://www.aikido.dev/blog/litellm-compromised-infostealer-rat
- Hacker News (Pillow): https://thehackernews.com/2026/10/critical-flaw-in-pythons-popular-pillow.html
- Astra (Node.js): https://www.getastra.com/blog/security-advisory/nodejs-october-2026-security-patches/
- Uravation (Node.js 日本語): https://uravation.com/media/nodejs-security-release-2026-10/
- CIO Dive (CrowdStrike): https://www.ciodive.com/news/agentic-ai-cyberattacks-harnesses-crowdstrike/833739/

本セッションのネットワークから php.net / jpcert.or.jp / blog.python.org / watchtowr.com は直接取得できず、
検索エンジン経由の要約で確認した。適用前にこれらの一次ページを自分で開くこと。

---

## 9. ローカル実測の監査所見（2026-10-24 05:11Z、ホスト DAIV、WSL2 Ubuntu 24.04.4）

オーナーが WSL で `bash scripts/security_audit.sh --windows` を実行した出力に基づく。

| 所見 | 判定 | 根拠と対応 |
|---|---|---|
| Node v24.13.0（nvm、PATH 既定） | **FAIL・最優先** | 24.22.1 未満。Brotli RCE と TLS 検証バイパスを含む 10 件が未修正。npm 11.6.2 と、グローバルの codex / opencode-ai / pi-coding-agent（いずれもコーディングエージェント）はこの Node 上で動く。`nvm install 24.22.1 --reinstall-packages-from=24.13.0` → `nvm alias default 24.22.1` → `nvm uninstall 24.13.0` |
| Python: PATH と `.venv` が distro の 3.12.3-1ubuntu0.17 | **WARN（要判断）** | 版番号は Ubuntu が固定するので数字では判定できない。クラウド側の同パッケージの changelog には 10/1 の CPython CVE（19553 / 15310 / 82049 / 87910）が**まだ無い**。つまり Ubuntu は 3.12 系へ未配信。本リポジトリは `requires-python >= 3.12` で、3.13.17 ではクラウドで 423 件が緑だったので、**`.venv` を uv 管理の 3.13.17 に移す**のが確実: `uv python install 3.13` → `rm -rf .venv && uv venv --python 3.13 && uv sync --extra dev` → `uv run pytest -m 'not local' -q` |
| uv 管理の Python 3.11.14 | WARN | 2026-10-01 の 3.11.17 未満。何が使っているか（`hermes` 等）を確認してから `uv python install 3.11` で更新、または不要なら `uv python uninstall 3.11.14` |
| uv 0.9.26 | INFO | 旧い（クラウドは 0.11.32）。`uv self update` |
| `zope.interface-6.1-nspkg.pth` | 誤検知 | Debian の名前空間パッケージ用フック。スクリプトを修正し許可リストに追加した |
| brotli / Pillow / litellm | 検出なし | 3.12 環境に該当パッケージが無い。LiteLLM 侵害指標も無し |
| PHP | 未導入 | WSL に PHP 無し。php2shell はこの機では対象外（Windows 側も PATH に無し） |
| Claude Code 2.1.211（ネイティブ） | INFO | ランタイム同梱なので Node の影響は受けない。`claude update` で最新へ |
| sshd が 0.0.0.0:22 / [::]:22 で待受 | **WARN（確認）** | llama-swap ではなく OpenSSH。WSL2 の既定 NAT では Windows ホストから到達でき、mirrored networking や portproxy を設定していれば LAN からも到達する。意図した運用なら `PasswordAuthentication no` と公開鍵のみを確認。不要なら `sudo systemctl disable --now ssh` |
| apt 保留: python3-apport / python3-apt / python3-distupgrade / python3-netplan / python3-problem-report | 誤判定（FAIL→INFO） | インタプリタではなく distro ツール。通常の `sudo apt update && sudo apt upgrade` で一緒に当てる。スクリプトの正規表現を修正した |
| Windows 側 node / python / php / claude | 検出なし | cmd.exe の PATH に無い。Windows 側の対象は無いと判断できる（winget 導入分があれば `winget list` で補完） |

結論: この機の実害に直結する未修正は **Node 24.13.0 の 1 点**。次に Python を 3.13.17 へ寄せる。
他は運用確認（sshd）と通常更新で足りる。

## 10. 実行の委任と監査の分担

実行部分は安価なモデル（別セッションまたは Codex）に委任し、監査を Claude（司令塔）が行う構成を採る。
AGENTS.md の「tests-green と形式的判定を分ける」「監査対象をコミットまたは出力で特定する」原則をそのまま使う。

### 10.1 実行ワーカーへの指示書（そのまま貼る）

```
あなたは ALEPH リポジトリ（~/llm_literature、WSL Ubuntu 24.04）のセキュリティ更新の実行担当です。
設計や方針は決めません。SECURITY_UPDATE_PLAN_2026-10.md §9 の順に実行し、証跡を残します。

制約:
- sudo が必要なコマンドは実行せず、コマンド文字列だけ提示してオーナーに打ってもらう。
- 稼働中の llama-swap / llama-server（port 8080/8081）を止めない・差し替えない。
- 資格情報（gh トークン、~/.ssh、~/.claude）を表示・コピーしない。
- PLAN.md、PLAN_CHANGELOG.md、tests/、config/、uv.lock を変更しない。リポジトリのファイルで書いてよいのは
  本計画書の「実施記録」節（§4.7 のとおり日付付きで追記）と state/ 配下の証跡だけ。
- 判断が要る分岐（3.11 を消すか、sshd を止めるか）は実行せず、確認事項として報告に書く。

手順:
0. 更新前の証跡: bash scripts/security_audit.sh --windows > state/security_before.txt; nvm ls; uv python list --only-installed; claude --version
1. Node: nvm install 24.22.1 --reinstall-packages-from=24.13.0 && nvm alias default 24.22.1 && nvm uninstall 24.13.0
   確認: node -v（v24.22.1）、npm -v、npm ls -g --depth=0（codex / opencode-ai / pi-coding-agent / corepack が残っている）
2. uv: uv self update
3. Python: uv python install 3.13 && rm -rf .venv && uv venv --python 3.13 && uv sync --extra dev
   確認: .venv/bin/python -c 'import platform;print(platform.python_version())'（3.13.17 以上）
4. 回帰: uv run pytest -m 'not local' -q 2>&1 | tail -3 を記録。main で既知の 2 件
   （test_repository_snapshot の README スナップショット、test_wiring_inventory の aleph.explore.vault 期限）以外が失敗したら作業を止めて報告。
5. Claude Code: claude update && claude --version
6. 提示のみ（オーナーが実行）: sudo apt update && sudo apt upgrade
   実行後にオーナーから結果をもらう。
7. 更新後の証跡: bash scripts/security_audit.sh --windows > state/security_after.txt
8. 報告: before/after の SUMMARY 行、各手順のコマンドと主要出力、確認事項（3.11 の用途、sshd の要否、
   /etc/ssh/sshd_config の PasswordAuthentication 値）を箇条書きで返す。推測で埋めない。
```

### 10.2 監査手順（Claude が行う）

監査対象は「ワーカーの報告」ではなく **`state/security_before.txt` / `state/security_after.txt` と
`uv run pytest` の生出力**。報告はそれらを読む手引きとして扱う。

1. after の SUMMARY が `failures=0`。残る WARN は §9 で予定したもの（3.11、sshd）に限ること。
2. Node: after に `v24.22.1`（またはそれ以上）が PATH と nvm の両方で PASS。npm グローバルの 4 件が残存。
3. Python: `.venv ->` の行が uv 管理の 3.13.17 以上で PASS。`uv.lock` に差分が無い（`git status --short` が .venv 以外空）。
4. pytest: `passed` 数が 423 以上、`failed` が既知の 2 件のみ。
5. 変更禁止領域（PLAN.md、PLAN_CHANGELOG.md、tests/、config/）に差分が無い。
6. 確認事項への回答が揃ったら、3.11 と sshd の判断をオーナーに返す（監査者は決めない）。
7. 合格なら §「実施記録」を更新してコミット。不合格なら差し戻し理由を証跡の行番号で示す。

### 10.3 監査結果（2026-10-24、監査者: Claude 司令塔）

監査対象: オーナー提出の `security_before.txt`（05:11Z）、`security_after.txt`（06:45Z / 06:59Z / 07:20Z の 3 回分）、
`security_after_ssh_disabled.txt`（07:20Z）、`security_pytest_pr3.txt`、`security_pr3_ssh.txt`。

| §10.2 条件 | 判定 | 証跡 |
|---|---|---|
| 1. after の SUMMARY が failures=0、残 WARN は予定内 | **合格** | 07:20Z: `failures=0 warnings=6`。残 WARN は distro python3.12（3 行）と 3.11 系（3 行）のみ。sshd の WARN は消えた |
| 2. Node が PATH と nvm の両方で v24.22.1 以上、npm グローバル残存 | **合格** | `PATH node … v24.22.1`、`nvm v24.22.1`、npm 11.19.1、グローバル pi-coding-agent / codex / corepack / npm / opencode-ai。v24.13.0 は nvm 一覧から消えている |
| 3. `.venv` が uv 管理の 3.13.17 以上、`uv.lock` に差分なし | **合格** | `repo .venv -> …/cpython-3.13.17-…/python3.13: 3.13.17`。`git status --short` は本計画書の変更と未追跡 `reports/patch_001.txt` のみで、`uv.lock` は無変更 |
| 4. pytest が 423 以上 passed、失敗は既知 2 件のみ | **合格** | `2 failed, 424 passed, 1 deselected`。失敗は test_repository_snapshot と test_wiring_inventory（期限 2026-09-30）で、更新前と同一 |
| 5. 禁止領域（PLAN.md、PLAN_CHANGELOG.md、tests/、config/）に差分なし | **合格** | 同上。禁止領域に差分なし。本計画書のローカル編集（+163/-6）は §4.7 に沿った実施記録の追記で、付録 A として取り込んだ |
| 6. 確認事項の回答 | **合格** | 3.11: Hermes（`~/.hermes/hermes-agent/venv`）が使用。3.11.17 へ更新済、3.11.14 は venv.old の予備として保持。sshd: `sshd -T` で `passwordauthentication yes` が判明し、オーナーが `systemctl disable --now ssh.socket ssh.service` を実行、`ss -ltn` で待受消失を確認 |

**総合: 合格（2026-10-24 確定）。** 6 条件すべてを証跡で閉じた。

訂正（2026-10-24）: 当初「ワーカーが指示書に反して本計画書を編集した」「Hermes の更新は指示書の範囲外」と
記したが、どちらも誤り。計画書の実施記録への追記は §4.7 が求めるものであり、矛盾していたのは §10.1 の
指示書（「リポジトリのファイルを変更しない」）のほうだった（§10.1 を修正済み）。Hermes と vLLM の更新は
オーナーが別途指示したもので、ワーカーのログ（付録 A）は各変更の前に明示許可を取った経過を記録している。
ワーカーの作業に手続き上の問題はなかった。

監査所見（追加）:

- Hermes（Python 3.11.14→3.11.17、Pillow 12.2.0→13.0.0、Hermes 本体 0.16.0 は据え置き）と vLLM 環境
  （Pillow 12.1.0→13.0.0）の更新はオーナー指示によるもので、GPU 推論の前後確認、`uv pip check`、画像処理
  テスト 265 件 PASS の証跡がある。ただし **venv.old、`/tmp/aleph-*-20261024/`、3.11.14 には更新前の
  Pillow 等が残る**。有効化しなければ無害だが、1〜2 週間の動作確認後に
  `rm -rf ~/.hermes/hermes-agent/venv.old && uv python uninstall 3.11.14` で片づける（`/tmp` は再起動で消える）。
- **Hermes リポジトリ側の変更 3 ファイル（`pyproject.toml`、`uv.lock`、`tools/lazy_deps.py`）が未コミット。**
  Hermes のリポジトリでコミットしないと、次の `uv sync` や checkout で Pillow 12.2.0 へ戻る。
- sshd は `passwordauthentication yes` だった。停止は妥当。将来 WSL への SSH が要るなら
  `PasswordAuthentication no` と `AuthenticationMethods publickey` を入れてから有効化する。
- Windows 側: オーナー提出の `winget list`（2026-10-24）に Node.js / Python / PHP は無い。10 月のランタイム
  修正は Windows 側には該当しない。閉じる。代わりに更新が溜まっているものがある: Docker Desktop 4.56.0
  （最新 4.96.3）、WSL 2.6.1（2.7.14）、Git 2.55.0.2（2.56.0.2）、Edge 155（156）、VC++ 再頒布パッケージ。
  Docker Desktop と WSL はセキュリティ修正を含む系統なので `winget upgrade Docker.DockerDesktop` と
  `wsl --update` を先に、残りは `winget upgrade --all` で当てる。
- distro python3.12（3.12.3-1ubuntu0.17）は 10/1 の CPython CVE 未配信のまま。PATH の `python3` が
  これを指すので、Ubuntu の USN が出たら `apt upgrade` で追従する。本リポジトリは `.venv` の 3.13.17 で動くので影響しない。
- スクリプト側: 3.11.17 以上を PASS にする判定を追加した（Hermes が 3.11 系を使い続けるため）。

### 10.4 ローカル編集の回収（完了）

ワーカーの実施記録はローカルで `git diff` としてパッチ化され、司令塔が付録 A として原文のまま取り込んだ。
以後、ワーカーは実施記録を直接コミットしてよい（§10.1 の修正後の指示書に従う）。

## 実施記録

| 日付 | 対象 | 更新前 | 更新後 | 確認方法 |
|---|---|---|---|---|
| 2026-10-24 | Node.js (nvm, WSL) | v24.13.0 / npm 11.6.2 | v24.22.1 / npm 11.19.1、v24.13.0 削除 | security_after.txt 07:20Z |
| 2026-10-24 | Python `.venv` | distro 3.12.3-1ubuntu0.17 | uv 管理 3.13.17 | security_after.txt、pytest 424 passed |
| 2026-10-24 | uv-managed Python 3.11（Hermes） | 3.11.14 | 3.11.17（3.11.14 は venv.old 用に保持） | security_after.txt |
| 2026-10-24 | Hermes venv Pillow | （未記録） | 13.0.0 | ワーカー報告（uv pip check 互換 OK） |
| 2026-10-24 | uv | 0.9.26 | 0.13.5 | security_after.txt |
| 2026-10-24 | Claude Code (native, WSL) | 2.1.211 | 2.1.310 | security_after.txt |
| 2026-10-24 | Ubuntu apt | 24.04.4、python3-* 5 件保留 | 24.04.5、保留なし | security_after.txt |
| 2026-10-24 | PHP | 未導入 | 対象外 | security_audit.sh |
| 2026-10-24 | sshd 0.0.0.0:22 | 待受中、passwordauthentication yes | ssh.socket / ssh.service 無効化、待受なし | security_pr3_ssh.txt、ss -ltn |
| 2026-10-24 | vLLM venv Pillow（オーナー指示） | 12.1.0 | 13.0.0 | ワーカー報告（uv pip check 145 件互換） |
| 2026-10-24 | Hermes repo（pyproject / uv.lock / tools/lazy_deps.py） | Pillow 12.2.0 固定 | 13.0.0 へ同期、コミット済み（オーナー報告） | Hermes 側 `git log` |
| 2026-10-24 | Windows（winget list） | — | Node / Python / PHP なし | WingetList.txt |
| 2026-10-24 | Windows Docker Desktop | 4.56.0 | 4.96.3 | WingetList_002.txt |
| 2026-10-24 | Windows WSL | 2.6.1 | 3.0.3（メジャー更新） | WingetList_002.txt |
| 2026-10-24 | WSL 3.0.3 後の推論スタック確認 | — | doctor.sh 全 PASS（RTX 3090 可視）、start_local_stack → verify_local_stack、`test_local_swap PASSED` | オーナー報告 |
| 2026-10-24 | Windows Git / VC++ 再頒布 / Terminal / その他 | Git 2.55.0.2 ほか | Git 2.56.0.2、VC++ 14.51、Terminal 1.25 ほか 9 件 | WingetList_002.txt |
| 2026-10-24 | Windows Edge | 155.0.4283.62 | 156 へ更新済み（Edge 自身の更新機能。winget は導入方式の違いでブロック） | オーナー報告 |
| 2026-10-24 | リポジトリ差分（uv.lock・禁止領域） | — | 差分なし（本計画書の実施記録追記と未追跡 reports/patch_001.txt のみ） | `git status --short && git diff --stat` |

---

## 付録 A: ワーカー実施ログ（2026-10-24、原文）

実行ワーカー（別セッション）が本計画書の実施記録に追記した経過記録。ローカルの `git diff` から司令塔が
原文のまま移した。時系列は上から下。監査（§10.3）はこのログではなく生出力（state/）を対象とした。

### 2026-10-24 ローカル適用（途中経過）

入力はオーナーが実機で実行した `reports/patch_001.txt`。この入力ファイルは一時資料で、
オーナーが後日削除予定。本記録時点では保持している。

| 対象 | 更新前 | 更新後 | 確認方法 |
|---|---|---|---|
| WSL nvm Node | 24.13.0 / npm 11.6.2 | 24.22.1 / npm 11.19.1 | 公式配布checksum一致、default alias変更、主要CLI版表示 |
| uv | 0.9.26 | 0.13.5 | `uv self update` / `uv --version` |
| uv Python | 3.11.14 | 3.11.17と3.13.17を追加 | `uv python list --only-installed`。旧3.11.14は保持 |
| ALEPH `.venv` | distro Python 3.12.3 | managed Python 3.13.17 | `uv sync --frozen --all-extras --python 3.13.17`、19依存の整合性確認 |
| Claude Code native | 2.1.211 | 2.1.310 | `claude update` / `claude --version` |

- ALEPH更新前venvは `/tmp/aleph-security-20261024/venv-before` に退避した。
  `/tmp` は永続バックアップではない。`uv.lock` と設計正典は変更していない。
- 非localテストは更新前・更新後とも **424 passed, 2 failed, 1 deselected**。
  失敗はREADME snapshot不一致と、`aleph.explore.vault` の配線猶予の2026-09-30失効。
  更新による追加失敗は観測していないが、全件greenの完了条件は未達。
- npmグローバルは既存版を移行し、Codex 0.142.5、Pi 0.80.3、OpenCode 1.14.29の版表示を確認。
  corepackは移行時に0.34.5から0.36.0へ変更。npmは一部install script未許可の警告を出した。
  各CLIの実タスク・モデル呼出しは未検証。
- Ubuntuのzope namespace `.pth` は内容を静的確認し、`dpkg -V python3-zope.interface` は差分なし。
  ALEPH、uv tool、system、user-local、Hermesと列挙した他venvの対象パッケージmetadataを
  Pythonのsite読込を無効にして確認。LiteLLMの該当metadataと既知`/tmp`指標は見つからなかった。
  過去の導入履歴・Docker・機械全体の非侵害を証明するものではない。
- **保留**: apt更新はsudoパスワードが必要でオーナーへ実行依頼済み。
  旧Node削除は自動承認レビューが拒否したため保持し、明示許可を確認中。
- **追加発見・未変更**: HermesはPython 3.11.14とPillow 12.2.0を使用し、
  `pyproject.toml`でもPillow 12.2.0を固定。依存契約を含む対応の許可を確認中。
  vLLM `models/vllm/gptoss/.venv` はPillow 12.1.0を使用。13.0.0へのdry-runは
  Pillowだけの変更だったが、別プロジェクト変更として自動承認レビューが拒否し、許可確認中。
- Windows PATH上にNode/PHP/Claude/pyは見つからず、pythonはWindowsAppsのaliasのみ。
  アプリ同梱ランタイムやWindows全体の更新状況は未検証。
- 推論サーバー、SSH待受、GPU設定は変更していない。更新後の全体監査と完了判定は保留。

### 2026-10-24 追加適用・確認結果（上記途中経過の更新）

- オーナーが `sudo apt update && sudo apt upgrade` を実行完了。
  実機で `dpkg --audit` は出力なし、監査対象パッケージの保留更新なしを確認した。
  Python補助パッケージは更新済み。OS表示はUbuntu 24.04.5 LTS、CUDA toolkitは13.4.3-1。
  `cloud-init` と `tmux` は更新候補として残っている（事前simulationでは段階配信対象）。
  `/var/run/reboot-required` は存在しなかった。OS Pythonは引き続き
  3.12.3-1ubuntu0.17であり、全CVEのバックポート適用を個別に証明したものではない。
- オーナーの明示許可後、旧Node 24.13.0を削除。既定Nodeは24.22.1。
- オーナーの明示許可後、vLLM環境のPillowのみ12.1.0から13.0.0へ更新。
  `uv pip check` は145パッケージ互換、site読込無効でのPNG書込・読込もPASS。
  vLLMモデルの推論動作は試していない。
- オーナー決定: **Hermesは別作業**。Pillow 12.2.0とPython 3.11.14を保持する。
  旧Python 3.11.14はHermes venvの参照先なので削除しない。
- 更新後の `bash scripts/security_audit.sh --windows` は
  **failures=0 warnings=8**（2026-10-24 06:27 UTC / 15:27 JST）。
  WARNにはdistro Pythonのバックポート判定保留、3.11系の一般警告、旧3.11.14、
  zope namespace `.pth`、SSHの全interface待受が含まれる。
- このスクリプトはHermesやvLLMのvenvを網羅しない。したがってFAIL 0件でも機械全体の
  修正完了・非侵害を意味しない。Hermes残件、Windowsアプリ同梱ランタイム未調査、
  更新前後で同じ非localテスト2件失敗は残る。セキュリティスクリプト自体は未変更。
- `reports/patch_001.txt` は削除せず保持。設計・コード・lockは未変更、commit/pushは未実施。

### 2026-10-24 Hermes限定セキュリティ更新（追加承認後）

オーナーの追加承認により、Hermes本体0.16.0は据え置き、実行Pythonを3.11.14から
3.11.17へ、Pillowを12.2.0から13.0.0へ変更した。Hermes側の`pyproject.toml`と
`uv.lock`を整合させ、lock内のパッケージ版変更はPillowのみと確認した。
新uvによるlock形式revisionは3から5へ変わった。

- 画像処理の実検証で`tools/lazy_deps.py`の旧Pillow固定が自動ダウングレードを起こすことを
  確認したため、同箇所も13.0.0へ同期した。更新後テストを通して旧版へ戻らないことを確認。
- 既存環境は`~/.hermes/hermes-agent/venv.old`へ退避し、さらに
  `/tmp/aleph-hermes-security-20261024/venv-before`にも保存した。
  旧Python/Pillowは退避物として残る。通常CLIが利用する`venv`は修正版。
- 更新前のテストは宣言済み`pytest-timeout==2.4.0`の欠落で起動不可だった。
  同テスト依存を補った更新前環境で画像関連168件PASS。
  更新後は公式`scripts/run_tests.sh`による画像処理・遅延依存6ファイル、
  **265 tests passed, 0 failed**。Hermes全テストsuiteを実行したものではない。
- 更新後の206インストール済みパッケージは整合性チェックPASS。
  更新前環境（テスト依存補完後）との版比較ではPillowのみが変わった。
- RTX 3090、空きport 8081を確認し、既存CUDA 12.9版llama-serverと
  Qwen3.6-27B（ctx=64000、KV=q4_0）で更新前後に短い推論を実行し、ともに`OK.`を返した。
  更新後Hermes Python/OpenAI SDK経由でも成功。自分で起動したサーバーのみ終了した。
  長時間run・Gemma profileは未検証。CUDA、llama.cpp、モデル設定は変更していない。
- ALEPHの最終`uv run --frozen pytest -m 'not local' -q`は
  **2 failed, 424 passed, 1 deselected in 8.76s**。更新前からのREADME snapshot不一致と
  配線猶予失効の2件がそのまま残り、今回の追加失敗はない。
- Hermes側変更は`pyproject.toml`、`uv.lock`、`tools/lazy_deps.py`の3ファイル。
  両repositoryのdiff checkは正常。commit/pushはしていない。

### 2026-10-24 PR #3追加指示の統合・再検証

- PR最新commit `e09418478b17c5e937cb34d484d0aba1664e843b`へfast-forwardし、
  §9・§10と監査判定修正を取り込んだ。ローカル実施記録86行を欠落なく保持した。
  取込前の文書・before/after証跡は`state/security_pr3_integration/`へ退避した。
  上表の未実施欄は既存の実測記録に合わせて更新した。§9は初回実測時点の評価であり、
  後から判明したHermes/vLLMのPillowやWindows同梱runtimeの未確認を否定するものではない。
- 新版スクリプトの実機再監査は **failures=0 warnings=7**。
  生出力は`state/security_after_pr3.txt`。旧8件からの減少1件はnamespace `.pth`の
  許可リスト変更による。残るWARNはdistro Pythonの判定保留3件、3.11系3件、SSH待受1件。
  distro PythonもWARNに残るので、§10.2の「3.11とsshdに限る」を厳密には満たさない。
  changelogのCVE語彙だけで未修正・修正済みを断定せず、USN/個別バックポートの確認は残件。
- NodeはPATH/nvm双方PASS、ALEPH `.venv ->` は3.13.17でPASS。
  npmのcodex / opencode-ai / pi-coding-agent / corepackは残存。
- pytestを再実行して生出力を`state/security_pytest_pr3.txt`へ保存。
  **2 failed, 424 passed, 1 deselected in 8.70s**。
  失敗はREADME snapshot不一致と配線猶予失効の既知2件のみ。
- `sshd -T -C user=ryota_tanaka,host=localhost,addr=127.0.0.1`は一般ユーザーで
  host keyへ到達できず失敗し、`sudo -n`もパスワードが必要だった。
  `PasswordAuthentication`の実効値は未確認。読める設定の明示行は
  `Include /etc/ssh/sshd_config.d/*.conf`と`KbdInteractiveAuthentication no`。
  生結果は`state/security_pr3_ssh.txt`。オーナーへsudoによる設定確認のみを依頼した。
  SSHの停止・認証方式変更は行っていない。
- `PLAN.md`、`PLAN_CHANGELOG.md`、`tests/`、`config/`、ALEPHの`uv.lock`に差分なし。
  shell構文・diff checkは正常。追加のruntime更新、正式監査PASS判定、新規commit/pushはしていない。

### 2026-10-24 SSH実効設定の追加確認（オーナー提供）

オーナーのsudo実行は最初に`Missing privilege separation directory: /run/sshd`で停止。
実行時ディレクトリを作成する手順を案内し、その後オーナーから以下の実効設定を受領した。
`user=ryota_tanaka,host=localhost,addr=127.0.0.1`の確認結果として記録する。

```text
permitrootlogin without-password
pubkeyauthentication yes
passwordauthentication yes
kbdinteractiveauthentication no
authenticationmethods any
```

この条件ではパスワード認証が有効であり、§9の公開鍵のみという確認条件は未達。
rootの`without-password`はパスワード認証を禁止する指定で、一般ユーザーの
`passwordauthentication yes`を無効にはしない。別接続元やrootユーザーのMatch条件、
稼働daemonへの反映状況は別途確認が必要。原文を`state/security_pr3_ssh.txt`と
`state/security_after.txt`へ追記し、以前の「実効値未確認」はこの条件に限り解消した。
SSHの用途と鍵ログインの可否をオーナーへ確認し、停止・認証方式変更はまだ行っていない。

### 2026-10-24 SSH停止のオーナー承認・実行待ち

オーナーはSSHを現在使用しておらず、削除してよいと明示承認した。
SSHクライアントを保持し、SSHサーバーのsocket/service停止と自動起動無効化で対応する。
読み取り確認では`ssh.service`はinactive/disabled、`ssh.socket`はactive/enabledで、
IPv4/IPv6の全interfaceで22番を待ち受けていた。serviceだけでは待受を解消できない。
`sudo -n true`はパスワード必須で失敗したため、停止は未実施。
オーナーへ`sudo systemctl disable --now ssh.socket ssh.service`を依頼する。

### 2026-10-24 SSHサーバー停止・最終確認

オーナーが`sudo systemctl disable --now ssh.socket ssh.service`を実行。
途中にtriggering unitの警告が出たが、独立した実機確認では`ssh.service`・`ssh.socket`とも
**inactive / disabled**。`ss -ltn 'sport = :22'`は見出しのみで、22番待受はない。
SSHクライアントとサーバーパッケージは保持し、サーバー停止と自動起動無効化で対応した。
設定値のPasswordAuthenticationは変更していない。SSHの用途判断・停止に関する残件は解消。

停止後の標準監査は **failures=0 warnings=6**。
生出力は`state/security_after_ssh_disabled.txt`、状態確認は`state/security_pr3_ssh.txt`。
`state/security_after.txt`へも過去の出力を保持して追記した。
残る警告はdistro Python判定保留と3.11系であり、旧退避環境・Windows同梱runtimeの
未確認と既知pytest失敗2件も、これまでどおり残件として扱う。
SSH停止に伴うコード変更はないためpytestは再実行していない。commit/pushは未実施。
