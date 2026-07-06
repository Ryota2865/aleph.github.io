"""ローカル推論基盤（PLAN §2.3）— RTX 3090 (24GB) 単機・llama-server + llama-swap.

設計上の制約:
- 27B〜31B Q4 の大型GGUFは同時に1つしか載らない（排他）。
- embedder + reranker（計~2GB）は常駐可。
- モデル交換コスト ≈ 数十秒。Loop は同一モデルのステップを束ねる（budgets.yaml
  の swap_cost_seconds を閾値としてスケジューラが判断する）。
- 「複数LLMの介在」はローカルでは時分割で実現し、真の並行陪審はAPI側（PLAN §2.3）。
"""
from __future__ import annotations


class LocalRuntime:
    """llama-swap 経由のモデル常駐管理。施工: M0.

    受入テスト: tests/test_m0_acceptance.py::test_local_swap（要 ALEPH_LOCAL=1）
    """

    def __init__(self, config) -> None:
        self.config = config

    def ensure_model(self, model: str) -> str:
        """指定GGUFがllama-serverに載っている状態を保証し、base_urlを返す.

        既に別の大型モデルが載っている場合はswapする。swap発生を呼び出し元に
        伝え、コスト計上（budget: local）すること。
        """
        raise NotImplementedError("M0: 施工対象")

    def resident_models(self) -> list[str]:
        raise NotImplementedError("M0: 施工対象")
