# EXP transmute pilot 2026-07-17

## Inputs

- works: `/home/ryota_tanaka/llm_literature/corpus/secondary/works.jsonl`
- theme: 観測と記憶
- n: 40

## Per-Source Measurements

| id | form_type | title | content_distance | form_fidelity | source_features | generated_features | generated_chars | notes |
|---|---|---|---:|---:|---|---|---:|---|
| law:106DF0000000065 | law | 明治六年太政官布告第六十五号（絞罪器械図式） | 0.4147 | 0.0000 |  | law.definition | 1065 |  |
| law:117DF1000000032 | law | 明治十七年太政官布告第三十二号（爆発物取締罰則） | 0.5145 | 1.0000 | law.article, law.definition, law.proviso | law.article, law.definition, law.proviso | 1063 |  |
| law:122AC0000000034 | law | 明治二十二年法律第三十四号（決闘罪ニ関スル件） | 0.4821 | 1.0000 | law.article, law.proviso | law.article, law.definition, law.proviso | 444 |  |
| law:123AC0000000001 | law | 保管金規則 | 0.5229 | 1.0000 | law.article | law.article, law.definition, law.item, law.proviso | 1353 |  |
| law:128AC0000000028 | law | 通貨及証券模造取締法 | 0.4562 | 0.5000 | law.article, law.proviso | law.article, law.definition, law.item | 1347 |  |
| law:129AC0000000005 | law | 国債証券買入銷却法 | 0.4956 | 0.0000 | law.article, law.proviso | law.definition | 672 |  |
| law:132AC0000000015 | law | 供託法 | 0.5699 | 0.6667 | law.article, law.definition, law.proviso | law.article, law.definition | 1471 |  |
| law:132AC1000000040 | law | 明治三十二年法律第四十号（失火ノ責任ニ関スル法律） | 0.4232 | 1.0000 | law.article | law.article, law.definition, law.item, law.proviso | 1345 |  |
| law:132AC0000000050 | law | 明治三十二年法律第五十号（外国人ノ署名捺印及無資力証明ニ関スル法律） | 0.5129 | 0.0000 | law.article | law.definition | 287 |  |
| law:132AC0000000093 | law | 行旅病人及行旅死亡人取扱法 | 0.5370 | 1.0000 | law.article, law.definition, law.proviso | law.article, law.definition, law.proviso | 1935 |  |
| law:132AC0000000101 | law | 明治三十二年法律第百一号（国債ヲ外国ニ於テ募集スル場合ニ関スル法律） | 0.3986 | 0.0000 |  | law.definition, law.proviso | 369 |  |
| law:133AC1000000033 | law | 二十歳未満ノ者ノ喫煙ノ禁止ニ関スル法律 | 0.4921 | 1.0000 | law.article, law.proviso | law.article, law.definition, law.proviso | 1073 |  |
| law:133AC0000000065 | law | 鉄道営業法 | 0.4781 | 0.5000 | law.article, law.proviso | law.article, law.definition, law.item, law.paragraph | 1113 |  |
| law:133AC1000000072 | law | 明治三十三年法律第七十二号（地上権ニ関スル法律） | 0.4587 | 1.0000 | law.article | law.article, law.definition, law.item, law.proviso | 1097 |  |
| law:135AC0000000011 | law | 明治三十五年法律第十一号（警察署内ノ留置場ニ拘禁又ハ留置セラルル者ノ費用ニ関スル法律） | 0.5450 | 1.0000 | law.article, law.proviso | law.article, law.definition, law.proviso | 631 |  |
| law:135AC1000000050 | law | 明治三十五年法律第五十号（年齢計算ニ関スル法律） | 0.4959 | 1.0000 | law.article | law.article, law.definition | 658 |  |
| law:137AC0000000017 | law | 明治三十七年法律第十七号（記名ノ国債ヲ目的トスル質権ノ設定ニ関スル法律） | 0.5042 | 1.0000 | law.article | law.article, law.definition | 1008 |  |
| law:138AC0000000055 | law | 鉱業抵当法 | 0.5215 | 1.0000 | law.article, law.proviso | law.article, law.definition, law.item, law.proviso | 1439 |  |
| law:138AC0000000063 | law | 外国裁判所ノ嘱託ニ因ル共助法 | 0.5041 | 1.0000 | law.article | law.article, law.definition, law.item, law.proviso | 1366 |  |
| law:138AC1000000066 | law | 明治三十八年法律第六十六号（外国ニ於テ流通スル貨幣紙幣銀行券証券偽造変造及模造ニ関スル法律） | 0.4663 | 1.0000 | law.article, law.proviso | law.article, law.definition, law.proviso | 1421 |  |
| rfc:768 | rfc | RFC 768: User Datagram Protocol | 0.5122 | 0.0000 |  |  | 2245 |  |
| rfc:791 | rfc | RFC 791: Internet Protocol | 0.5013 | 0.0000 | rfc.section |  | 1401 |  |
| rfc:792 | rfc | RFC 792: Internet Control Message Protocol | 0.5991 | 0.0000 |  |  | 4162 |  |
| rfc:793 | rfc | RFC 793: Transmission Control Protocol | 0.4502 | 0.0000 | rfc.section |  | 1017 |  |
| rfc:821 | rfc | RFC 821: Simple Mail Transfer Protocol | 0.5584 | 1.0000 | rfc.section | rfc.section | 3600 |  |
| rfc:822 | rfc | RFC 822: Standard for the Format of ARPA Internet Text Messages | 0.5970 | 1.0000 | rfc.section | rfc.section | 4188 |  |
| rfc:1122 | rfc | RFC 1122: Requirements for Internet Hosts - Communication Layers | 0.5626 | 1.0000 | rfc.section | rfc.section | 5399 |  |
| rfc:1459 | rfc | RFC 1459: Internet Relay Chat Protocol | 0.5831 | 1.0000 | rfc.abstract, rfc.section | rfc.abstract, rfc.section | 3636 |  |
| rfc:1738 | rfc | RFC 1738: Uniform Resource Locators (URL) | 0.5768 | 1.0000 | rfc.abstract, rfc.section | rfc.abstract, rfc.section | 4633 |  |
| rfc:1945 | rfc | RFC 1945: Hypertext Transfer Protocol -- HTTP/1.0 | 0.6040 | 1.0000 | rfc.abstract, rfc.section | rfc.abstract, rfc.section | 5150 |  |
| rfc:2119 | rfc | RFC 2119: Key words for use in RFCs to Indicate Requirement Levels | 0.4976 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 1769 |  |
| rfc:3986 | rfc | RFC 3986: Uniform Resource Identifier (URI): Generic Syntax | 0.5898 | 0.5000 | rfc.abstract, rfc.section | rfc.section | 4576 |  |
| rfc:5246 | rfc | RFC 5246: The Transport Layer Security (TLS) Protocol Version 1.2 | 0.5790 | 0.4000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.abstract, rfc.section | 5027 |  |
| rfc:6749 | rfc | RFC 6749: The OAuth 2.0 Authorization Framework | 0.6626 | 0.5000 | rfc.abstract, rfc.section | rfc.section | 5731 |  |
| rfc:7231 | rfc | RFC 7231: Hypertext Transfer Protocol (HTTP/1.1): Semantics and Content | 0.5671 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 3215 |  |
| rfc:7540 | rfc | RFC 7540: Hypertext Transfer Protocol Version 2 (HTTP/2) | 0.5424 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 3251 |  |
| rfc:8446 | rfc | RFC 8446: The Transport Layer Security (TLS) Protocol Version 1.3 | 0.4445 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 1426 |  |
| rfc:9000 | rfc | RFC 9000: QUIC: A UDP-Based Multiplexed and Secure Transport | 0.5835 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 5422 |  |
| rfc:9110 | rfc | RFC 9110: HTTP Semantics | 0.6442 | 1.0000 | rfc.abstract, rfc.section | rfc.abstract, rfc.section | 5100 |  |
| rfc:9114 | rfc | RFC 9114: HTTP/3 | 0.5784 | 0.2000 | rfc.abstract, rfc.may, rfc.must, rfc.section, rfc.should | rfc.section | 5542 |  |

