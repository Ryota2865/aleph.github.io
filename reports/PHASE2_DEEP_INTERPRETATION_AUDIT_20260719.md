# ALEPH Phase 2 Independent Audit

**監査日時**: 2026-07-19T01:37Z (UTC)
**監査者**: Claude Code (Opus 4.8) — 施工者(Codex)とは別担当
**対象 git 状態**: `main` @ `09f77c9` (worktree にコミット前の Phase 2 変更)
- 新規: `aleph/core/model_output.py`, `aleph/core/work_snapshot.py`, `aleph/core/repository_snapshot.py`, `scripts/audit_repository_snapshot.py`, `designs/phase2-deep-interpretation.md`, および3件の新規テスト
- 変更: CLI・publish・dashboard・public site・全 ModelOutput 移行モジュール・README・PLAN_CHANGELOG・PROGRESS・実行計画
- `git diff --check`: クリーン / 独立 pytest: **283 passed, 1 deselected** / `doctor.sh`: failures=0

---

## Formal Verdict

**FAIL**（1件の P2 のみ。Phase 2 の設計・移行・fail-closed 性はほぼ全面的に成立しているが、`ModelOutput` の duplicate-key 処理に外向きゲートへ波及しうる fail-open のコーナーが1つ残る。修正は約2行・局所的。）

PLAN の意味・受入条件・状態機械・予算規則・公開上限の変更は**検出されなかった**（この点は完全に遵守）。

---

## Findings

### P2-1 — duplicate-key 応答がネスト/後続オブジェクトへ退避して暗黙の成功になる

- **file:line**: `aleph/core/model_output.py:79-88`（`_json_values` の `except _DuplicateKey: … index += 1; continue`）+ `:159-172`（候補採用）
- **observed evidence**（/tmp 上で実行、リポジトリ非変更）:
  ```
  入力: {"publish": true, "publish": false, "reason": "x",
         "extra": {"publish": false, "reason": "y"}}
  schema = {"publish": bool, "reason": str}
  → ok=True  value={'publish': False, 'reason': 'y'}
     warnings=('duplicate JSON key: publish',)  fragment={"publish": false, "reason": "y"}
  ```
  外側オブジェクトは gate が読む当の `publish` フィールドで矛盾（duplicate key）しているのに、スキャナが `_DuplicateKey` 発生後に `index += 1` で**同じオブジェクトの内部を再走査**し、schema に一致するネストオブジェクトを唯一の候補として `ok=True` で採用する。単純な duplicate-key ケース（tracer bullet test #2）は正しく拒否されるが、救済可能なサブ/後続オブジェクトが1つある場合に限りこの穴が開く。
- **impact**: fail-closed 境界の中で、**構造的矛盾（parse failure相当）が暗黙の成功に化ける**。これは設計 §3 failure model の「duplicate key を拒否」と、監査観点「parse/schema failure が暗黙の成功にならないか」に直接反する。波及先は `publish`（`meta/publication_gate._ask_publish_intent`）・技術床（`{"pass":bool,...}`）・家風分類など strict schema の外向き経路。返り値の warning は "duplicate JSON key" のみで低シグナルであり、`.ok` を見る consumer は矛盾に気づけない（監査可能性の劣化）。発火確率は低い（duplicate key 自体が稀 + schema 一致のネスト対が必要）が、当モジュールの存在意義がまさにこの種の異常出力を安全に扱うことにあるため、コーナーであっても fail-closed が破れている点を重く見る。
- **required correction**（最小）: duplicate-key 検出を parse 全体の毒とみなす。`fail_closed=True` かつ scan 中に `_DuplicateKey` を1件でも観測したら、候補救済に進まず not-ok（`value=None`）を返す。あるいは矛盾オブジェクトの span 全体を消費してから走査を継続し、内部の再走査による救済を禁じる。RED は上記入力＋公開 schema で `ok is False` を期待する回帰テストとして追加する。

（P0/P1 なし。P3 は下記。）

### P3-1 — 探索系 caller の multi-JSON 挙動変化（yield 低下の可能性）
`explore/niche`・`compose/generate`・`critique/*`・`materia/*` は旧 `_extract_json_object`（先頭の1個を採用）から `parse_model_output(schema=dict/list)` の **fail_closed=True 既定**へ移行した。冗長なモデルが理由文＋最終JSONのように複数オブジェクトを返すと、旧実装は先頭を採ったが新実装は None を返す。安全側だが、設計 §3 が「探索的 caller は `fail_closed=False` 可」と明記する箇所で既定のままのため、実走行で niche/構成の歩留まりが下がりうる。`file`: `aleph/explore/niche.py:126,199`, `aleph/compose/generate.py:124`。非阻害。

### P3-2 — 自己申告テスト数の軽微な陳腐化
`PLAN_CHANGELOG.md` 0.7.20-9 / `PROGRESS.md` / `designs/next-designer-execution-plan.md` が「282 passed」と記録するが、現在の独立実行は **283 passed**。過小申告であり過大表現ではない。

