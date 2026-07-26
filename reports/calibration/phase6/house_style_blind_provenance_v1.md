# fixation.house_style blind packet provenance v1

状態: **PREPARED / OWNER LOCK REQUIRED / DO NOT SHOW BEFORE BOTH LABELS ARE LOCKED**

## annotation開始前にオーナーがlockするprotocol

- instrument: `fixation.house_style` v1（provisional）
- packet: `reports/calibration/phase6/house_style_blind_packet_v1.md`
- print artifact: `reports/calibration/phase6/house_style_blind_packet_v1.pdf`（人間annotatorへの配布対象）
- candidate selector: Codex設計者。候補抽出とhard negative作成だけを担当し、人間goldを置換しない。
- annotation actor: 人間2名。1名はオーナー、もう1名は独立した人間annotator（未指定。開始前に固定）。
- annotation model/prompt: なし。packet本文の三択説明だけを使用する。
- excerpt unit: 既存採用稿（w0009はselected draft v3）の連続部分からなる短い抜粋。
  見出し、題名、work IDを表示しない。
- labels: `S = 同じ装置`、`T = 担体・役割を変えた変形`、`U = 異なる・不明`
- proposed agreement floor: exact agreement `10/12`以上。オーナー承認後にlockし、結果を見て閾値を下げない。
- proposed disagreement handling: 不一致は強制裁定せず、pair単位で両labelを保存する。合意床未達なら
  `fixation.house_style`をprovisionalのまま維持する。合意床達成だけで自動判断へ昇格しない。
- prohibited: annotatorへの候補選定理由・予想label・source mappingの事前表示、相談、
  classifier training、prompt tuning、結果を見た後の抜粋差替え。

## A/B orientation

表示順は、各`pair_id`について次の文字列のSHA-256先頭hexを用い、奇数ならbase順を反転した。

```text
house-style-v1|979c3e75e0fc7c119832f34df1b11ee59399a968|{pair_id}
```

| pair | digest | orientation |
|---|---|---|
| P01 | `1da285e8895b641b76643162122ff96b779624134c7e20901d9df44654d3979d` | flip |
| P02 | `21ddb174353680de36d9bc7aa94552f7ebccd5e1510fd84448ef24dc6a9ce89c` | keep |
| P03 | `47389e2e480da4474d3726a44958263418b27380a30157c4ed783f6b8cf11367` | keep |
| P04 | `8df26e74bc4929c4b6fd8d968ea21f354fc6ce197700643856dc6cb1006c5df6` | keep |
| P05 | `a2ea8ee0c681dd5bfd2de4c6a2f7377a25e12cdd318915b3bf9a90ee18720075` | keep |
| P06 | `9fc40eed37ceb9af257cc36f5b744547c4c57b99c909e3811550c1910474ef25` | flip |
| P07 | `064cc008ea3849f7edba02895ba16d8a875eb7d2308d26bb31e779e41cae2098` | keep |
| P08 | `be2a35726b636f41a387c0fdc3e1a8dde656d80ae6da3416e51545b6b5d1f208` | flip |
| P09 | `73310cad1ede0aeb37775c3eb5087150b6e4a990f183b7233ee02392b458b52c` | flip |
| P10 | `828137b255bcc94d53cacbd2f2026e3b97d3f662cf55145819b472c8d17cdfc4` | keep |
| P11 | `e8b10038c6d73a76120b7cfe109bd6f86d80bf42becdc71f472c7c5c46eacc54` | keep |
| P12 | `62bfaf8e3664ba952453a550e7392f3662f89ba0eb4edaeaa4b44d5c2321188b` | keep |

## Source mapping

候補選定者の予想labelは保存しない。mappingは再現性だけを目的とする。

| pair.side | source |
|---|---|
| P01.A | `works/w0007/final/text.md:23` |
| P01.B | `works/w0004/final/text.md:231-235` |
| P02.A | `works/w0005/final/text.md:11` |
| P02.B | `works/w0009/drafts/v3.md:22` |
| P03.A | `works/w0006/final/text.md:51` |
| P03.B | `works/w0007/final/text.md:19` |
| P04.A | `works/w0004/final/text.md:55-57` |
| P04.B | `works/w0008/final/text.md:67` |
| P05.A | `works/w0006/final/text.md:45` |
| P05.B | `works/w0008/final/text.md:47` |
| P06.A | `works/w0009/drafts/v3.md:35` |
| P06.B | `works/w0007/final/text.md:53` |
| P07.A | `works/w0008/final/text.md:55` |
| P07.B | `works/w0009/drafts/v3.md:154` |
| P08.A | `works/w0009/drafts/v3.md:74` |
| P08.B | `works/w0004/final/text.md:1570` |
| P09.A | `works/w0008/final/text.md:33` |
| P09.B | `works/w0006/final/text.md:57` |
| P10.A | `works/w0007/final/text.md:43` |
| P10.B | `works/w0009/drafts/v3.md:65` |
| P11.A | `works/w0004/final/text.md:71-73` |
| P11.B | `works/w0005/final/text.md:13` |
| P12.A | `works/w0006/final/text.md:115` |
| P12.B | `works/w0007/final/text.md:85` |

## Source identities

| source | SHA-256 |
|---|---|
| `works/w0004/final/text.md` | `cab133b6171969e662fd7a92d2a4e79037ac68d7303d60c220c482efd209c421` |
| `works/w0005/final/text.md` | `9cf494bb456a174a6054a4b05428721a83cfed60b14e985ab5512dd070ad70b5` |
| `works/w0006/final/text.md` | `405ddadc0191a4122801689fa8b5c46eece553254ed90183ece86f8663135c64` |
| `works/w0007/final/text.md` | `8bd27be991ce173c1769a8c7c2cf34031f101acbf7ae41bf2e3bcc52570a17be` |
| `works/w0008/final/text.md` | `72c545f8bd0f5be89a5ff8aeeb5c44bf415a9f75ed0f2b56588750ef1fffdfd1` |
| `works/w0009/drafts/v3.md` | `1b351e11fad55967c7f7f7821c1fc5e72e3092b15a61dcbbbe416e97c755649c` |

Source Markdown SHA-256: `3285a114919f153d90a039d37aeee9136fa39bde487cb884b81393ef8f804663`

Print PDF SHA-256: `7550c5efdb35c2b6643235df6c2223ad6a29713a5ab70e0c34a915b4e6e02b00`

PDF build: `.zed/tasks.json`の`Markdown → PDF (Typst)` task、Pandoc 3.10.1、
`--from=gfm --pdf-engine=typst --variable=papersize:a4`。出力はPDF 1.7、5頁。
