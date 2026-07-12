# ALEPH 運用手順（日本語）

Claude Code / CLI から ALEPH を操作するための手順。設計正典は PLAN.md、変更履歴は
PLAN_CHANGELOG.md。作業規約は CLAUDE.md（`~/.claude/CLAUDE.md`）。

すべて WSL 内で実行する: `wsl.exe -d ubuntu -- bash -lc 'cd ~/llm_literature && …'`。
ローカル推論が要る操作は先に `bash scripts/start_local_stack.sh`（llama-swap 起動、冪等）。

## 批評を公開ページに追加する（file convention + 再ビルド）

公開サイトの「批評と応答」ページは、`reports/` の以下のファイルを**自動収集**して時系列で並べる:

- `reports/CRITIQUE_*.md` … 批評（例: チャット Fable 5 の批評）
- `reports/RESPONSE_*.md` … 設計者応答

**追加手順（コード変更不要）:**

1. 批評文を `reports/CRITIQUE_<件名>_<YYYYMMDD>.md` として保存（先頭に `# 見出し` を付ける。
   末尾に出典・ライセンス（CC-BY 推奨）を書く）。応答があれば `reports/RESPONSE_<件名>_<YYYYMMDD>.md`。
   - ファイル名に `YYYYMMDD` を含めると、その日付で時系列ソートされる。
2. 公開サイトを再生成: `uv run python scripts/build_public_site.py`
3. 確認 → コミット → プッシュ:
   `git add reports/ docs/ && git commit -m "Add critique: …" && git push origin main`

Claude Code へは「この批評を dialogue に追加してプッシュして」と頼めば上記を実行する
（将来 `/add-critique` スキル化も可能。今は上記の手動フローで足りる）。

**注意:** 公開は外向きの不可逆操作。批評は他者の会話ログを含むことがあるため、
公開前にオーナーの同意を取る（個人情報が無いこと・CC-BY で置けることを確認）。

## 作品の制作フロー

```bash
# 1. 探索（アトラス＋ニッチ。要 llama-server）。索引がある間はスキップ可
uv run python -m aleph.cli explore

# 2. 作品を新規作成（seed hint は任意。題は完成時に作品自身が選ぶので hint は着想メモでよい）
uv run python -m aleph.cli new --hint "着想…"

# 3. 閉ループを実行（チェックポイントから継続）。宛先を実験固定する場合は --force-audience
bash scripts/run_work_detached.sh w0005                       # 自律（バックグラウンド）
bash scripts/run_work_detached.sh w0005 --force-audience "LLM 0.6 / 自分 0.25 / 人間 0.15"

# 監視: works/w0005/decisions.jsonl の遷移と state/run_w0005.log
```

- **題は作品自身が選ぶ**（FINISH で著者に聞き `works/<id>/title.txt` に保存）。公開ページ・
  プライベート棚の双方がこれを読む。手で変える場合は title.txt を書き換える。
- 予算: `uv run python -m aleph.cli status`（api/harness/local の3系統）。cap は config/budgets.yaml。

## 公開する（初回は人間承認）

```bash
# 1. policies.yaml で承認: publication.first_publish_ack を true にする（初回のみ）
# 2. 公開ゲートを再評価（棚上げ済み作品も FINISH に戻して再判定）
uv run python -m aleph.cli publish --work w0005
# 3. 公開サイトを再生成してプッシュ
uv run python scripts/build_public_site.py
git add docs/ && git commit -m "Publish w0005" && git push origin main
```

- 公開作品は `final/text.md`（最高スコア版を自動選抜）＋関与モデルの役割名義（CC0）。
- GitHub Pages: Settings → Pages → `main` / `/docs`。URL は
  `https://ryota2865.github.io/aleph.github.io/`。

## サイト生成

- 公開（過程込み）: `uv run python scripts/build_public_site.py` → `docs/`（追跡・公開）。
- プライベート棚（SHELVE 含む全作品）: `uv run python scripts/build_private_shelf.py`
  → `state/site_private/`（git 管理外・非公開）。

## 実験を走らせる

- 志向アトラクタ計測: `uv run python scripts/exp_intent_attractor.py`（実験C）
- L1 の取り調べ: `uv run python scripts/exp_L1_interrogation.py`（実験D）
- いずれも `reports/EXP_*.md` に出力。work_id は `exp-*` で予算計上。

## 検証（変更のたびに）

```bash
uv run pytest -m 'not local' -q > /tmp/pt.txt 2>&1; rc=$?; tail -1 /tmp/pt.txt; echo EXIT=$rc
```

緑でなければコミットしない。設計不変条件（tests/test_design_invariants.py）と各マイルストーンの
受入テストは契約であり、弱める変更は監査で不合格（PLAN §12）。
