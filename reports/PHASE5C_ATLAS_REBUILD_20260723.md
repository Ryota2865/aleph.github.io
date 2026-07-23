# Phase 5C step 10 — Atlas再構築とfull identity初回発行

日付: 2026-07-23
scope: Phase 5C施工順10のみ
owner決定: 現行青空文庫corpus＋現行PCA64/HDBSCAN構成。corpus拡張とUMAP本番昇格は分離する。

## 観測

- source Atlas: `state/atlas`（既存artifactはread-only）
- new Atlas: `state/atlases/phase5c-pca64-hdbscan40-aozora-v1`
- full identity:
  `8ab3e51a4d8c64bdbb456b2dc7dbea9bdf4fe71f60888eda997203c4c59827ca`
- corpus: 青空文庫16,950作品、95,690チャンク
- plain index: 1024次元bge-m3 f16。source/newの`manifest.json`、`chunks.jsonl`、
  `embeddings.npy`はそれぞれSHA-256一致。
- build:
  - PCA: 64次元、`random_state=42`
  - HDBSCAN: `min_cluster_size=40`、`cluster_selection_method=eom`
  - kNN: 16、PCA空間上のEuclidean
  - style: 95,690×9
- output: labels/density各95,690、4 clusters。新Atlas全体857MB。
- `identity.json`は全artifact生成・verify・`Atlas.load()`成功後にstaging directoryを
  final directoryへrenameする最後のcommit markerとして発行した。
- provider call、corpus取得、再embedding、新作生成、既存Atlas/work/audit書換えは行っていない。

## identityに固定したprovenance

- corpus source SHA-256:
  `0fe63b3e2bc219ba97e6969d2d1adfa5a9d5c9dfda5e0f159e2e771b476ca6e8`
- corpus license manifest SHA-256:
  `a189c46f1646ed3fdc00bee378ffb61b0cdcde8107f1b1c7424e0248147a1600`
- chunks SHA-256:
  `1039855598da18f8ab3aea5aa465c173e079f8248e51484028b248502e5415b1`
- embeddings SHA-256:
  `3f5733159ef709ae11a43a288b6926972390680a95ca3599f2e3c4756896664e`
- bge-m3 f16 artifact SHA-256:
  `a8d0847ea726e827a3318974f04b2895f5b59481bf6441357a21f38425d0ceff`
- `aleph/explore/atlas.py` SHA-256:
  `28209f6e7d7a5bdc6162645c9b30650b47c81e33ad6657306b2a8dc54f8b3926`
- `aleph/explore/atlas_identity.py` SHA-256:
  `213c634c29713b72f665cd7701247b85b0476276fe285275f7c1268408901af2`

## 故障注入

`/tmp/aleph-phase5c-atlas-fault-iAV1rr`に実Atlasのread-only symlinkとidentityを置き、
copyした`atlas_meta.json`だけを1 byte変更した。`Atlas.load()`は次でfail closedした。

```text
AtlasIdentityError: Atlas artifact hash mismatch: atlas_meta.json
```

source/new同一directory、既存destination、build specと実行引数の不一致もtestでprovider前・
書込み前に拒否する。

## 検証

- focused: **20 passed, 14 deselected**
- 全non-local: **385 passed, 1 deselected**
- `git diff --check`: 違反なし
- real identity verify: `True`
- real `Atlas.load()`: PASS

## 推論

- source/newのplain index hash一致により、観測されたAtlas差分はcorpusやembeddingの変更ではなく、
  seedを明示した再構築artifactの差分である。
- 旧Atlasと新Atlasはbit同一ではないため比較不能であり、旧novelty値を新identityへ遡及帰属しない。
- cluster数4は現行PCA/eom構成の既知の粗さを再現した観測であり、corpusの真の均質性を意味しない。

## 解釈と残余

step 10はfull identity発行までgreen。これはcorpus拡張、UMAPの本番採用、novelty改善、
Phase 5全体完了を意味しない。step 11ではこの新identityを参照する
`InstrumentRecord`配線と、cross-identity比較拒否を検証する。
