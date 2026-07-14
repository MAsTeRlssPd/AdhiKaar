"""Exercises the verified law-and-steps pipeline with a stubbed LLM.

The point of the pipeline is that a WRONG legal claim never reaches the user as
'verified'. The deterministic guard must catch a claim that names a section its
cited source does not contain — before any model is trusted.

Run: python test_lawsteps_verify.py
"""

import json

import lawsteps_pipeline as lp

CHUNKS = [
    {"chunk_id": "bns_2023_en:section-63", "text": "Section 63. Rape. A man is said to commit rape ...",
     "act": "Bharatiya Nyaya Sanhita, 2023", "section": "63",
     "official_url": "https://www.indiacode.nic.in/bns-63"},
    {"chunk_id": "bnss_2023_en:section-173", "text": "Section 173. Information in cognizable cases. Every information relating to a cognizable offence ...",
     "act": "Bharatiya Nagarik Suraksha Sanhita, 2023", "section": "173",
     "official_url": "https://www.indiacode.nic.in/bnss-173"},
]


def make_stub():
    """First call = draft (one clean claim citing s.173, one fabricating s.999).
    Second call = verify (support the surviving claim)."""
    calls = {"n": 0}

    def call_llm(messages, temperature=0.2, num_ctx=8192, response_format=None):
        calls["n"] += 1
        if calls["n"] == 1:  # DRAFT
            return json.dumps({
                "situation_and_law": "You can report the offence. The police must register an FIR under Section 173.",
                "applicable_law": ["FIR must be registered for a cognizable offence."],
                "rights": [{"text": "You have the right to have your FIR registered.", "source": "BNSS 173"}],
                "next_steps": ["Go to the police station and insist on FIR registration."],
                "stress_test": {"for": ["Clear cognizable offence."], "against": ["Facts disputed."], "weaknesses": ["No witnesses."]},
                "explain_simply": "The police have to write down your complaint as an FIR.",
                "claims": [
                    {"text": "The police must register an FIR under Section 173.",
                     "cited_chunk_ids": ["bnss_2023_en:section-173"]},
                    {"text": "You are protected under Section 999 of the BNSS.",
                     "cited_chunk_ids": ["bnss_2023_en:section-173"]},
                ],
            })
        # VERIFY — support whatever survived the guard
        return json.dumps({"results": [{"claim_id": "c0", "supported": True}]})

    return call_llm, calls


def main():
    call_llm, calls = make_stub()
    result = lp.run_pipeline("Police won't file my FIR for a theft.", CHUNKS, "English", call_llm)

    # 2 claims tracked
    assert len(result["verification"]) == 2, result["verification"]

    statuses = {v["claim"][:20]: v["status"] for v in result["verification"]}
    # the fabricated Section 999 claim must NOT be supported (guard catches it)
    fabricated = next(v for v in result["verification"] if "999" in v["claim"])
    assert fabricated["status"] == "unverified", fabricated
    # the good claim is supported
    good = next(v for v in result["verification"] if "173" in v["claim"])
    assert good["status"] == "supported", good

    # sources contain ONLY the supported claim's chunk url, never the fabricated one
    urls = [s["url"] for s in result["sources"]]
    assert urls == ["https://www.indiacode.nic.in/bnss-173"], urls

    # explain_simply is non-empty
    assert result["explain_simply"].strip(), "explain_simply empty"

    # guard ran before verify: the fabricated claim never went to the verify call,
    # so exactly 2 LLM calls (draft + one verify batch)
    assert calls["n"] == 2, f"expected 2 LLM calls, got {calls['n']}"

    print("OK - law-and-steps verify pipeline: guard caught fabricated section, sources clean, 2 LLM calls")


if __name__ == "__main__":
    main()