## Scatter Summary

- content_distance: n=40, min=0.3986, median=0.5180, max=0.6626
- form_fidelity: n=40, min=0.0000, median=0.8333, max=1.0000
- Pearson r(content_distance, form_fidelity): 0.1791

## Raw Values

| id | form_type | content_distance | form_fidelity | transmute_final_cos |
|---|---|---:|---:|---:|
| law:106DF0000000065 | law | 0.4147 | 0.0000 | 0.4147 |
| law:117DF1000000032 | law | 0.5145 | 1.0000 | 0.5147 |
| law:122AC0000000034 | law | 0.4821 | 1.0000 | 0.4821 |
| law:123AC0000000001 | law | 0.5229 | 1.0000 | 0.5229 |
| law:128AC0000000028 | law | 0.4562 | 0.5000 | 0.4562 |
| law:129AC0000000005 | law | 0.4956 | 0.0000 | 0.4956 |
| law:132AC0000000015 | law | 0.5699 | 0.6667 | 0.5699 |
| law:132AC1000000040 | law | 0.4232 | 1.0000 | 0.4232 |
| law:132AC0000000050 | law | 0.5129 | 0.0000 | 0.5129 |
| law:132AC0000000093 | law | 0.5370 | 1.0000 | 0.5370 |
| law:132AC0000000101 | law | 0.3986 | 0.0000 | 0.3986 |
| law:133AC1000000033 | law | 0.4921 | 1.0000 | 0.4921 |
| law:133AC0000000065 | law | 0.4781 | 0.5000 | 0.4781 |
| law:133AC1000000072 | law | 0.4587 | 1.0000 | 0.4587 |
| law:135AC0000000011 | law | 0.5450 | 1.0000 | 0.5450 |
| law:135AC1000000050 | law | 0.4959 | 1.0000 | 0.4959 |
| law:137AC0000000017 | law | 0.5042 | 1.0000 | 0.5042 |
| law:138AC0000000055 | law | 0.5215 | 1.0000 | 0.5215 |
| law:138AC0000000063 | law | 0.5041 | 1.0000 | 0.5041 |
| law:138AC1000000066 | law | 0.4663 | 1.0000 | 0.4663 |
| rfc:768 | rfc | 0.5122 | 0.0000 | 0.5122 |
| rfc:791 | rfc | 0.5013 | 0.0000 | 0.5013 |
| rfc:792 | rfc | 0.5991 | 0.0000 | 0.5991 |
| rfc:793 | rfc | 0.4502 | 0.0000 | 0.4502 |
| rfc:821 | rfc | 0.5584 | 1.0000 | 0.5584 |
| rfc:822 | rfc | 0.5970 | 1.0000 | 0.5970 |
| rfc:1122 | rfc | 0.5626 | 1.0000 | 0.5626 |
| rfc:1459 | rfc | 0.5831 | 1.0000 | 0.5831 |
| rfc:1738 | rfc | 0.5768 | 1.0000 | 0.5768 |
| rfc:1945 | rfc | 0.6040 | 1.0000 | 0.6040 |
| rfc:2119 | rfc | 0.4976 | 0.2000 | 0.4976 |
| rfc:3986 | rfc | 0.5898 | 0.5000 | 0.5898 |
| rfc:5246 | rfc | 0.5790 | 0.4000 | 0.5790 |
| rfc:6749 | rfc | 0.6626 | 0.5000 | 0.6626 |
| rfc:7231 | rfc | 0.5671 | 0.2000 | 0.5671 |
| rfc:7540 | rfc | 0.5424 | 0.2000 | 0.5424 |
| rfc:8446 | rfc | 0.4445 | 0.2000 | 0.4445 |
| rfc:9000 | rfc | 0.5835 | 0.2000 | 0.5835 |
| rfc:9110 | rfc | 0.6442 | 1.0000 | 0.6442 |
| rfc:9114 | rfc | 0.5784 | 0.2000 | 0.5784 |

