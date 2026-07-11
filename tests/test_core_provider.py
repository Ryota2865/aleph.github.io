"""M2コア小修正の回帰テスト（PLAN_CHANGELOG 0.7.4-3/4）.

実行: pytest -m m2
AnthropicProviderのtemperature除去・refusal検査、Router._invokeの役割宣言pricingに
よる正確なコスト計上を固定する。
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from aleph.core.budget import Budget
from aleph.core.config import load_config
from aleph.core.llm import AnthropicProvider, CallLogger, LLMResponse, Message, Router, Usage

pytestmark = pytest.mark.m2

ROOT = Path(__file__).resolve().parents[1]


def _client_with_handler(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- AnthropicProvider
def test_anthropic_provider_omits_temperature():
    """claude-fable-5 / claude-opus-4-8 はtemperatureを送ると400になるため送らない."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
                "stop_reason": "end_turn",
            },
        )

    provider = AnthropicProvider(api_key="test-key", client=_client_with_handler(handler))
    provider.complete("claude-fake", [Message("user", "hi")], temperature=1.0)
    assert "temperature" not in captured["payload"]


def test_anthropic_provider_raises_on_refusal():
    """stop_reason=='refusal' はRuntimeErrorとして送出し、呼び出し側のフォールバックを促す."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [],
                "usage": {"input_tokens": 1, "output_tokens": 0},
                "stop_reason": "refusal",
                "stop_details": {"reason": "policy"},
            },
        )

    provider = AnthropicProvider(api_key="test-key", client=_client_with_handler(handler))
    with pytest.raises(RuntimeError, match="anthropic refusal"):
        provider.complete("claude-fake", [Message("user", "hi")])


# ---------------------------------------------------------------- Router pricing
class _FakeProvider:
    name = "fake"

    def complete(self, model, messages, **kw):
        return LLMResponse(
            text="ok",
            model=model,
            provider=self.name,
            usage=Usage(prompt_tokens=1000, completion_tokens=1000),
            cost_usd=0.0,
        )


def test_router_uses_role_pricing_for_cost(tmp_path, monkeypatch):
    """役割宣言のpricingがあれば実usageから正確なcost_usdを計上する（PLAN_CHANGELOG 0.7.4-4）."""
    cfg = load_config(ROOT)
    cfg.models["roles"]["_test_priced_role"] = {
        "provider": "anthropic",
        "model": "claude-fake",
        "pricing": {"input_per_mtok": 10.0, "output_per_mtok": 50.0},
    }
    logger = CallLogger(tmp_path / "calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg)
    router = Router(cfg, logger, budget)
    monkeypatch.setattr(router, "_provider_for_test", _FakeProvider(), raising=False)

    resp = router.call("_test_priced_role", [Message("user", "hi")])

    assert resp.cost_usd == pytest.approx(0.06)
    status = budget.status()
    assert status["api"]["spent"] == pytest.approx(0.06)


# ---------------------------------------------------------------- OpenAICompatProvider
def _openai_compat_captured_payload(name: str) -> dict:
    from aleph.core.llm import OpenAICompatProvider

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                "model": "m",
            },
        )

    provider = OpenAICompatProvider(
        base_url="http://test/v1", api_key="k", name=name,
        client=_client_with_handler(handler),
    )
    provider.complete("m", [Message("user", "hi")], max_tokens=64)
    return captured["payload"]


def test_openai_api_uses_max_completion_tokens():
    """gpt-5系従量APIは max_tokens を400で拒否する（w0001実ラン陪審の回帰）."""
    payload = _openai_compat_captured_payload("openai")
    assert payload.get("max_completion_tokens") == 64
    assert "max_tokens" not in payload


def test_llamacpp_keeps_max_tokens():
    """llama-server は従来どおり max_tokens を受け取る."""
    payload = _openai_compat_captured_payload("llamacpp")
    assert payload.get("max_tokens") == 64
    assert "max_completion_tokens" not in payload
