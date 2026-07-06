# corpus/ — 参照コーパス（PLAN §4.1）

取り込み済みコーパスの置き場。**本体はgit管理外**（.gitignore済み。公開にも含めない——PLAN §8）。

- 一次: 青空文庫 / Project Gutenberg / Wikisource（パブリックドメイン全文のみ）
- 二次: 非文学母材（arXiv要旨・法令・特許・プロトコル文書等。換骨奪胎用）
- 著作権保護テキストは全文を置かない。引用短片+書誌のみ（works/内の素材カードとして）。
- 自作（ALEPHの出力）を再取り込みする場合は明示ラベル必須（model-collapse対策、policies.yaml）。

取り込みスクリプトと索引は M1 で施工される（aleph/explore/corpus.py）。