## Findings

**測定器は目的と直交している（sol §4.4の疑いを実証。designs/corpus-expansion.md 前提の検証）。**
現行 `transmute()` の唯一のゲートは embedding cosine（近すぎ=パロディ／遠すぎ=無関係の帯域 0.3–0.85）
であり、骨格保存という transmute の本来の目的（PLAN §5.3「形式的骨格を保存したまま内容を入替」）を
直接測っていない。本パイロットの form_fidelity（法令=条項号・定義・但し書き、RFC=MUST/SHOULD/MAY・
節番号・Abstract の検出器ベース残存率）との相関は **Pearson r = 0.1791**（n=40）でほぼ無相関。

- **反例（ゲート通過・骨格全消失）**: law:106DF0000000065 (0.4147)、rfc:768 (0.5122)、
  rfc:791 (0.5013)、rfc:792 (0.5991)、rfc:793 (0.4502) の5件は content_distance が帯域中央
  (0.40–0.60) に収まり現行ゲートを通過するが、form_fidelity=0.0000——母材の構造的特徴が
  生成文に一つも残っていない。cosine だけでは「意味は程よく離れたが骨格も消えた」贋作を
  合格させてしまう。
- **両立例も存在**（測定器が常に無意味というわけではない）: rfc:9110 (HTTP Semantics) は
  content_distance=0.6442（帯域内・やや高め）かつ form_fidelity=1.0000（完全な骨格保存）。
  骨格保存と意味的距離は両立し得るが、現行ゲートはそれを**選別しない**。
- **form_fidelity の分布は二極化**（min=0.0000, median=0.8333, max=1.0000）——骨格が
  「残るか消えるか」ははっきり分かれる一方、content_distance は 0.3986–0.6626 という
  狭い帯に収束しており、この一軸だけでは生成物の質的な違いを弁別できない。
- **設計含意（S-3着手前の要判断）**: 大量取得（S-2以降のスケールアップ）の前に、
  `transmute()` のゲートへ form_fidelity 相当の detector ベース基準を第二軸として追加するか、
  最低限 provenance に二軸を併記するログ変更が必要。現行の cosine 単独ゲートのままでは
  「骨格喪失」を検出できない。detector は form_type 別の正規表現ベースなので、二次コーパスの
  form_type を増やすたびに新規実装が要る点もスケール時の負債として明記しておく。

**副産物: 測定パイプライン自体のバグを1件発見・回避**。`build_secondary_corpus.py` の
`--max-chars` 既定値(20000字)は、漢字密度の高い法令テキストで bge-m3 の n_ctx=8192 を
超過しうる（実測: law:131AC0000000014 の19,638字→13,122トークンで embeddings が500エラー）。
文字数は CJK テキストのトークン数の安全な代理指標ではない。今回は法令側の `--max-chars` を
8000へ下げて回避（RFC側は英語で密度が低く20000字でも実測5000トークン台で安全）。これは
2026-07-09に記録済みの既知debt（explore実ランの埋め込み失敗、巨大段落で8192超）と同根であり、
恒久修正は `aleph/explore/corpus.py::LlamaServerEmbedder` 側でのトークン数ベースの安全マージン
（本パイロットのallowlist外のため今回は未修正、次のdebtとして記録）。