### P3-3 — README 日英の非対称
`README.en.md:19` は "the first two phases … Phase 2 awaits an independent milestone audit" と phase 状態を明示するが、`README.md` の対応節は M0–M8 のみで Phase 1/2 に言及しない。矛盾ではないが情報量が非対称。生成マーカー内（snapshot 由来）は日英一致。

---

## Acceptance Matrix

| Phase 2 要件 | 判定 | 根拠 |
|---|---|---|
| ModelOutput: fail-closed な単一境界が存在 | PASS | `parse_model_output` が唯一の seam。全 caller から `_extract_json*` を削除（`rg _extract_json` = 0件） |
| prose/fence/fragment の扱い・JSON 欠落・複数値・duplicate | **PARTIAL** | 欠落=not-ok、複数=fail-closed 拒否、単純 duplicate=拒否 ✔。ただし **P2-1**（duplicate 後のネスト救済） |
| 型混同（bool/"false"、int/数値文字列、float/bool、非有限数、enum bool≠int） | PASS | /tmp failure injection 17ケース全通過（NaN/Infinity/1/"3"/enum 型一致 いずれも拒否） |
| object/list/enum/StringMap の strict schema | PASS | `_schema_error` 検証・実測。StringMap は空・未知キーを拒否 |
| parse/schema failure が暗黙成功にならない | **FAIL** | **P2-1**: duplicate-key で暗黙成功が発生 |
| run_w0008 tech floor・house-style が fail-closed | PASS | not-ok → `pass=False`(hold)。`{"pass":"false"}` 拒否をテスト＆実測で確認 |
| WorkSnapshot: authoritative read model | PASS | 全 consumer が `WorkReader.snapshot()` 経由 |
| modern replay が checkpoint より優先 | PASS | modern分岐で `strict_replay` を一次像に採用 |
| replay 失敗が checkpoint fallback で隠蔽されない | PASS | 注入検証: broken modern → lifecycle None / publication UNKNOWN / not published（checkpoint の PUBLISH 主張は無視） |
| replay↔checkpoint 不一致が明示 warning | PASS | 実データ w0001–w0008 で "checkpoint … differs from … replay" 等を可視化 |
| legacy 互換・不正/欠落/破損が成功と解されない | PASS | 破損 checkpoint → UNKNOWN/not published |
| best/selected/adopted と latest の分離 | PASS | `test_selected_published_draft_is_distinct_from_latest`＋実データ（w0005 best=2, latest 分離） |
| published surface が採用本文を参照 | PASS | PUBLISH 時 `final/text.md` を採用、差異は warning（w0005 実例） |
| publication metadata の stale/矛盾が可視化 | PASS | 注入: checkpoint 改竄の publication_disposition は modern で採られず SHELVE 維持＋replay不一致warning |
| RepositorySnapshot が works/budget/exp/PID/audit/deadline を集約 | PASS | audit report: works 8 / published 5 / experiments 2 / warnings 20 |
| malformed/missing が監査上不可視にならない | PASS | 20警告を report/JSON に列挙、`test_audit_report_keeps_snapshot_warnings_visible` |
| deadline review が状態を自動変更しない | PASS | `_deadlines` は情報のみ、`publish.max_per_month==999` で 2026-08-01 を返すだけ・値不変 |
| 公開上限/予算規則を再定義しない | PASS | config の `publish.max_per_month` をそのまま読む |
| 同一 fixture で site/dashboard/CLI が state・title・採用稿一致 | PASS | 合成 fixture テスト＋**実データ5公開作で title/state 完全一致**を独立確認 |
| consumer が生ファイルを独自解釈しない | PASS | status/site/archive/dashboard/CLI/README すべて snapshot 経由。process ページの生 decision/review 表示は設計上許容 |
| README 生成マーカーが現在値と一致（日英） | PASS | `test_checked_in_readme_snapshot_sections_match_current_repository` 通過、両言語で 8作/5公開/13 audit |
| Phase 1 PASS と Phase 2 現況の区別 | PASS | 実行計画・EN README とも Phase1=正式PASS / Phase2=独立監査待ち |

---

## Independent Verification

実行コマンドと結果（すべて WSL・read-only。失敗注入は /tmp のみ）:

1. `bash scripts/doctor.sh` → `SUMMARY failures=0 warnings=1`（worktree 変更の警告のみ）
2. `TMPDIR=/tmp uv run pytest -q -m 'not local' --capture=no` → **283 passed, 1 deselected**（handoff の282から+1、いずれも過小申告方向）
3. `git diff --check` → 空（whitespace 問題なし）
4. `rg '_extract_json|raw_decode|bool\(parsed\.get|json\.loads' aleph scripts` → `_extract_json`/`bool(parsed.get` は**0件**。`raw_decode` は `model_output.py` の境界内1件のみ。`json.loads` 残存は全て正当なローカルファイル読取（seed/decisions/trajectory/meta/budget/calls/atlas）で、LLM 出力境界の迂回ではないと分類
5. `scripts/audit_repository_snapshot.py --format report` → works 8 / published 5 / experiments 2 / warnings 20（legacy 不連続・w0005 手修正 final・w0008 古い colophon を隠さず列挙）
6. 実 works の modern/legacy 判定 → **8作すべて legacy**（w0008 も既存 checkpoint 保持のため `initialize` 未実行）。modern strict-replay 経路は実データ未使用でテスト/合成 fixture のみで担保

