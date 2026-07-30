"""Preregistered w0009 publication-input shadow.

The public seam is :class:`PublicationShadow`: it validates the frozen
manifest, constructs both prompts, executes each slot once through an injected
adapter, and preserves raw evidence without touching the canonical work.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

from aleph.core.model_output import ModelOutput, parse_model_output
from aleph.core.llm import scrub_secrets


DEFAULT_MANIFEST = Path("works/w0009/publication_shadow/preregistration.json")
_INTENT_SCHEMA = {"publish": bool, "reason": str}
_SCHEMA_TEXT = '{"publish":"bool","reason":"str"}'


class PublicationShadowError(RuntimeError):
    """The preregistered shadow cannot be verified or executed."""


@dataclass(frozen=True)
class ShadowRequest:
    slot: str
    packet_id: str
    phase: str
    prompt: str
    prompt_sha256: str


@dataclass(frozen=True)
class ShadowCall:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    response_hash: str


class ShadowAdapter(Protocol):
    """External provider and budget adapter at the paid-call seam."""

    def reserve(self, shadow: "PublicationShadow") -> str: ...

    def call(self, request: ShadowRequest, *, reservation_id: str) -> ShadowCall: ...

    def settle(self, reservation_id: str) -> dict[str, Any]: ...


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _intent_prompt(audience: str, body: str) -> str:
    lines = [
        "以下の作品を公開するか判断してください。宛先と公開は別の判断です——",
        "自分に宛てて書いた作品であっても、他者が読むに値すると考えるなら公開しうる",
        "（自己宛ては非公開を意味しません）。逆に、まだ他者に見せるべきでないと考えるなら",
        "非公開を選んでよい。これは規則ではなくあなたの選択です。",
        "注記: ここでの「非公開」は「見えなくする」ことではありません。この作品は",
        "選んだ結果に関わらず、制作記録全体（基準書・決定ログ・草稿・査読）が",
        "このリポジトリの深層アーカイブとして残ります。ここで問うているのは、",
        "読者向けの完成品として提示するかどうかです。",
        f"想定読者配合: {audience}",
        "",
        "作品（抜粋）:",
        body,
        'JSON {"publish": true|false, "reason": "..."} で返してください。',
    ]
    return "\n".join(lines)


def _comparison_prompt(audience: str, shelf: list[str]) -> str:
    return (
        "以下の作品を公開するため、棚の既公開作と比較して、"
        "なぜ本作が公開に値するかを論述してください。\n\n"
        f"想定読者配合:\n{audience}\n\n"
        "棚の既公開作:\n"
        + ("\n".join(shelf) if shelf else "（既公開作なし）")
    )


def _parse_classification(output: ModelOutput) -> str:
    if output.ok:
        return "PARSED"
    warnings = output.warnings
    if any("duplicate JSON key" in warning for warning in warnings):
        return "DUPLICATE_KEY"
    if any("multiple JSON values" in warning for warning in warnings):
        return "MULTIPLE_JSON"
    if any("must be" in warning or "missing required fields" in warning for warning in warnings):
        return "SCHEMA_INVALID"
    return "NO_JSON"


class PublicationShadow:
    """Deep module for the one-pair preregistered comparison."""

    def __init__(self, root: Path, manifest_path: Path, manifest: dict[str, Any]) -> None:
        self.root = Path(root)
        self.manifest_path = Path(manifest_path)
        self.manifest = manifest
        self._bodies: dict[str, str] = {}
        self._prompts: dict[str, str] = {}
        self._comparison = ""
        self.verify()

    @classmethod
    def open(
        cls,
        root: Path,
        manifest_path: Path | None = None,
    ) -> "PublicationShadow":
        root = Path(root)
        path = root / (manifest_path or DEFAULT_MANIFEST)
        try:
            manifest = _read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            raise PublicationShadowError(f"cannot read preregistration: {path}") from exc
        if not isinstance(manifest, dict):
            raise PublicationShadowError("preregistration must be a JSON object")
        return cls(root, path, manifest)

    @property
    def experiment_id(self) -> str:
        return str(self.manifest["experiment_id"])

    @property
    def charged_to(self) -> str:
        return f"experiment:{self.experiment_id}"

    @property
    def reserve_usd(self) -> float:
        return float(self.manifest["budget_reserve"]["total_max_usd"])

    @property
    def manifest_sha256(self) -> str:
        return _sha256_bytes(self.manifest_path.read_bytes())

    @property
    def expected_slots(self) -> tuple[str, ...]:
        slots: list[str] = []
        for packet_id in self.manifest["blind"]["order"]:
            slots.extend((f"{packet_id}:intent", f"{packet_id}:shelf_comparison"))
        return tuple(slots)

    def verify(self) -> dict[str, Any]:
        m = self.manifest
        if (
            m.get("schema_version") != 1
            or m.get("status") != "preregistered_not_run"
            or m.get("experiment_id") != "exp-w0009-publication-input-shadow-v1"
        ):
            raise PublicationShadowError("unexpected preregistration identity or status")

        stimulus = m["stimulus"]
        source = self.root / stimulus["source"]
        try:
            full = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise PublicationShadowError(f"cannot read frozen stimulus: {source}") from exc
        excerpt = full[:4000] + "\n……\n" + full[-2000:]
        omitted = full[4000:-2000]
        self._assert_text_identity("full", full, stimulus, prefix="full")
        self._assert_text_identity("excerpt", excerpt, stimulus, prefix="excerpt")
        if (
            len(omitted) != int(stimulus["omitted_chars"])
            or _sha256_text(omitted) != stimulus["omitted_sha256"]
        ):
            raise PublicationShadowError("omitted middle identity drift")

        trajectory = self.root / "works/w0009/reviews/trajectory.jsonl"
        if _sha256_bytes(trajectory.read_bytes()) != stimulus["trajectory_sha256"]:
            raise PublicationShadowError("trajectory identity drift")
        rows = [
            json.loads(line)
            for line in trajectory.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        best = max(rows, key=lambda row: float(row.get("mean_score", 0.0)))
        if (
            int(best["version"]) != int(stimulus["selected_version"])
            or not math.isclose(
                float(best["mean_score"]),
                float(stimulus["selected_mean_score"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise PublicationShadowError("selected draft no longer follows preregistered rule")

        fixed = m["fixed_context"]
        publication_gate = self.root / "aleph/meta/publication_gate.py"
        if (
            not publication_gate.exists()
            or _sha256_bytes(publication_gate.read_bytes())
            != fixed["publication_gate_sha256"]
        ):
            raise PublicationShadowError("publication gate identity drift")
        shelf = list(fixed["shelf_summaries"])
        actual_shelf = []
        for path in sorted((self.root / "works").glob("*/final/meta.json")):
            meta = _read_json(path)
            actual_shelf.append(str(meta.get("title", path.parent.parent.name)))
        if actual_shelf != shelf or _sha256_text("\n".join(shelf)) != fixed["shelf_sha256"]:
            raise PublicationShadowError("shelf summary identity drift")

        checkpoint = _read_json(self.root / "works/w0009/checkpoint.json")
        if checkpoint.get("state") != m["baseline"]["work_state"]:
            raise PublicationShadowError("w0009 lifecycle drift")
        self._verify_baseline_files()

        model_path = self.root / "config/models.yaml"
        pricing_identity = str(m["model"]["pricing_version"])
        model_hash = _sha256_bytes(model_path.read_bytes())
        if f"sha256:{model_hash}" not in pricing_identity:
            raise PublicationShadowError("model pricing identity drift")
        from aleph.core.config import load_config

        config = load_config(self.root)
        role = config.models["roles"][m["model"]["role"]]
        expected_role = {
            "provider": m["model"]["provider"],
            "model": m["model"]["model"],
            "max_tokens": m["model"]["max_tokens"],
            "pricing": {
                "input_per_mtok": m["model"]["input_usd_per_mtok"],
                "output_per_mtok": m["model"]["output_usd_per_mtok"],
            },
        }
        for key, expected in expected_role.items():
            if role.get(key) != expected:
                raise PublicationShadowError(f"author role identity drift: {key}")
        if "temperature" in role or m["model"]["temperature"] is not None:
            raise PublicationShadowError("author temperature identity drift")

        if _sha256_text(_SCHEMA_TEXT) != m["schema"]["sha256"]:
            raise PublicationShadowError("schema identity drift")

        packet_by_body = {packet["body"]: packet for packet in m["packets"]}
        for body_name, body in (("excerpt", excerpt), ("full", full)):
            packet = packet_by_body[body_name]
            prompt = _intent_prompt(fixed["audience"], body)
            if (
                len(prompt) != int(packet["intent_prompt_chars"])
                or len(prompt.encode("utf-8")) != int(packet["intent_prompt_utf8_bytes"])
                or _sha256_text(prompt) != packet["intent_prompt_sha256"]
            ):
                raise PublicationShadowError(f"{body_name} intent prompt identity drift")
            packet_id = str(packet["packet_id"])
            self._bodies[packet_id] = body
            self._prompts[packet_id] = prompt

        order = list(m["blind"]["order"])
        if set(order) != set(self._prompts) or len(order) != len(set(order)):
            raise PublicationShadowError("blind packet order is invalid")

        comparison = _comparison_prompt(fixed["audience"], shelf)
        compare_spec = m["shelf_comparison"]
        if (
            len(comparison) != int(compare_spec["prompt_chars"])
            or len(comparison.encode("utf-8")) != int(compare_spec["prompt_utf8_bytes"])
            or _sha256_text(comparison) != compare_spec["prompt_sha256"]
        ):
            raise PublicationShadowError("shelf comparison prompt identity drift")
        self._comparison = comparison

        slots = m["budget_reserve"]["slots"]
        derived = math.fsum(float(slot["max_usd"]) for slot in slots)
        if not math.isclose(derived, self.reserve_usd, rel_tol=0.0, abs_tol=1e-12):
            raise PublicationShadowError("budget reserve total is not derived from slots")
        return {
            "experiment_id": self.experiment_id,
            "manifest_sha256": self.manifest_sha256,
            "packet_count": len(order),
            "reserve_usd": self.reserve_usd,
            "status": "VERIFIED_NOT_RUN",
        }

    @staticmethod
    def _assert_text_identity(
        label: str,
        text: str,
        stimulus: dict[str, Any],
        *,
        prefix: str,
    ) -> None:
        if (
            len(text) != int(stimulus[f"{prefix}_chars"])
            or len(text.encode("utf-8")) != int(stimulus[f"{prefix}_utf8_bytes"])
            or _sha256_text(text) != stimulus[f"{prefix}_sha256"]
        ):
            raise PublicationShadowError(f"{label} stimulus identity drift")

    def _verify_baseline_files(self) -> None:
        paths = {
            "checkpoint_sha256": self.root / "works/w0009/checkpoint.json",
            "decisions_sha256": self.root / "works/w0009/decisions.jsonl",
            "calls_sha256": self.root / "works/w0009/calls.jsonl",
        }
        for key, path in paths.items():
            if _sha256_bytes(path.read_bytes()) != self.manifest["baseline"][key]:
                raise PublicationShadowError(f"canonical w0009 file drift: {path.name}")

    def execution_blockers(self, *, today: date | None = None) -> tuple[str, ...]:
        from aleph.core.config import load_config

        current = today or date.today()
        config = load_config(self.root)
        reserve = self.manifest["budget_reserve"]
        blockers = []
        if current < date.fromisoformat(str(reserve["earliest_run_date"])):
            blockers.append("earliest run date has not arrived")
        if float(config.budgets["api"]["usd_per_month"]) != float(
            reserve["required_monthly_api_cap_usd"]
        ):
            blockers.append("monthly API cap is not the preregistered 45 USD")
        if int(config.budgets["publish"]["max_per_month"]) != 4:
            blockers.append("publish.max_per_month is not the preregistered value 4")
        return tuple(blockers)

    def run(
        self,
        adapter: ShadowAdapter,
        *,
        output_dir: Path | None = None,
        today: date | None = None,
        secrets: Iterable[str] = (),
        execution_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.verify()
        blockers = self.execution_blockers(today=today)
        if blockers:
            raise PublicationShadowError("execution is blocked: " + "; ".join(blockers))
        output = Path(output_dir or self.root / "works/w0009/publication_shadow/results")
        if output.exists():
            raise PublicationShadowError(f"shadow result path already exists: {output}")

        reservation_id = adapter.reserve(self)
        started = datetime.now(timezone.utc).isoformat()
        observations: list[dict[str, Any]] = []
        status = "COMPLETE_AWAITING_BLIND_ANALYSIS"
        failure: dict[str, str] | None = None
        settlement: dict[str, Any] | None = None
        try:
            # Create the durable attempt marker before the first provider call. A crash after
            # reservation cannot silently turn a later invocation into an unrecorded retry.
            _atomic_write_json(
                output / "attempt.json",
                {
                    "experiment_id": self.experiment_id,
                    "manifest_sha256": self.manifest_sha256,
                    "started_at": started,
                    "reservation_id": reservation_id,
                    "attempts_per_slot": 1,
                    "execution_evidence": execution_evidence,
                },
            )
            # Complete the paired primary observation before any conditional secondary call.
            for packet_id in self.manifest["blind"]["order"]:
                intent_request = ShadowRequest(
                    slot=f"{packet_id}:intent",
                    packet_id=packet_id,
                    phase="intent",
                    prompt=self._prompts[packet_id],
                    prompt_sha256=_sha256_text(self._prompts[packet_id]),
                )
                intent = self._call_and_record(
                    adapter,
                    intent_request,
                    reservation_id=reservation_id,
                    output=output,
                    secrets=secrets,
                )
                parsed = parse_model_output(intent.text, schema=_INTENT_SCHEMA, fail_closed=True)
                observation = self._intent_observation(
                    packet_id,
                    intent_request.prompt_sha256,
                    intent,
                    parsed,
                )
                observations.append(observation)
            for observation in observations:
                packet_id = str(observation["packet_id"])
                if observation["decision"] == "PUBLISH":
                    comparison_request = ShadowRequest(
                        slot=f"{packet_id}:shelf_comparison",
                        packet_id=packet_id,
                        phase="shelf_comparison",
                        prompt=self._comparison,
                        prompt_sha256=_sha256_text(self._comparison),
                    )
                    comparison = self._call_and_record(
                        adapter,
                        comparison_request,
                        reservation_id=reservation_id,
                        output=output,
                        secrets=secrets,
                    )
                    observation["shelf_comparison"] = {
                        "status": "RECORDED_UNSCORED",
                        "response_sha256": comparison.response_hash,
                        "usage": {
                            "prompt_tokens": comparison.prompt_tokens,
                            "completion_tokens": comparison.completion_tokens,
                        },
                        "cost_usd": comparison.cost_usd,
                        "latency_ms": comparison.latency_ms,
                    }
                else:
                    observation["shelf_comparison"] = {"status": "NOT_TRIGGERED"}
        except Exception as exc:
            status = "INCOMPLETE_CALL_FAILURE"
            failure = {
                "type": type(exc).__name__,
                "message": scrub_secrets(str(exc), secrets),
            }
        finally:
            try:
                settlement = adapter.settle(reservation_id)
            except Exception as exc:
                status = "INCOMPLETE_UNRECONCILED"
                failure = {
                    "type": type(exc).__name__,
                    "message": scrub_secrets(str(exc), secrets),
                }

        try:
            self._verify_baseline_files()
            canonical_immutability = "PASS"
        except PublicationShadowError as exc:
            canonical_immutability = "FAIL"
            status = "INCOMPLETE_IMMUTABILITY_VIOLATION"
            failure = {"type": type(exc).__name__, "message": str(exc)}

        result = {
            "experiment_id": self.experiment_id,
            "manifest_sha256": self.manifest_sha256,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "reservation_id": reservation_id,
            "settlement": settlement,
            "canonical_immutability": canonical_immutability,
            "observations": observations,
            "totals": self._totals(observations),
            "provider_reconciliation": "UNAVAILABLE_PENDING_BEST_EFFORT",
            "failure": failure,
            "selection": "PENDING_BLIND_MIDDLE_ANNOTATION",
            "execution_evidence": execution_evidence,
        }
        _atomic_write_json(output / "observations.json", result)
        _atomic_write_json(
            output / "blind_middle_annotation_packet.json",
            self._blind_annotation_packet(observations),
        )
        return result

    @staticmethod
    def _intent_observation(
        packet_id: str,
        prompt_sha256: str,
        call: ShadowCall,
        parsed: ModelOutput,
    ) -> dict[str, Any]:
        value = parsed.value if parsed.ok else None
        return {
            "packet_id": packet_id,
            "intent_prompt_sha256": prompt_sha256,
            "intent_response_sha256": call.response_hash,
            "parser": {
                "ok": parsed.ok,
                "classification": _parse_classification(parsed),
                "fragment": parsed.fragment,
                "source_span": list(parsed.source_span) if parsed.source_span else None,
                "warnings": list(parsed.warnings),
            },
            "decision": (
                "PUBLISH"
                if value is not None and value["publish"] is True
                else "SHELVE"
                if value is not None
                else "PARSE_INCOMPLETE"
            ),
            "reason": value["reason"].strip() if value is not None else None,
            "middle_annotation": {
                "middle_reference": "PENDING",
                "decision_relevant": "PENDING",
                "response_quote": None,
                "source_quote": None,
                "source_span_python_chars": None,
            },
            "usage": {
                "prompt_tokens": call.prompt_tokens,
                "completion_tokens": call.completion_tokens,
            },
            "cost_usd": call.cost_usd,
            "latency_ms": call.latency_ms,
            "provider": call.provider,
            "model": call.model,
        }

    def _blind_annotation_packet(
        self,
        observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stimulus = self.manifest["stimulus"]
        return {
            "experiment_id": self.experiment_id,
            "mapping_disclosed": False,
            "instructions": (
                "Do not inspect preregistration.json before fixing both annotations. "
                "Use designs/w0009-publication-input-shadow-preregistration.md section 5."
            ),
            "source": stimulus["source"],
            "source_sha256": stimulus["full_sha256"],
            "omitted_source_span_python_chars": stimulus[
                "omitted_source_span_python_chars"
            ],
            "items": [
                {
                    "packet_id": row["packet_id"],
                    "parse_status": row["parser"]["classification"],
                    "decision": row["decision"],
                    "reason": row["reason"],
                    "middle_reference": "PENDING",
                    "decision_relevant": "PENDING",
                    "response_quote": None,
                    "source_quote": None,
                    "source_span_python_chars": None,
                }
                for row in observations
            ],
        }

    @staticmethod
    def _totals(observations: list[dict[str, Any]]) -> dict[str, float | int]:
        prompt_tokens = 0
        completion_tokens = 0
        cost_usd = 0.0
        latency_ms = 0.0
        calls = 0
        for row in observations:
            usage = row["usage"]
            prompt_tokens += int(usage["prompt_tokens"])
            completion_tokens += int(usage["completion_tokens"])
            cost_usd += float(row["cost_usd"])
            latency_ms += float(row["latency_ms"])
            calls += 1
            comparison = row.get("shelf_comparison", {})
            if comparison.get("status") == "RECORDED_UNSCORED":
                usage = comparison["usage"]
                prompt_tokens += int(usage["prompt_tokens"])
                completion_tokens += int(usage["completion_tokens"])
                cost_usd += float(comparison["cost_usd"])
                latency_ms += float(comparison["latency_ms"])
                calls += 1
        return {
            "calls": calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": round(cost_usd, 6),
            "latency_ms": latency_ms,
        }

    @staticmethod
    def _call_and_record(
        adapter: ShadowAdapter,
        request: ShadowRequest,
        *,
        reservation_id: str,
        output: Path,
        secrets: Iterable[str],
    ) -> ShadowCall:
        before = time.monotonic()
        call = adapter.call(request, reservation_id=reservation_id)
        elapsed_ms = (time.monotonic() - before) * 1000
        text = scrub_secrets(str(call.text), secrets)
        response_hash = _sha256_text(text)
        normalized = ShadowCall(
            text=text,
            provider=call.provider,
            model=call.model,
            prompt_tokens=int(call.prompt_tokens),
            completion_tokens=int(call.completion_tokens),
            cost_usd=float(call.cost_usd),
            latency_ms=float(call.latency_ms if call.latency_ms >= 0 else elapsed_ms),
            response_hash=response_hash,
        )
        _atomic_write_text(
            output / "responses" / f"{request.packet_id}-{request.phase}.txt",
            normalized.text,
        )
        return normalized
