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
import json
import subprocess
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol, Sequence

import httpx


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
        text = json.dumps(record, ensure_ascii=False, sort_keys=True)
        text = scrub_secrets(text, self.secrets)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


class Router:
    """役割名 → プロバイダ/モデルの解決と呼び出し.

    必須機能（PLAN §2.1）: リトライ、レート制御、logprobs取得、ストリーミング、
    コスト集計、予算の事前照会（budget.precheck → 超過なら呼ばずに BudgetExceeded）、
    ローカルモデルのswap要求（core.local 経由）、全呼び出しの記録。

    役割が陪審（リスト宣言）の場合、call_jury() で全員に並行/時分割で問い、
    個別応答のリストを返す。合意への集約は critique 層の仕事であり Router はしない。

    施工: M0
    """

    def __init__(self, config, logger: CallLogger, budget, local_runtime=None) -> None:
        self.config = config
        self.logger = logger
        self.budget = budget
        self.local_runtime = local_runtime
        self._providers: dict[tuple[str, str | None], "Provider"] = {}
        harness_concurrency = int(config.budgets.get("harness", {}).get("concurrent", 1))
        self._harness_sem = threading.Semaphore(max(1, harness_concurrency))

    # -- 役割解決 ----------------------------------------------------------
    def _role_decls(self, role: str) -> list[dict]:
        try:
            decl = self.config.models["roles"][role]
        except KeyError as exc:
            raise RouterError(f"unknown role: {role}") from exc
        return decl if isinstance(decl, list) else [decl]

    def _ledger_for(self, provider_name: str) -> str:
        if provider_name == "local":
            return "local"
        providers = self.config.models.get("providers", {})
        try:
            return providers[provider_name]["kind"]
        except KeyError as exc:
            raise RouterError(f"unknown provider: {provider_name}") from exc

    def _provider_instance(self, decl: dict) -> "Provider":
        fake = getattr(self, "_provider_for_test", None)
        if fake is not None:
            return fake
        provider_name = decl["provider"]
        cache_key = (provider_name, decl.get("cli"))
        if cache_key not in self._providers:
            self._providers[cache_key] = build_provider(provider_name, decl, self.config)
        return self._providers[cache_key]

    @staticmethod
    def _charge_amount(ledger: str, resp: LLMResponse) -> float:
        if ledger == "api":
            return resp.cost_usd
        if ledger == "harness":
            return 1.0  # calls_per_day 単位。GPU時間はLocalRuntimeが別途計上
        return 0.0

    @staticmethod
    def _precheck_amount(ledger: str, provider_name: str, messages: Sequence[Message], kwargs: dict) -> float:
        """呼び出し前に予見できる消費見積り（PLAN §2.1: 超過が予見される呼び出しは実行前に拒否）.

        api は実費が応答後にしか確定しないため、プロンプト長と max_tokens から
        概算する（実費との差は charge() 時点で真値に置き換わる）。harness は
        1呼び出し=1件で確定しているので厳密。local はGPU時間をRouterでは計上しない。
        """
        if ledger == "harness":
            return 1.0
        if ledger == "api":
            prompt_chars = sum(len(m.content) for m in messages)
            est_prompt_tokens = max(1, prompt_chars // 4)
            est_completion_tokens = kwargs.get("max_tokens") or 1024
            usage = Usage(prompt_tokens=est_prompt_tokens, completion_tokens=est_completion_tokens)
            return _estimate_cost(provider_name, usage)
        return 0.0

    # -- 呼び出し ------------------------------------------------------------
    def _invoke(self, role: str, decl: dict, messages: Sequence[Message], **overrides) -> LLMResponse:
        # work_id はBudgetの作品別サブ台帳（usd_per_work）を通す経路。プロバイダへは渡さない
        # （Codex監査 finding: Router.callがwork_idを一切伝播しておらず、作品別上限が
        # 事実上機能していなかった）。
        work_id = overrides.pop("work_id", None)
        provider_name = decl["provider"]
        model = decl.get("model") or decl.get("cli") or provider_name
        ledger = self._ledger_for(provider_name)

        kwargs = {
            "temperature": overrides.pop("temperature", decl.get("temperature", 1.0)),
            "max_tokens": overrides.pop("max_tokens", decl.get("max_tokens")),
            "logprobs": overrides.pop("logprobs", decl.get("logprobs", False)),
            "seed": overrides.pop("seed", None),
        }
        kwargs.update(overrides)

        self.budget.precheck(
            ledger, self._precheck_amount(ledger, provider_name, messages, kwargs), work_id=work_id
        )

        using_fake = getattr(self, "_provider_for_test", None) is not None
        if not using_fake and ledger == "local" and self.local_runtime is not None:
            self.local_runtime.ensure_model(model)  # swap要求（PLAN §2.3）

        provider = self._provider_instance(decl)

        lock = self._harness_sem if ledger == "harness" else nullcontext()
        last_err: Exception | None = None
        with lock:
            resp = None
            for attempt in range(3):
                try:
                    resp = provider.complete(model, messages, **kwargs)
                    break
                except Exception as exc:  # リトライ（PLAN §2.1）
                    last_err = exc
                    if attempt == 2:
                        raise
                    time.sleep(min(2**attempt, 5))
        assert resp is not None  # ループは break か raise のいずれかで抜ける

        self.budget.charge(ledger, self._charge_amount(ledger, resp), work_id=work_id)

        prompt_text = "\n".join(f"{m.role}:{m.content}" for m in messages)
        response_hash = resp.response_hash or sha256_text(resp.text)
        self.logger.log(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "provider": resp.provider,
                "model": resp.model,
                "params": kwargs,
                "prompt_hash": sha256_text(prompt_text),
                "response_hash": response_hash,
                "usage": {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                },
                "cost_usd": resp.cost_usd,
            }
        )
        return resp

    def call(self, role: str, messages: Sequence[Message], **overrides) -> LLMResponse:
        decls = self._role_decls(role)
        if len(decls) != 1:
            raise RouterError(f"role {role!r} is a jury (multiple providers); use call_jury()")
        return self._invoke(role, decls[0], messages, **overrides)

    def call_jury(self, role: str, messages: Sequence[Message], **overrides) -> list[LLMResponse]:
        decls = self._role_decls(role)
        return [self._invoke(role, decl, messages, **overrides) for decl in decls]


