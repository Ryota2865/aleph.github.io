# 設計書: ALEPH ローカルUI（文学のためのエージェントハーネスの操作面）

状態: **設計のみ**（オーナー希望 2026-07-12/13。実装は後回しでよい。当面は Claude Code / CLI 経由で運用）。
実装時は本書を正典とし、乖離は本書を改訂してから施工する。担当想定: codex-implement / pi へ委任可能な
自己完結タスク（オーナーの8月方針とも一致）。

## 目的と非目的

**目的**: オーナー（人間）が、走行中の閉ループを**観察**し、要所で**判断**し、成果物を**読む**ための
単一の画面。ALEPH の自律性を損なわない——UI は制御盤ではなく**観測窓＋数少ない人間ゲートの受付**。

**非目的**: 作品の編集機能（人間が本文を直す UI は作らない。人間協働は L7 の設計に従う）、
プロンプトの対話的いじり（それは設計変更であり PLAN_CHANGELOG の仕事）、多ユーザー対応。

## 原則

1. **読み取りは自由、書き込みは既存 CLI の呼び出しに限定。** UI が直接 works/ や state/ を
   書き換えない。すべて `aleph new / run / publish / status` と scripts/ の既存入口を叩く。
   （新しい変更経路を作らない＝監査可能性の維持。）
2. **人間ゲートを一級市民に。** 現在人間の判断が必要な点は3つ: (a) 初回公開 ack
   （policies.publication.first_publish_ack）、(b) 予算 cap の引き上げ、(c) 実験腕の起動
   （--force-audience）。UI はこの3つを「保留中の判断」として明示的に提示する。
3. **依存最小。** llama-swap/実験と同居するローカル環境なので、重いフレームワークを避ける。
   推奨: Python 標準ライブラリ + 単一 HTML（既存の build_private_shelf.py / build_public_site.py
   と同じ流儀）。サーバが要る部分は `http.server` 派生 or FastAPI 単体まで。

## 画面（優先順）

### P1: ダッシュボード（読み取り専用。最初に作る）
- **走行状態**: works/*/checkpoint.json を列挙（作品ID・状態・step・宛先配合・最終更新時刻）。
  state/run_*.pid の生死判定つき。
- **予算3系統**: `aleph status` 相当（api の月/作品別、実残高はオーナー入力欄 or 設定値）。
- **直近の決定**: 全作品の decisions.jsonl 末尾 N 件をマージした時系列（layer 色分け）。
- **棚**: build_private_shelf.py の index への リンク（再生成ボタン可）。
- 実装ヒント: 静的生成（30秒ポーリング or 手動更新）で十分。まず
  `scripts/build_dashboard.py` → state/dashboard.html が最小。

### P2: 発火（書き込み・要確認ダイアログ）
- 「新しい作品を始める」= aleph new（hint 入力欄）→ run_work_detached.sh。
- 「実験腕で走る」= --force-audience のプリセット（LLM/人間/自分の純粋条件＋自由入力）。
- 「公開ゲート再評価」= aleph publish --work <id>（first_publish_ack の現在値を表示し、
  false なら「あなたの承認が必要」の説明つき）。
- すべて実行前に、消費見込み（作品別 usd_per_work と月残）を表示。

### P3: 読書室
- 棚（private shelf）と公開サイト（docs/）を iframe or リンクで統合。
- 作品ごとの「過程を読む」: criteria / decisions / reviews / trajectory を1画面に。

## データ源（すべて既存・追加スキーマなし）
works/<id>/{checkpoint.json, decisions.jsonl, seed.json, title.txt, reviews/trajectory.jsonl,
final/meta.json} / state/budget.json / state/run_*.{log,pid} / config/{budgets,policies,models}.yaml

## マイルストーン案
- **UI-1**: build_dashboard.py（静的HTML、読み取りのみ）。受入: 走行中/完了作品と予算と直近決定が
  1ページで見える。
- **UI-2**: 発火フォーム（ローカル http サーバ、上記 P2 の3操作、確認ダイアログ必須）。
  受入: UI からの操作が CLI 経由と同一の decisions/ログを残す。
- **UI-3**: 読書室統合。
- 各段で codex-implement に委任 → Claude が検証（pytest 緑 + 手動操作確認）→ codex-audit。
