# 属性被覆・層化標本推定 2026-07-17

- 標本: 225 作品（注釈成功 223 / 未注釈 2 / 低信頼<0.5 0）
- ノイズ多数派作品（アトラス上でチャンクの過半がノイズ）: 220 件——ノイズ点を被覆測定から落とさないという要求（0.7.19 問2）の充足を示す。
- 注釈器: gemma-4-26B-A4B-it-qat-UD-Q4_K_XL（prompt work-sample-v1、単一注釈器）
- 層化: author_death_decade・著者上限 2・seed 42
- **これは標本推定である**。era・言語・形式(NDC)の全数真値は `reports/CORPUS_COVERAGE_METADATA_*.md`（台帳直接計算）を参照。

### theme（観測 221 種）

| 値 | 作品数 |
|---|---|
| ethnography/geography | 2 |
| supernatural_and_morality | 2 |
| Absurdity and the blurring of truth and falsehood | 1 |
| Comparative musicology/Etymology of musical instruments | 1 |
| Comparative mythology and folklore (snakes/serpents in Ireland and Japan) | 1 |
| Creation and the cycle of life and death | 1 |
| Editorial message, commitment to publication, personal status report, and reflections on lifestyle/social issues. | 1 |
| Emotional metamorphosis and primal longing | 1 |
| Ethnological/Archaeological debate regarding the identity and origins of the Ainu and Korobokkuru | 1 |
| Identity and Crime (Identity/Social Struggle/Mystery) | 1 |
| Marriage and familial discord, social status, and the consequences of excessive parental pride | 1 |
| Memoir/Intellectual lineage | 1 |
| Memoir/Tribute to a master/Intellectual interaction | 1 |
| Nature and human memory | 1 |
| Nature and human sensibility (the duality of seasonal change and psychological states) | 1 |
| Nature vs. Humanity (the power of the sea/danger) | 1 |
| Okinawan food culture and nostalgia | 1 |
| SF/Adventure | 1 |
| Virtue versus vanity, the testing of character through adversity, beauty and inner goodness | 1 |
| abundance and seasonal bounty of fruits | 1 |
| adventure and unexpected experiences | 1 |
| adventures, exploration, surrealism, social satire | 1 |
| animal_instinct_vs_anthropomorphism | 1 |
| artistic_inspiration_and_perceptual_fragmentation | 1 |
| beauty and vanity / aesthetics of appearance | 1 |

### form（観測 185 種）

| 値 | 作品数 |
|---|---|
| 随筆（エッセイ） | 14 |
| essay | 8 |
| short_story | 4 |
| 随筆・エッセイ | 4 |
| Essay | 2 |
| fable | 2 |
| first-person monologue/reminiscence | 2 |
| free verse poetry | 2 |
| free_verse_poetry | 2 |
| prose narrative | 2 |
| 書簡（手紙） | 2 |
| 歴史小説（時代小説） | 2 |
| 短編小説（散文） | 2 |
| 論説・エッセイ | 2 |
| 論説（エッセイ） | 2 |
| 随筆 | 2 |
| Academic treatise/Expository essay | 1 |
| Autobiographical essay | 1 |
| Editorial/Letter-style essay (column) | 1 |
| Epistolary/Framed Narrative (Metafiction) | 1 |
| Essay/Autobiographical prose | 1 |
| Essay/Non-fiction | 1 |
| Fairy tale (folktale) | 1 |
| Fairy tale-like narrative with satirical commentary | 1 |
| Free verse poem | 1 |

### viewpoint（観測 149 種）

| 値 | 作品数 |
|---|---|
| first-person | 17 |
| 一人称（私） | 13 |
| third-person omniscient | 10 |
| 三人称客観視点 | 7 |
| third-person limited | 5 |
| third-person_omniscient | 4 |
| third_person_omniscient | 4 |
| 一人称（著者自身） | 4 |
| First-person (I) | 3 |
| first-person (I) | 3 |
| first-person observer | 3 |
| first_person | 3 |
| 一人称（僕） | 3 |
| Third-person omniscient | 2 |
| first-person female | 2 |
| first-person protagonist | 2 |
| first_person_observer | 2 |
| third_person_objective | 2 |
| 一人称（観察者） | 2 |
| 三人称多角的視点 | 2 |
| 三人称客観視点（全知視点） | 2 |
| First-person (Authorial 'I') | 1 |
| First-person (Dual perspective: Narrator/Author and Protagonist) | 1 |
| First-person (Father's perspective) | 1 |
| First-person (I/Ore/Waga) | 1 |

### 占有組み合わせ（theme×form×viewpoint）: 223 通り

### era（台帳）× theme（注釈）上位

| era / theme | 作品数 |
|---|---|
| 1950s / 演劇界の現状分析と新劇団のあり方への提言 | 1 |
| 1950s / 科学的真理の探究と社会への応用 | 1 |
| 1950s / existential_anxiety_and_fragmented_identity | 1 |
| 1950s / 演劇論・近代劇運動の批評 | 1 |
| 1950s / memoir/family history | 1 |
| 1950s / 江戸の風俗と情緒 | 1 |
| 1950s / 都市の変容と新旧の対照（風景の美学） | 1 |
| 1950s / 芸術における意匠（技巧・様式）と表現（本質）の相克と調和 | 1 |
| 1950s / 美と欠落、存在の虚無感、神話的モチーフの現代への投影 | 1 |
| 1950s / 人間関係の機微と孤独 | 1 |
| 1950s / war_and_fatigue | 1 |
| 1950s / 慈悲と対立の超越、仏道における生き方の対比 | 1 |
| 1950s / 近代文明における科学的・実証的精神の普及と、それによる社会構造（生産様式・経営・行政）の変容および合理化 | 1 |
| 1950s / 回想・栄光と凋落の対比 | 1 |
| 1950s / memorialization of an actor's death amidst wartime destruction | 1 |
| 1950s / loss and transience | 1 |
| 1950s / correspondence | 1 |
| 1950s / 文学的評価と宗教的・民族的精神の探究 | 1 |
| 1950s / 存在の驚きと自然との一体感における芸術の不可欠性 | 1 |
| 1950s / 陶磁器の歴史的変遷と茶の湯における美的価値の形成 | 1 |

## 所見（司令塔記述）— 計器の問題を1件検出

**自由語彙ラベルの断片化により、組み合わせ占有の測定は今回の形では成立していない。**
223作品の注釈成功に対し theme が221種・form が185種——ほぼ全作品が固有ラベルを持ち、
「占有組み合わせ」は全数と同義になる。加えてラベルの大半が英語で返っており
（プロンプトは日本語）、正規化なしには軸としても層としても使えない。

- 成立しているもの: 層化サンプリング自体（225作品・ノイズ多数派220件・著者上限・
  決定論seed）、単一注釈器の出所明示、注釈の永続化。標本の器は正しい。
- 成立していないもの: 開語彙の属性値をそのまま数える被覆測定。これは
  cluster注釈（n=4）が「粗すぎて無意味」だったのと対称に、「細かすぎて無意味」。
- 次の一手（設計変更の門を通る——観測された計器の失敗への応答）:
  (1) prompt v2: 日本語・短い名詞句を強制し、応答語彙の分散を下げる。
  (2) それでも開語彙の正規化は必要——ラベル自体を埋め込み+クラスタリングで
  粗視化するか、台帳のNDC形式軸と同様の「閉じた粗い語彙＋自由記述の併記」二段構えにする。
  被覆（セルの空き）を数えられるのは閉じた語彙だけであり、発見的な細部は自由記述に残す。
