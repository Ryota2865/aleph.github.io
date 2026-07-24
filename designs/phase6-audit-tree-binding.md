# Phase 6 formal audit candidate-tree binding

状態: 初回正式監査FAIL・P2-1修繕green・focused再監査待ち

正典: `PLAN.md`、`PLAN_CHANGELOG.md` 0.7.20-30、
`designs/next-designer-execution-plan.md` §6.1/§6.3。

## 1. 問題

0.7.20-28のformal-audit ledgerはverdict順序と対象CHANGELOGを明示化したが、
`candidate_tree`は形式検査だけで、現在repositoryのGit実体へ照合していなかった。
そのためCHANGELOG番号を変えない未監査変更や、存在しないtreeを記録したentryでも
`currency=CURRENT`になり得た。

## 2. Binding

最新登録auditのcurrencyは、次をすべて満たす場合だけ`CURRENT`とする。

1. `target_changelog`が現在の最新CHANGELOG番号と一致する。
2. `candidate_tree`がGit tree objectとして存在する。
3. `candidate_commit`がGit commit objectとして存在し、そのtreeが`candidate_tree`と一致する。
4. `candidate_ref`が`refs/tags/audit-candidate/`配下に存在し、`candidate_commit`を指す。
5. 現在像が次のどちらかである。
   - clean worktreeの`HEAD^{tree}`
   - untracked/unstaged変更がなく、変更がすべてindexへstageされた状態
6. candidateから現在像への変更pathが、ledger entryの`closure_paths`内だけである。

candidate/commit/refが検証不能なら`UNKNOWN`、対象CHANGELOG不一致、dirty worktree、
allowlist外差分なら`NEEDS_AUDIT`へ倒す。verdict自体は保存証拠なので維持し、currencyだけを
現在適用可能性として判定する。

## 3. Closure allowlist

`closure_paths`は重複・絶対path・`..`を拒否し、次の機械的closure面だけを許す。

- `PLAN_CHANGELOG.md`
- `PROGRESS.md`
- `README.md`
- `README.en.md`
- `config/formal-audits.json`
- `designs/next-designer-execution-plan.md`
- 当該PASS report自身

code、test、契約design、他reportをallowlistへ入れられない。allowlist内の変更であっても
runbookの「監査証拠と機械的closureだけ」という意味制約は残る。

## 4. Read-only Git probe

`RepositoryReader`はsubprocessの引数配列で`git -C <root>`をread-only実行する。

- `rev-parse HEAD^{tree}`
- `status --porcelain=v1 --untracked-files=normal`
- `cat-file -e`
- `rev-parse <candidate_commit>^{tree}`
- `rev-parse <candidate_ref>^{commit}`
- `diff --name-only`または`diff --cached --name-only`

shellは使わず、5秒timeoutとする。Gitがない、rootがrepositoryでない、object/refがない場合は
例外でread surfaceを失わず`UNKNOWN`へ倒す。

## 5. Evidence durability

監査candidate treeは、PASS後に同じtreeを持つ証拠commitへ固定し、
`audit-candidate/<scope>-<date>` tagで到達可能にする。tagはbranchとともにremoteへpushする。
ledgerはtree、commit、完全refを全て記録する。これによりlocalのunreachable tree objectや
GC偶然性をformal currencyの根拠にしない。

既存current-state auditについては次を証拠identityとする。

- candidate tree: `351cd83ffe0bdaeec527d3dbb512e63070ccd19e`
- candidate commit: `9bdfe0e37b81692a842699e865119b0e5ae7f8fb`
- candidate ref: `refs/tags/audit-candidate/phase6-current-state-20260725`

## 6. 受入条件

1. clean HEADとcandidateの差分がclosure allowlist内だけなら`CURRENT`。
2. allowlist内だけをstageし、unstaged/untrackedがなければindex面も`CURRENT`。
3. codeのdirty変更またはcommit済みallowlist外変更は`NEEDS_AUDIT`。
4. tree、commit、refの不存在・不一致は`UNKNOWN`。
5. target CHANGELOG不一致は、treeが一致しても`NEEDS_AUDIT`。
6. JSON/report/CLIからbinding state、tree、unexpected pathsを監査できる。
7. public work state、予算、期限、作品生成経路を変更しない。

## 7. 非目標

- Git署名や署名鍵基盤
- remote GitHub APIでのref検証
- legacy audit全件へのcommit/ref遡及作成
- R-1およびR-3〜R-9の同時修繕
- 新作、local inference、有償API call、provider cost照合
