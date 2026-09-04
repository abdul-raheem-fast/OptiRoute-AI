"""Free-text conservative-routing guarantee.

The project documents that arbitrary, non-benchmark-style prompts route
conservatively and often escalate to GPT-5. This turns that claim into an
executable guarantee: if the router EVER sends a casual free-text prompt to a
cheap model, it must do so with genuinely high confidence (>0.90) for that
model - never a confident-but-unjustified cheap route on ambiguous text.

The escalation rate is MEASURED here, not assumed, so it can be quoted honestly.
"""
import pytest

from routing.config import STRONGEST

CASUAL_PROMPTS = [
    "hey can u help me fix my code idk what's wrong",
    "explain this to me like im 5 thanks",
    "yo whats the deal with this error msg im stuck",
    "can you make this sound more professional for my boss",
    "idk if this is right but does it even matter lol",
    "write me something catchy for my instagram bio",
    "hmm why is my wifi slow today of all days",
    "give me a random fun fact i guess",
    "ok so like how do i even start learning guitar",
    "translate this vibe into a polite email please",
    "my cat keeps knocking stuff over any advice",
    "whats a good name for my food blog maybe",
    "summarize whatever this is im too tired to read",
    "brb but first tell me a joke about mondays",
]

# A cheap route is only acceptable on ambiguous free text if the router's own
# confidence for that model genuinely clears this bar.
MIN_CONFIDENCE_FOR_CHEAP_ROUTE = 0.90


@pytest.fixture(scope="module")
def freetext_decisions(core):
    return [(p, core.route(p, None, core.t_star)) for p in CASUAL_PROMPTS]


def test_cheap_routes_on_free_text_are_high_confidence(freetext_decisions):
    violations = []
    for prompt, d in freetext_decisions:
        if d["chosen_model"] != STRONGEST:
            p = d["p_correct"][d["chosen_model"]]
            if p <= MIN_CONFIDENCE_FOR_CHEAP_ROUTE:
                violations.append(
                    f"{prompt!r} -> {d['chosen_model']} at p={p:.3f} "
                    f"(<= {MIN_CONFIDENCE_FOR_CHEAP_ROUTE})"
                )
    assert not violations, (
        "confident-but-unjustified cheap route on ambiguous free text:\n"
        + "\n".join(violations)
    )


def test_every_free_text_decision_is_well_formed(freetext_decisions):
    for _prompt, d in freetext_decisions:
        assert d["chosen_model"] is not None
        assert d["tier"] in ("easy", "medium", "hard")
        # the gate is honoured: a non-fallback choice cleared t
        if not d["is_fallback"]:
            assert d["p_correct"][d["chosen_model"]] >= d["threshold"]


def test_report_measured_escalation_rate(freetext_decisions):
    """Measure, don't assume. Prints the rate so it can be quoted honestly."""
    escalated = [p for p, d in freetext_decisions if d["chosen_model"] == STRONGEST]
    rate = len(escalated) / len(freetext_decisions) * 100.0
    cheap = [(p, d["chosen_model"], d["p_correct"][d["chosen_model"]])
             for p, d in freetext_decisions if d["chosen_model"] != STRONGEST]
    print("\n--- free-text conservative-routing report ---")
    print(f"prompts: {len(freetext_decisions)}")
    print(f"escalated to {STRONGEST}: {len(escalated)} "
          f"({rate:.1f}% escalation rate)")
    for p, m, conf in cheap:
        print(f"  cheap-route: {m} (p={conf:.3f})  <- {p!r}")
    print("---------------------------------------------")
    assert 0.0 <= rate <= 100.0
    # The documented behaviour is that free text escalates OFTEN; require that
    # the measurement is a real majority-or-near-majority, not a vacuous 0%.
    assert rate >= 50.0, (
        f"escalation rate {rate:.1f}% is suspiciously low for OOD free text; "
        "re-check that these prompts are genuinely out-of-distribution"
    )
