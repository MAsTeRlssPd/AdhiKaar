"""
Self-check for the chat document-RAG flow: upload -> indexed -> chat grounded in it -> clear.
Runs without Ollama (call_gemma is stubbed). Needs ChromaDB only.

    python test_doc_rag.py
"""

import os
import app

SESSION = "test-sess-0001"
DOC_TEXT = (
    "LEGAL NOTICE. The landlord Ram Kumar must return the security deposit of "
    "Rs 50000 to the tenant Sita Devi on or before 30 June 2026, failing which "
    "proceedings will be initiated. "
) * 8


def demo():
    client = app.app.test_client()
    upload_path = os.path.join(app.UPLOADS_DIR, f"{SESSION}.txt")

    # ── upload: saved locally, chunked into the per-session collection, summarised ──
    app.call_gemma = lambda messages, temperature=0.7, fallback_cpu=False: "STUB SUMMARY"
    res = client.post('/api/upload-document', json={
        'text': DOC_TEXT, 'filename': 'notice.txt', 'session_id': SESSION,
    })
    assert res.status_code == 200, res.data
    body = res.get_json()
    assert body['doc_id'] and body['filename'] == 'notice.txt'
    assert body['chunks'] >= 1, body
    assert body['summary'] == "STUB SUMMARY"
    assert app.sessions[SESSION]['doc']['filename'] == 'notice.txt'
    assert os.path.exists(upload_path), "document not saved locally"

    # ── chat: the doc's chunks are injected into the system prompt ──
    captured = {}

    def spy(messages, temperature=0.7, fallback_cpu=False):
        captured['system'] = messages[0]['content']
        return "ok"

    app.call_gemma = spy
    res = client.post('/api/chat', json={
        'message': 'How much is the security deposit?', 'session_id': SESSION,
    })
    assert res.status_code == 200, res.data
    assert "From the user's uploaded document:" in captured['system'], captured['system']
    assert "50000" in captured['system'], "doc chunk not retrieved into context"

    # ── clear: collection, session state, and local file all gone ──
    res = client.post('/api/clear-document', json={'session_id': SESSION})
    assert res.status_code == 200
    assert 'doc' not in app.sessions[SESSION]
    assert not os.path.exists(upload_path)
    assert app.load_doc_collection(SESSION) is None

    # ── no doc attached: chat behaves as before ──
    captured.clear()
    res = client.post('/api/chat', json={'message': 'hello', 'session_id': SESSION})
    assert res.status_code == 200
    assert "From the user's uploaded document:" not in captured['system']

    print("OK: upload -> index -> grounded chat -> clear")


if __name__ == '__main__':
    demo()