class RouterError(Exception):
    pass


# ---------------------------------------------------------------- プロバイダ実装
_PROVIDER_USD_PER_1K_TOKENS = {
    # 実額はモデルごとに異なるが、モデル名をコードに直書きしないため（設計不変条件）
    # プロバイダ単位の概算レートで代用する。厳密なコスト集計はプロバイダのAPI応答
    # (該当すれば)や請求実績で校正すること。
    "anthropic": 0.006,
    "openai": 0.006,
}


def _estimate_cost(provider_name: str, usage: Usage) -> float:
    rate = _PROVIDER_USD_PER_1K_TOKENS.get(provider_name)
    if rate is None:
        return 0.0
    total_tokens = usage.prompt_tokens + usage.completion_tokens
    return round(total_tokens / 1000 * rate, 6)


def _parse_openai_logprobs(raw: dict | None) -> tuple[TokenLogprob, ...] | None:
    if not raw or not raw.get("content"):
        return None
    out = []
    for item in raw["content"]:
        alts = tuple((a["token"], a["logprob"]) for a in item.get("top_logprobs", []) or [])
        out.append(TokenLogprob(token=item["token"], logprob=item["logprob"], top_alternatives=alts))
    return tuple(out)


class AnthropicProvider:
    """Anthropic Messages API アダプタ."""

    name = "anthropic"
    api_url = "https://api.anthropic.com/v1/messages"
    api_version = "2023-06-01"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=120.0)

    def complete(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        logprobs: bool = False,
        seed: int | None = None,
        stream: bool = False,
        **_ignored,
    ) -> LLMResponse:
        system = "\n".join(m.content for m in messages if m.role == "system") or None
        turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        payload: dict = {
            "model": model,
            "messages": turns,
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.api_version,
            "content-type": "application/json",
        }
        resp = self._client.post(self.api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage_raw = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_raw.get("input_tokens", 0),
            completion_tokens=usage_raw.get("output_tokens", 0),
        )
        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            usage=usage,
            cost_usd=_estimate_cost(self.name, usage),
            response_hash=sha256_text(text),
        )


