"""ローカル推論基盤（PLAN §2.3）— RTX 3090 (24GB) 単機・llama-server + llama-swap.

設計上の制約:
- 27B〜31B Q4 の大型GGUFは同時に1つしか載らない（排他）。
- embedder + reranker（計~2GB）は常駐可。
- モデル交換コスト ≈ 数十秒。Loop は同一モデルのステップを束ねる（budgets.yaml
  の swap_cost_seconds を閾値としてスケジューラが判断する）。
- 「複数LLMの介在」はローカルでは時分割で実現し、真の並行陪審はAPI側（PLAN §2.3）。
"""
from __future__ import annotations

import httpx


class LocalRuntime:
    """llama-swap 経由のモデル常駐管理。施工: M0.

    受入テスト: tests/test_m0_acceptance.py::test_local_swap（要 ALEPH_LOCAL=1）

    llama-swap は OpenAI互換エンドポイントへのリクエストの "model" フィールドを見て
    自動的にバックエンドを交換する。ensure_model は、実際の処理リクエストより前に
    軽量な補完で対象モデルをpre-warmし、swapコスト（budgets.yaml: swap_cost_seconds）
    を呼び出し元の処理から切り離して吸収する（PLAN §2.3）。
    """

    def __init__(self, config, client: httpx.Client | None = None) -> None:
        self.config = config
        provider_cfg = config.models["providers"]["llamacpp"]
        self._base_url = provider_cfg["base_url"].rstrip("/")
        self._client = client or httpx.Client(timeout=180.0)
        self._resident: set[str] = set()

    def ensure_model(self, model: str) -> str:
        """指定GGUFがllama-serverに載っている状態を保証し、base_urlを返す.

        既に別の大型モデルが載っている場合はswapする。swap発生を呼び出し元に
        伝え、コスト計上（budget: local）すること。
        """
        if model not in self._resident:
            resp = self._client.post(
                f"{self._base_url}/chat/completions",
                json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
            resp.raise_for_status()
            # 排他ロード（PLAN §2.3: 27B〜31B Q4は同時に1つ）。常駐は最新のみ扱う。
            self._resident = {model}
        return self._base_url

    def resident_models(self) -> list[str]:
        return sorted(self._resident)
