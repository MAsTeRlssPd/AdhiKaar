"""Checks the deterministic evidence-checklist matcher.

The matcher grounds the AI checklist in a human-reviewed template, so a WRONG
match is worse than no match - it would hand the user the wrong documents and
the wrong statutory deadlines. The negative cases below matter as much as the
positive ones: ambiguous or off-topic input must return None, not a guess.

Run: python test_checklist_match.py
"""

import app

CASES = [
    # (situation, expected template id)
    ("my employer has not paid my salary for 3 months", "unpaid_wages"),
    ("mera malik ne meri salary nahi di", "unpaid_wages"),          # Hinglish
    ("landlord not returning security deposit", "security_deposit_refund"),
    ("landlord is evicting me illegally", "illegal_eviction"),
    ("cheque bounce case against me", "cheque_bounce"),
    ("my husband beats me", "domestic_violence"),
    ("someone cheated me on UPI online", "online_upi_fraud"),
    ("my boss touched me inappropriately at work", "workplace_sexual_harassment"),
    ("doctor operated on the wrong leg", "medical_negligence"),
    ("RTI application got no reply in 30 days", "rti_first_appeal"),

    # Sibling case types that expansion can blur - "police" expands to include
    # "FIR", which once tied a custodial complaint with fir_refusal.
    ("police refused to file my FIR", "fir_refusal"),
    ("the police beat me in custody", "police_misconduct"),

    # Off-topic must not match anything.
    ("what is the capital of France", None),
    ("hello how are you", None),
]


def main():
    failures = []
    for situation, expected in CASES:
        got = app.match_checklist(situation)
        got_id = got["id"] if got else None
        if got_id != expected:
            failures.append(f"  {situation!r}\n    expected {expected}, got {got_id}")

    assert not failures, "checklist matcher regressions:\n" + "\n".join(failures)
    print(f"OK - {len(CASES)} checklist matcher cases passed")


if __name__ == "__main__":
    main()