class OpenAICompatProvider:
    """OpenAI互換 chat/completions アダプタ（従量API・llama-server 兼用. PLAN §2.1）."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        name: str = "openai",
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=120.0)

    def complete(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        logprobs: bool = False,
        seed: int | None = None,
        stream: bool = False,
        **_ignored,
    ) -> LLMResponse:
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 5
        if seed is not None:
            payload["seed"] = seed
        headers = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        resp = self._client.post(f"{self._base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage_raw = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
        )
        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            usage=usage,
            cost_usd=_estimate_cost(self.name, usage),
            logprobs=_parse_openai_logprobs(choice.get("logprobs")),
            response_hash=sha256_text(text),
        )


class HarnessProvider:
    """OAuthサブスクCLIの非対話モードを包むアダプタ（PLAN §14.1）.

    控えめ運用（低頻度・人間起動のバッチ、無人常駐デーモン化しない。PLAN §15-1）を
    前提とし、Router側の harness セマフォ・低頻度ロールへの限定でレートを抑える。
    """

    def __init__(self, cli: str, timeout: float = 300.0) -> None:
        self.name = "harness"
        self._cli = cli
        self._timeout = timeout

    def _build_command(self, prompt: str) -> list[str]:
        if self._cli == "claude-code":
            return ["claude", "-p", prompt]
        if self._cli == "codex":
            return ["codex", "exec", prompt]
        raise RouterError(f"unknown harness cli: {self._cli}")

    def complete(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        temperature: float = 1.0,
        max_tokens: int | None = None,
        logprobs: bool = False,
        seed: int | None = None,
        stream: bool = False,
        **_ignored,
    ) -> LLMResponse:
        prompt = "\n\n".join(f"[{m.role}] {m.content}" for m in messages)
        cmd = self._build_command(prompt)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"harness {self._cli} failed: {proc.stderr.strip()[:500]}")
        text = proc.stdout.strip()
        usage = Usage(prompt_tokens=0, completion_tokens=0)
        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            usage=usage,
            cost_usd=0.0,
            response_hash=sha256_text(text),
        )


def build_provider(provider_name: str, decl: dict, config) -> "Provider":
    """役割宣言からプロバイダインスタンスを組み立てる（PLAN §2.1 3プロバイダ + harness）."""
    if provider_name == "harness":
        cli = decl["cli"]
        harness_policy = config.policies.get("harness", {})
        if not harness_policy.get("enabled", False):
            raise RouterError(
                "harness is disabled by policy (config/policies.yaml: harness.enabled=false). "
                "PLAN §15-1: 利用規約適合を人間が確認し明示的に有効化するまで拒否する。"
            )
        if not harness_policy.get("cli_tos_ack", {}).get(cli, False):
            raise RouterError(
                f"harness cli {cli!r} not acknowledged (config/policies.yaml: harness.cli_tos_ack.{cli}=false)"
            )
        return HarnessProvider(cli=cli)
    if provider_name == "local":
        raise RouterError("provider 'local' (embedder/reranker) はRouter.call経由の対象外")

    providers_cfg = config.models.get("providers", {})
    provider_cfg = providers_cfg.get(provider_name)
    if provider_cfg is None:
        raise RouterError(f"unknown provider: {provider_name}")
    kind = provider_cfg["kind"]

    if kind == "api":
        api_key = config.secrets.get(provider_cfg.get("api_key_env", ""), "")
        base_url = provider_cfg.get("base_url", "https://api.openai.com/v1")
        if provider_name == "anthropic":
            return AnthropicProvider(api_key=api_key)
        return OpenAICompatProvider(base_url=base_url, api_key=api_key, name=provider_name)

    if kind == "local":
        return OpenAICompatProvider(base_url=provider_cfg["base_url"], api_key=None, name=provider_name)

    raise RouterError(f"unsupported provider kind: {kind}")
