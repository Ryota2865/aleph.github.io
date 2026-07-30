# fixation.house_style blind人間annotation結果 v1

状態: **OBSERVED / AGREEMENT FLOOR NOT MET / NO ADJUDICATION**

## 1. 事前固定した入力と判定規則

- instrument: `fixation.house_style` v1（provisional）
- pre-label proof commit: `4069c7663397644b9fce39a08eb0f921aab8de41`
- source packet:
  `reports/calibration/phase6/house_style_blind_packet_v1.md`
- source Markdown SHA-256:
  `e01c464efebf8ce4667433c69588029ea9eb939db070dd6f0ada1f42b33dad1e`
- distributed print artifact:
  `reports/calibration/phase6/house_style_blind_packet_v1.pdf`
- print PDF SHA-256:
  `ebab0bf6bb5a1491022afd323aec30256f06c1fcffc12ab5989e91449cee8687`
- labels: `S = 同じ装置`、`T = 担体・役割を変えた変形`、`U = 異なる・不明`
- agreement floor: 12組中10組以上のexact agreement
- disagreement handling: 強制裁定せず、両回答をそのまま保存
- floor未達時: `fixation.house_style`をprovisionalのまま維持

この規則は両annotatorの回答前に固定され、結果を見た後の閾値変更、抜粋差替え、
classifier training、prompt tuningは行っていない。

## 2. 原回答identity

| annotator | role | completed_at | duration | raw artifact | SHA-256 |
|---|---|---|---:|---|---|
| H01 | owner | `2026-07-30 21:52 +09:00` | 46分 | `annotations/house_style_blind_H01_raw_v1.pdf` | `addb951a1629a51715b6ee62c325ff3e780478e88cff77c3dec3e28bd3da0151` |
| H02 | independent human annotator | `2026-07-30 21:52 +09:00` | 31分 | `annotations/house_style_blind_H02_raw_v1.pdf` | `1c2bee9a26fd3beda560b7f56d88224d56f94e44f96b27f876b28f2b1b5d9d0d` |

両原回答は1頁PDFで、24 labelすべてを判読できた。オーナー確認により、H01の訂正後の
実施時刻は上記の値で確定した。両者とも回答固定前の相談・出典調査を行わず、
sealed provenanceを見ていない。

## 3. 転記とexact agreement

| pair | H01 | H02 | exact match |
|---|---|---|---|
| P01 | S | T | no |
| P02 | U | S | no |
| P03 | U | U | yes |
| P04 | T | S | no |
| P05 | T | U | no |
| P06 | U | S | no |
| P07 | T | S | no |
| P08 | S | T | no |
| P09 | U | S | no |
| P10 | S | T | no |
| P11 | U | T | no |
| P12 | U | U | yes |

- exact matches: P03、P12
- exact agreement: `2/12 = 1/6 = 16.7%`
- preregistered floor: `10/12 = 83.3%`
- floor shortfall: 8組
- result: **FLOOR NOT MET**

Label分布はH01が`S=3 / T=3 / U=6`、H02が`S=5 / T=4 / U=3`。
不一致10組は裁定せず、表の両labelを観測値として維持する。

## 4. 契約上の判定

`fixation.house_style` v1は**provisionalを維持**する。この結果から自動判断への昇格、
作品評価への適用、classifierの正解label生成を行わない。合意床を事後に下げず、
同じpacketの回答を修正または取り直さない。

## 5. 解釈の境界

### Observed

- 二人の人間annotatorは同一packetを独立に評価し、exact agreementは2/12だった。
- 一致はP03とP12の`U/U`のみで、`S/S`または`T/T`の一致はなかった。
- 両者の所要時間は31分と46分で、40分を超えたH01も事前規則どおり打ち切られていない。

### Inference

このpacketと三択説明だけでは、二人が「表現の仕組み」とその変形境界を再現可能な形で
共有できなかった。少なくとも現instrumentを自動判断へ昇格できる証拠は得られなかった。

### Uncertainty

本結果だけでは、低合意の原因を、構成概念の曖昧さ、説明文、抜粋難度、候補分布、
annotatorごとの判定閾値の違いへ分解できない。二人・12組の低負荷protocolであり、
文学的品質、作品間の実際の類似度、いずれかのannotatorの正誤を確定するものではない。
候補選定者の予想labelは保存されていないため、accuracy goldとの比較でもない。

## 6. H01 post-task debrief

回答固定・agreement算出後、H01は次を報告した。

- 文章難度を非常に高いと感じた。
- 主な難しさは、レトリックの複雑さと文体の時代性だった。
- 説明文自体はよいと感じた。
- 実施内容の抽象度が高いため、例があると理解しやすいと感じた。

これはowner annotator一名の事後所感であり、低合意の原因を確定するものではない。
将来、例示の効果を検証する場合は、今回の回答やpacketを遡及変更せず、例と境界を事前固定した
別packetとして扱う。例がlabelを誘導する可能性もあるため、「理解支援」と「正解の教示」を
区別する必要がある。

## 7. 実施しなかったこと

- 不一致の強制裁定
- 合意床の引下げ
- 回答またはpacketの事後修正
- instrument statusの昇格
- classifier trainingまたはprompt tuning
- 新作、local inference、有償API call