追加した failure injection（/tmp、リポジトリ非変更）と結果:
- **ModelOutput 境界17ケース**: NaN/Infinity 拒否、int↔bool・float↔bool・数値文字列・enum bool≠int・未知 StringMap キー・空 StringMap・複数値・ネスト duplicate・list 要素型 — **全通過**
- **WorkSnapshot fail-closed 3シナリオ**: (A) 非連続 modern event で replay 失敗 → UNKNOWN/not published（checkpoint の PUBLISH 無視）✔ (B) checkpoint の publication_disposition 改竄 → modern SHELVE は昇格せず ✔ (C) 破損 legacy checkpoint → UNKNOWN/not published ✔
- **クロス consumer 実データ整合**: 5公開作すべてで site/dashboard/CLI の title・state 一致 ✔
- **duplicate-key 救済**（P2-1）: 上記シナリオで `ok=True` に矛盾値が漏れることを再現 ✗

---

## Design Assessment

- **狭い interface・深い実装**: 3モジュールとも `parse_model_output` / `WorkReader.snapshot` / `RepositoryReader.snapshot` の小さい seam の背後に、JSON 走査・遷移 replay・legacy 分岐・draft 選定・budget 投影を隠している。caller は失敗処理や legacy 分岐を知らずに済む（`publish/status.py` が20行の薄い adapter に縮小したのが好例）。
- **情報の重複漏れの解消**: 旧来6モジュールに散っていた `_extract_json_object` を1点へ集約し、checkpoint/decision/trajectory/colophon の個別読取を WorkSnapshot へ吸収。RepositorySnapshot が単一の現在像を site/dashboard/CLI/README/audit へ供給する。
- **temporal decomposition/shallow wrapper の増殖なし**: 旧 interface の上に新 interface を重ねず、caller を移行済み。`publish/site.py` の M6 契約面と `build_public_site.py` の正規生成器は役割分離が docstring で明示されている。
- **変更範囲の局所化**: 将来の状態追加は `State`/`Publication` enum と `_publication` に、schema 変更は宣言的 schema に閉じる。
- 唯一の設計上の綻びが P2-1（走査の例外復帰が救済まで許す点）で、これは failure model の一貫性に関わる。

## TDD Assessment

- **observable behavior 検証**: テストは snapshot/parse の interface 越しで、内部 scanner/reader を直接叩かない（設計 §1 と一致）。
- **意味ある failure injection**: 文字列 `"false"` 技術床（`test_tech_floor_rejects_string_false`）、複数JSON/duplicate（`test_model_output`）、modern↔stale checkpoint 不一致（`test_modern_event_replay_wins`）、採用稿↔最新稿分離を実データ的 fixture で網羅。
- **cross-consumer 統合**: `test_site_dashboard_and_cli_share_state_title_and_selected_draft` が site/dashboard/CLI JSON を同一 fixture で突き合わせ。mock 過剰ではなく Work fixture 経由の統合確認。
- **fail-closed 検証**: tech floor の hold、README 検証、audit warning 保持まで正常系以外を押さえている。
- **ギャップ**: (a) duplicate-key の**ネスト救済**を突く RED が無い（P2-1 を見逃した原因）。(b) modern replay **失敗**の fail-closed（lifecycle unknown 化）を直接主張する WorkSnapshot テストが無い（挙動自体は注入で正しいと確認済み）。(c) audience・published-count のクロス consumer 一致は未アサート。

---

## Residual Risks

- **実データが全 legacy**: modern strict-replay 優先という Phase 2/1 の中核は本番 works で一度も走っていない。次に modern work（`aleph run` を新規 checkpoint から）が生まれた時が最初の実地検証になる。今回は注入で健全性を確認済みだが、実運用初回の監視を推奨。
- **探索 caller の歩留まり**（P3-1）: 冗長モデル出力で niche/構成の JSON 抽出が旧来より保守的に None 化しうる。実 API 走行で観測すべき。
- **P2-1 の波及**: 修正までは、公開意思・技術床など strict schema の外向きゲートが、duplicate-key を含む矛盾応答から救済されたサブ値を受理しうる（確率は低いが fail-open）。

**再監査に必要な最小修正範囲**: P2-1 のみ。`aleph/core/model_output.py` で「scan 中に duplicate key を観測したら `fail_closed=True` では候補救済せず not-ok を返す（または矛盾オブジェクト span を消費して内部再走査を禁止）」の約2行修正＋公開 schema での救済不成立を主張する回帰テスト1件。これが入れば、他の受入項目はすべて満たされているため PASS 相当となる。

VERDICT: FAIL
