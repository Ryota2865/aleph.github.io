"""モデルルーティング層の契約（PLAN §2.1・§14.1）.

設計上の不変条件（施工者はこれを破ってはならない。破ると tests/ が赤になる）:

1. コードは具体的なモデル名を参照しない。役割名（config/models.yaml の roles）のみ。
2. すべてのLLM呼び出しは CallLogger を経由して calls.jsonl に記録される。例外なし。
3. ログ・成果物への書き出しは必ず scrub_secrets を通す（PLAN §14.2）。
4. 予算超過が予見される呼び出しは実行前に BudgetExceeded を送出する（PLAN §2.1）。
5. ルーティング優先順位: local → harness → api（PLAN §14.1）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


@dataclass(frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class TokenLogprob:
    """logprobs はAI固有表現（PLAN §5.4）の一次素材。対応プロバイダでは必ず取得可能にする."""

    token: str
    logprob: float
    top_alternatives: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: Usage
    cost_usd: float
    logprobs: tuple[TokenLogprob, ...] | None = None
    response_hash: str = ""


class Provider(Protocol):
    """プロバイダアダプタの契約。

    実装対象（M0）: AnthropicProvider / OpenAICompatProvider（従量API・llama-server 兼用）
    / HarnessProvider（サブスクCLIの非対話モード。PLAN §14.1）。
    """

    name: str

    def complete(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        logprobs: bool = False,
        seed: int | None = None,
    ) -> LLMResponse: ...


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scrub_secrets(text: str, secrets: Iterable[str]) -> str:
    """既知の秘密文字列を [REDACTED] に置換する（PLAN §14.2）.

    ログ・成果物・公開物への全書き出し経路の必須通過点。
    秘密の一覧は Config.secrets（.env 由来）から渡す。
    """
    for s in secrets:
        if s and len(s) >= 8:  # 短すぎる値の置換は誤爆するため下限を設ける
            text = text.replace(s, "[REDACTED]")
    return text


class CallLogger:
    """全LLM呼び出しの記録（PLAN §1.1 再現性・§2.2 calls.jsonl）.

    1呼び出し = 1行のJSON。必須フィールド:
      ts, role, provider, model, params(temperature/max_tokens/logprobs/seed),
      prompt_hash, response_hash, usage, cost_usd
    本文はログに書かない（成果物側に残る）。ハッシュで照合する。
    書き出しは scrub_secrets を通すこと。

    施工: M0（受入テスト: tests/test_m0_acceptance.py::test_router_logs_every_call）
    """

    def __init__(self, path, secrets: Iterable[str] = ()) -> None:
        self.path = path
        self.secrets = tuple(secrets)

    def log(self, record: dict) -> None:
        raise NotImplementedError("M0: 施工対象")


class Router:
    """役割名 → プロバイダ/モデルの解決と呼び出し.

    必須機能（PLAN §2.1）: リトライ、レート制御、logprobs取得、ストリーミング、
    コスト集計、予算の事前照会（budget.precheck → 超過なら呼ばずに BudgetExceeded）、
    ローカルモデルのswap要求（core.local 経由）、全呼び出しの記録。

    役割が陪審（リスト宣言）の場合、call_jury() で全員に並行/時分割で問い、
    個別応答のリストを返す。合意への集約は critique 層の仕事であり Router はしない。

    施工: M0
    """

    def __init__(self, config, logger: CallLogger, budget) -> None:
        self.config = config
        self.logger = logger
        self.budget = budget

    def call(self, role: str, messages: Sequence[Message], **overrides) -> LLMResponse:
        raise NotImplementedError("M0: 施工対象")

    def call_jury(self, role: str, messages: Sequence[Message], **overrides) -> list[LLMResponse]:
        raise NotImplementedError("M0: 施工対象")
