"""Self-check for /api/law-and-steps.

Runs offline: the LLM is stubbed, so this exercises only the branchy parts -
pulling JSON out of the model's reply (fenced or bare), failing soft into a
six-panel shape when the model returns prose, and the deterministic citation
guard that stops a fabricated deep link ever reaching the user.

    python test_lawsteps.py
"""

import json
import app

PANELS = ('situation_and_law', 'verification', 'sources',
          'stress_test', 'rights_card', 'explain_simply')

INDIACODE = "https://www.indiacode.nic.in"

GOOD = {
    "situation_and_law": "Your salary is unpaid. BNS Section 316 covers criminal breach of trust.",
    "verification": [{"claim": "BNS Section 316 applies",
                      "supported_by": "IPC 406 -> BNS 316 mapping",
                      "status": "verified"}],
    "sources": [{"title": "Bharatiya Nyaya Sanhita, 2023", "url": INDIACODE}],
    "stress_test": {"for": ["Written contract exists"],
                    "against": ["Employer may allege poor performance"],
                    "weaknesses": ["No written demand sent yet"]},
    "rights_card": {"title": "Your Rights",
                    "rights": [{"text": "You can demand unpaid wages", "source": "Payment of Wages Act"}]},
    "explain_simply": "They owe you money for work you did. The law is on your side.",
}


def post(client, situation="my employer has not paid my salary"):
    r = client.post('/api/law-and-steps', json={"situation": situation, "language": "en"})
    assert r.status_code == 200, r.status_code
    return r.get_json()["result"]


def main():
    app.app.testing = True
    client = app.app.test_client()
    original = app.call_gemma

    try:
        # 1. Fenced JSON - the common Gemma reply shape - must parse, not fall back.
        app.call_gemma = lambda *a, **k: "```json\n" + json.dumps(GOOD) + "\n```"
        assert post(client) == GOOD, "fenced JSON was not extracted cleanly"

        # 2. Bare JSON must parse too.
        app.call_gemma = lambda *a, **k: json.dumps(GOOD)
        got = post(client)
        assert got["explain_simply"] == GOOD["explain_simply"]
        assert all(k in got for k in PANELS), sorted(got)

        # 3. Prose instead of JSON must NOT 500 - it fails soft into all six panels,
        #    keeping the model's text in panel (a) and real official sources in (c).
        app.call_gemma = lambda *a, **k: "Sorry, I cannot do that."
        got = post(client)
        assert all(k in got for k in PANELS), "fallback dropped a panel: %s" % sorted(got)
        assert got["situation_and_law"] == "Sorry, I cannot do that."
        assert got["sources"], "fallback must still cite official sources"

        # 4. THE GUARD: a fabricated deep link must never survive to the user.
        #    Right host, invented path -> collapsed to the domain root.
        #    Unknown host entirely -> dropped to India Code.
        hallucinated = dict(GOOD, sources=[
            {"title": "BNS s.316", "url": "https://www.indiacode.nic.in/bns/section-316-does-not-exist"},
            {"title": "Totally made up", "url": "https://legal-advice-blog.example.com/bns"},
            {"title": "NALSA", "url": "https://nalsa.gov.in"},
        ])
        app.call_gemma = lambda *a, **k: json.dumps(hallucinated)
        urls = [s["url"] for s in post(client)["sources"]]
        assert urls[0] == INDIACODE, "invented deep link survived: %s" % urls[0]
        assert urls[1] == INDIACODE, "unofficial host survived: %s" % urls[1]
        assert urls[2] == "https://nalsa.gov.in", "a real official root was rewritten"
        for u in urls:
            assert u in app._official_urls(), "non-official URL reached the user: %s" % u

        # 5. An empty situation is rejected rather than sent to the model.
        app.call_gemma = lambda *a, **k: (_ for _ in ()).throw(AssertionError("model must not be called"))
        assert client.post('/api/law-and-steps', json={"situation": "  "}).status_code == 400

        # 6. The official URL set is well-formed and holds the two national fallbacks.
        assert INDIACODE in app._official_urls()
        assert "https://nalsa.gov.in" in app._official_urls()
        for url in app._official_urls():
            assert url.startswith("https://"), url
    finally:
        app.call_gemma = original

    print("law-and-steps: all checks passed")


if __name__ == '__main__':
    main()
