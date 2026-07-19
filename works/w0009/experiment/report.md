# w0009 report
date_utc: 2026-07-19
decision: RULE_4_LEVEL_SPLIT_OR_MIXED
L4の3案とL5の疑似セクションは独立標本ではない。統計的検定、有意差、p値として解釈しない。

## input hashes
seed_hash: 0053ea712b1a38b1c8ac1e0fe07e913c0fd36be87e506de40a1d1e35edd4e10f
poetics_hash: 02a8fca078b713ac550df9aaf8d7883450c9fd32c53890d5b5efcff1c48063f1
config_hash: fcb1b2c884134260d9f493eb396f78d6b4464cc5f4838c3a98ccdadd7268e315
atlas_identity: {"atlas_meta_hash": "c02b2f542da21a24dec0aac9111fba1aa79d38570bb15c8a0705e1b1ad48b160", "index": "state/atlas", "manifest_hash": "12f987177369f5552587d6ff9fd871a9d921188ca98dcbce5823e5a15d046e22"}

## packet/effective hashes
{
  "era_pinned": {
    "effective_constraints_hash": "2a42c728906152549fbd074c8fb4c03916ead086ecd2a3e21a44f09580dea346",
    "packet_hash": "1ce67789cd2428744cb6e795614a8661c490b0bdd34450ec1c87ccd689557329"
  },
  "era_unpinned": {
    "effective_constraints_hash": "2a42c728906152549fbd074c8fb4c03916ead086ecd2a3e21a44f09580dea346",
    "packet_hash": "eea9ff9c7bb90ce47fbeb8b18868e08ad2ae9b2a89f8dc9c018dc87b6499e08f"
  }
}

## classification
{
  "era_pinned": {
    "L4": {
      "classified": 3,
      "marker_rates": {
        "aphoristic_voice": 0.3333333333333333,
        "backstage_world": 1.0,
        "era_taisho_showa": 0.0,
        "perspective_deviation": 1.0,
        "quotation_transform": 0.3333333333333333
      },
      "observed": 3,
      "unclassified": 0
    },
    "L5": {
      "classified": 17,
      "marker_rates": {
        "aphoristic_voice": 0.5882352941176471,
        "backstage_world": 1.0,
        "era_taisho_showa": 0.29411764705882354,
        "perspective_deviation": 0.9411764705882353,
        "quotation_transform": 0.29411764705882354
      },
      "observed": 17,
      "unclassified": 0
    }
  },
  "era_unpinned": {
    "L4": {
      "classified": 3,
      "marker_rates": {
        "aphoristic_voice": 0.0,
        "backstage_world": 1.0,
        "era_taisho_showa": 0.3333333333333333,
        "perspective_deviation": 1.0,
        "quotation_transform": 1.0
      },
      "observed": 3,
      "unclassified": 0
    },
    "L5": {
      "classified": 17,
      "marker_rates": {
        "aphoristic_voice": 0.9411764705882353,
        "backstage_world": 1.0,
        "era_taisho_showa": 0.11764705882352941,
        "perspective_deviation": 0.9411764705882353,
        "quotation_transform": 0.17647058823529413
      },
      "observed": 17,
      "unclassified": 0
    }
  }
}

## jury disclosure
{
  "blind_choice_matched_jury_argmax": false,
  "jury_argmax": null,
  "rows": [
    {
      "arm": "era_unpinned",
      "call_evidence": [
        {
          "call_id": "adc6853d-a73e-4b40-b1cc-ed6bffc9fc58",
          "charge_id": "4dfc39f1-b01a-4099-a94b-6bc3f3d9c605",
          "model": "claude-opus-4-8",
          "response_hash": "1a3c9acb575f6e13727632097279c86b0ae872b69dbceb0f7e6b59f4d9dca8fe"
        },
        {
          "call_id": "7779839c-bea1-4edd-a514-372b187f9cd7",
          "charge_id": "13bea900-4835-4303-8f05-eb847093cc48",
          "model": "gpt-5.5",
          "response_hash": "d18c4c2733474f79f818787a9a8b374c4779b687aa0b6e7fc7493e7c0dca4bb9"
        },
        {
          "call_id": "820892b4-1a75-4583-a9e0-0c28864791ef",
          "charge_id": "03b102fa-c9b2-4560-a046-5cb4ee49119f",
          "model": "Qwen3.6-27B-Q4_K_M",
          "response_hash": "84ff24715c895b5d81d9dee5d451699fb1095795ae575eabc10b173bd520b9e6"
        }
      ],
      "disagreement": null,
      "effective_constraints_hash": "2a42c728906152549fbd074c8fb4c03916ead086ecd2a3e21a44f09580dea346",
      "mean_score": null,
      "packet_hash": "eea9ff9c7bb90ce47fbeb8b18868e08ad2ae9b2a89f8dc9c018dc87b6499e08f",
      "rationales": [],
      "reveal_event_id": "exp-w0009-l2-era-pin:000009",
      "scores": [],
      "status": "INCOMPLETE_PARSE"
    },
    {
      "arm": "era_pinned",
      "call_evidence": [
        {
          "call_id": "d7823d60-af46-4542-ad31-fc16fa403880",
          "charge_id": "ffa2c5aa-5c6d-4827-839b-5a170dcc7b7a",
          "model": "claude-opus-4-8",
          "response_hash": "2bfb5b636bd230d078271863d8f6dba9d9be44a37f93f0e481caf1093d5e7cf2"
        },
        {
          "call_id": "b414cd57-43cd-4b6d-9874-f5b584e625ae",
          "charge_id": "ee316b36-94ca-4010-aad1-2532112276ff",
          "model": "gpt-5.5",
          "response_hash": "a33edde3afd1bc4201e7615f52780d3a28510634f0cdcbcb1d40b738a108406c"
        },
        {
          "call_id": "455551fc-dc1c-4d33-a1c0-6478b24443e0",
          "charge_id": "11e3a980-6a9c-41a9-96b8-445765aac1f2",
          "model": "Qwen3.6-27B-Q4_K_M",
          "response_hash": "cb308ac8ecff4777b1b1a68b8e4c8b831a1af264cc2bdfbdd552b79d56c0e161"
        }
      ],
      "disagreement": null,
      "effective_constraints_hash": "2a42c728906152549fbd074c8fb4c03916ead086ecd2a3e21a44f09580dea346",
      "mean_score": null,
      "packet_hash": "1ce67789cd2428744cb6e795614a8661c490b0bdd34450ec1c87ccd689557329",
      "rationales": [],
      "reveal_event_id": "exp-w0009-l2-era-pin:000009",
      "scores": [],
      "status": "INCOMPLETE_PARSE"
    }
  ]
}

