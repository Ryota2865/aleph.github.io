"""fixation_checkの配線初回テストケース（PLAN_CHANGELOG 0.7.18-1、Fable5審査 問7-2）.

Fable5の指摘: 「〜ほど」警句機関（w0004）・弁証法的往復（w0005）・職能語彙の統一比喩網
（w0007）は、同じAI紋が三度、衣裳を替えて出た実物であり、固着監視の初回テストケースと
して理想的。検出できなければ、監視器のほうを疑うべき。

**実際の結果: fixation_checkはこの反復を検出しない（False）**。Jaccard類似度は
それぞれ1.5%・2.7%——閾値0.8に遠く及ばない。これは実装の不具合ではなく、
`_bigrams`が文字2-gramの語彙的重複しか見ていないことの当然の帰結である:
「Xほど、Yない」という**構文パターン**の反復は、3作が全く異なる題材（役者小屋の
稽古場・弁証法的唯物論の論考・質屋の帳場）を扱う以上、共有される文字bigramの
絶対数が小さすぎて検出限界の外にある。

**結論（司令塔記述）**: fixation_checkは「詩学本文が版を跨いで同じ語彙へ収斂して
いないか」を見る設計としては機能しうるが、「生成された作品群に同じ修辞装置＝AI紋が
繰り返し出現していないか」を見る設計としては機能しない——後者は文字bigramではなく
構文・修辞パターンの抽出（例: LLM審級による装置の同定、または既存のAI固有表現
detector群の拡張）を要する、別の測定器が必要という設計上の限界が実証された。
Fable5の「検出できなければ監視器を疑え」という条件どおり、監視器の設計範囲を
このテストで確定する。

実行: pytest -m m5
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.m5

# w0004「半呼吸」docs/works/w0004.html / works/w0004/final/text.md からの実際の抜粋
# （「Xほど、Yないものはない」という警句構文の反復）
_W0004_EXCERPT = (
    "逃げると言われる役者ほど、逃げ道の位置をよく見る。"
    "乾いた赤ほど、よく残るものはない。"
    "段取りほど、よく隠れるものはない。"
    "半分残った名ほど呼びにくいものはない。"
    "大きな言葉ほど、仮小屋の梁へ当たる音は軽い。"
)

# w0005「床の硬さ」works/w0005/final/text.md からの実際の抜粋
# （「だが/しかし、〜はそこで終わらない/止まらない」という弁証法的往復構文の反復）
_W0005_EXCERPT = (
    "だが、問題はそこで終わらない。いかなる「問題」が問題として提出されうるのか。"
    "しかし、問題はそこで止まらない。行為の成功は、誰にとっての成功か。"
)

# w0007「折り目」works/w0007/final/text.md からの実際の抜粋
# （質屋・仕立ての職能語彙による「折り目」の統一比喩網の反復）
_W0007_EXCERPT = (
    "折り目は、進物の掛け紙と同じ向きにした。折り目は家を語る。"
    "畳み方の正しい品は仕舞い方の正しい家から来て、"
    "折り目は掛け紙の向きに揃い、折り目のところで止まった。"
)


def test_fixation_check_does_not_detect_recurring_rhetorical_device_across_works():
    """3作にまたがる同一のAI紋（修辞装置）の反復を、既存のfixation_checkは検出しない
    ——文字bigram類似度が低すぎるため（実測: 約1.5%・2.7%）。この失敗自体が、
    fixation_checkの設計範囲（詩学本文の語彙的固着監視）と、AI紋の構造的反復検出は
    別の測定器を要することを示す実証結果である。"""
    from aleph.meta.poetics import _jaccard, fixation_check

    history = [_W0004_EXCERPT, _W0005_EXCERPT, _W0007_EXCERPT]

    assert fixation_check(history) is False

    jaccard_04_05 = _jaccard(_W0004_EXCERPT, _W0005_EXCERPT)
    jaccard_05_07 = _jaccard(_W0005_EXCERPT, _W0007_EXCERPT)
    assert jaccard_04_05 < 0.1
    assert jaccard_05_07 < 0.1