## deviations
[
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "9153e8c16de3e5243094e87963fe8ac361af806c91abed07b67037b9cd3e3a66",
    "event_id": "exp-w0009-l2-era-pin:000001",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: phase allocation changes or mismatches require a deviation event before the next paid call",
    "previous_hash": null,
    "reason": "prepare intent call was durably logged as phase L1 because RealDeps.choose_intent overwrote the preregistered prepare phase; preserve the charged call and normalize experiment phase provenance before the next provider call",
    "ts": "2026-07-19T06:43:22.277490+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "7ba804684127eb44157a1f17d3dde5fcdf098eddd2e852272e0bc83f2015d0da",
    "event_id": "exp-w0009-l2-era-pin:000003",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: crash resume may reuse only matching immutable inputs and existing artifacts; all call/charge provenance must remain explicit",
    "previous_hash": "8bf56ab5baf0becd3983c5315ab83193f44e9e0d04cf6dfd7c50bcac21ec27b7",
    "reason": "era_unpinned L4-L5 stopped before the first local scout response because the API-only experiment scope target was also applied to the local ledger; preserve completed criteria/proposals and charged Fable calls, separate local charge target, then resume from durable artifacts without discretionary regeneration",
    "ts": "2026-07-19T06:49:53.381784+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "a5d00a52d9c9884fefbd724790f991e9c12c3802b7a2e1f284d13c2f7fe5808b",
    "event_id": "exp-w0009-l2-era-pin:000005",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: phase allocation overrun is reported as a deviation while aggregate cap remains the fail-closed provider gate",
    "previous_hash": "faee07c29d1c2ecec01cc72d4b61e8e309908ecd8e759ae84f41c6f2bc49a97c",
    "reason": "era_unpinned L4-L5 completed at USD 2.690760, exceeding its preregistered USD 2.50 allocation by USD 0.190760; aggregate experiment cap remains USD 12.00 and no fixed condition or outcome rule changes",
    "ts": "2026-07-19T07:06:39.745979+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "3f6a7f0059d09421460af05cd84363795b4c995bb45e77c35d860e9b9bfbf0ab",
    "event_id": "exp-w0009-l2-era-pin:000006",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: phase allocation overrun is reported as a deviation while aggregate cap remains the fail-closed provider gate",
    "previous_hash": "a5d00a52d9c9884fefbd724790f991e9c12c3802b7a2e1f284d13c2f7fe5808b",
    "reason": "era_pinned L4-L5 completed at USD 2.856650, exceeding its preregistered USD 2.50 allocation by USD 0.356650; aggregate experiment cap remains USD 12.00 and no fixed condition or outcome rule changes",
    "ts": "2026-07-19T07:21:33.518319+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "e001dfebd0b50bc25d9ed0f427427dc138a8e1945348349b7df1220a51cae515",
    "event_id": "exp-w0009-l2-era-pin:000008",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: provider-internal retry is the only regeneration allowed; blind selection must remain prior to jury reveal and post-hoc evidence must not alter the primary rule",
    "previous_hash": "b34e1f00374e69b5ca53f20ba02bcf1665d88c45dedd001f3f480416dbbcc012",
    "reason": "all six preregistered jury calls completed and were charged, but the final era_pinned local-jury response failed strict JSON parsing before any jury rows were durably projected; do not regenerate, disclose call/response hashes as INCOMPLETE_PARSE, and keep jury comparison secondary and inconclusive",
    "ts": "2026-07-19T07:26:44.832337+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex Phase 4 runner",
    "event_hash": "5d61bf9b7786cf5ed8195b4853b0d99fa175e2edbe138ee217138666cae76e3e",
    "event_id": "exp-w0009-l2-era-pin:000011",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "designs/phase4-w0009-l2-era-intervention.md: phase allocation overrun is reported as a deviation while aggregate cap remains the fail-closed provider gate",
    "previous_hash": "d2cb4703859e2834c8628e0026cd4b69706037dc66d12f537c1492247c5673c4",
    "reason": "canonical L6-L7 reached USD 3.622440, exceeding its preregistered USD 3.50 allocation by USD 0.122440 during the existing closed-loop stopping path; aggregate experiment cap remains USD 12.00 and the stopping rules remain unchanged",
    "ts": "2026-07-19T08:02:28.438906+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex/operator-safe-interrupt",
    "event_hash": "5b69cb4c4f578db853ad0ce73607d1f4ef41351ece77f50734be2d28c9991b33",
    "event_id": "exp-w0009-l2-era-pin:000012",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "Deviation rule: record and preserve any operational interruption or incomplete evaluation; never silently retry charged calls. Complete experiment API cap is $12.00 and execution must fail closed before further charge.",
    "previous_hash": "5d61bf9b7786cf5ed8195b4853b0d99fa175e2edbe138ee217138666cae76e3e",
    "reason": "canonical L6 review cycle 5 was interrupted during the local Qwen juror call after charged API juror calls 40810f78-3a2e-4101-b92f-8db3ff395ddb and 5dc1a1cc-9603-4d9e-9e7c-bfaef84d5bad completed. The partial review is excluded from trajectory and will not be regenerated. Interruption prevented another paid cycle while L7 stopping did not yet include the registered all-phase experiment scope; the stopping query was repaired test-first before checkpoint resume.",
    "ts": "2026-07-19T08:16:23.687761+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex/budget-fail-closed",
    "event_hash": "031936c91c71d252f54fdba05a7c60656c0b8f8bf36d6fbe2f17f7e5f5e382e4",
    "event_id": "exp-w0009-l2-era-pin:000013",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "Complete experiment API cap is $12.00; fail closed before charge and record operational deviations without regenerating completed calls.",
    "previous_hash": "5b69cb4c4f578db853ad0ce73607d1f4ef41351ece77f50734be2d28c9991b33",
    "reason": "After budget-path stopping, the idempotent title call e4554989-cf82-4ee1-af47-b046b37412c1 completed for $0.127780. The subsequent author publication-intent call was rejected by scope precheck before provider execution (remaining $0.754550; reserved estimate $1.006250). L7 publication was repaired test-first to resolve budget exhaustion as SHELVE without another author call.",
    "ts": "2026-07-19T08:18:45.533955+00:00",
    "type": "deviation"
  },
  {
    "decided_by": "Codex/evidence-correction",
    "event_hash": "d1341c3e706e007763a03c3238208707569aa580106227893cb04a3ce76a6b91",
    "event_id": "exp-w0009-l2-era-pin:000014",
    "experiment_id": "exp-w0009-l2-era-pin",
    "preregistration": "Canonical continuation is limited to L6-L7 and must not execute the poetics-reflection hook or enter Phase 5.",
    "previous_hash": "031936c91c71d252f54fdba05a7c60656c0b8f8bf36d6fbe2f17f7e5f5e382e4",
    "reason": "Canonical continuation intentionally omitted the poetics-reflection hook, but the existing FINISH/L7 title-selection implementation records its title decision with historical layer=L8. The title call and decision are preserved; no poetics reflection, poetics amendment, or Phase 5 work was executed. Reports distinguish this legacy layer label from reflection execution.",
    "ts": "2026-07-19T08:26:27.389984+00:00",
    "type": "deviation"
  }
]

## costs
{
  "budget_envelope": {
    "blind_select": 0.75,
    "canonical_L6_L7": 3.5,
    "era_pinned_L4_L5": 2.5,
    "era_unpinned_L4_L5": 2.5,
    "failure_reserve": 0.5,
    "jury_reveal": 1.5,
    "prepare": 0.75
  },
  "phase_costs": {
    "blind_select": 0.24097,
    "canonical_L6_L7": 5.01272,
    "era_pinned_L4_L5": 2.85665,
    "era_unpinned_L4_L5": 2.69076,
    "failure_reserve": 0.0,
    "jury_reveal": 0.35641999999999996,
    "prepare": 0.08793
  },
  "phase_overruns": {
    "canonical_L6_L7": {
      "cap": 3.5,
      "spent": 5.01272
    },
    "era_pinned_L4_L5": {
      "cap": 2.5,
      "spent": 2.85665
    },
    "era_unpinned_L4_L5": {
      "cap": 2.5,
      "spent": 2.69076
    }
  },
  "total_cap": 12.0,
  "total_spent": 11.24545
}
reconciliation_status: unreconciled
provider statements absent or unreconciled; matched is not claimed
