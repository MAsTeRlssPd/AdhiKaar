"""Verified 'Law & Next Steps' pipeline - draft -> guard -> verify -> repair.

Re-implemented (not imported) from Nyaya Navigator's agent pipeline, adapted to a
plain injected LLM callable so it runs on AdhiKaar's Ollama call_gemma and is
testable with a stub.

Flow, per analysis:
  1. DRAFT   (1 LLM call): the model reads the retrieved statute excerpts and
             produces the six panels + a list of claims, each citing chunk ids.
  2. GUARD   (free): a claim naming a section absent from its cited excerpts is
             marked 'unverified' before any model sees it (deterministic
             hallucination guard, ported from drafter.uncited_section_references).
  3. VERIFY  (1 LLM call, batched): surviving claims are checked against only
             their cited excerpts; the model returns supported / unsupported.
  4. REPAIR  (free): unsupported/unverified claims are excluded from the law,
             rights and sources panels and flagged in verification[].

Typical path = 2 LLM calls (draft + verify); 3 only if verify batches split.
"""

import json
import re

DRAFT_EXCERPT = 1200      # chars of each chunk shown to the drafter
VERIFY_EXCERPT = 1500     # chars of each chunk shown to the verifier
MAX_CHUNKS = 6
MAX_CLAIMS = 8
VERIFY_BATCH_CHARS = 18000

_SECTION_REFERENCE = re.compile(
    r"\b(?:section|sec\.|article|art\.|rule|धारा|अनुच्छेद)\s*([0-9]+[A-Za-z]?)",
    re.IGNORECASE,
)


def _uncited_section_references(claim_text, cited_excerpts):
    """Return the section numbers a claim asserts that its cited excerpts do not
    contain. Deterministic hallucination guard (ported from Nyaya's drafter)."""
    offences = []
    for reference in _SECTION_REFERENCE.findall(claim_text):
        supported = False
        for excerpt in cited_excerpts:
            found = {f.casefold() for f in _SECTION_REFERENCE.findall(excerpt)}
            if reference.casefold() in found or re.search(rf"\b{re.escape(reference)}\b", excerpt):
                supported = True
                break
        if not supported:
            offences.append(reference)
    return offences


def _parse_json(text):
    """Tolerant JSON extraction - strips code fences, finds the outermost object."""
    if not text:
        return None
    t = text.strip()
    if '```json' in t:
        t = t.split('```json', 1)[1].split('```', 1)[0]
    elif '```' in t:
        t = t.split('```', 1)[1].split('```', 1)[0]
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # last resort: slice from first { to last }
        i, j = t.find('{'), t.rfind('}')
        if 0 <= i < j:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                return None
        return None


_DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "situation_and_law": {"type": "string"},
        "applicable_law": {"type": "array", "items": {"type": "string"}},
        "rights": {"type": "array", "items": {
            "type": "object",
            "properties": {"text": {"type": "string"}, "source": {"type": "string"}},
            "required": ["text"],
        }},
        "next_steps": {"type": "array", "items": {"type": "string"}},
        "stress_test": {"type": "object", "properties": {
            "for": {"type": "array", "items": {"type": "string"}},
            "against": {"type": "array", "items": {"type": "string"}},
            "weaknesses": {"type": "array", "items": {"type": "string"}},
        }},
        "explain_simply": {"type": "string"},
        "claims": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "cited_chunk_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
        }},
    },
    "required": ["situation_and_law", "applicable_law", "rights", "next_steps",
                 "stress_test", "explain_simply", "claims"],
}


def _draft(situation, chunks, language, call_llm):
    numbered = "\n\n".join(
        f"[{c['chunk_id']}] {c.get('act', '')} {c.get('section', '')}\n{c['text'][:DRAFT_EXCERPT]}"
        for c in chunks[:MAX_CHUNKS]
    ) or "(no statute excerpts retrieved)"

    system = (
        "You are an Indian legal-aid expert. Using ONLY the statute excerpts provided, "
        "produce a verified analysis as JSON. Every legal claim you make MUST cite the "
        "chunk id(s) it relies on in cited_chunk_ids, and you may only name a section "
        "number that literally appears in a cited excerpt. Do not invent sections. "
        f"Write all prose in {language}. Return ONLY JSON with keys: situation_and_law "
        "(markdown restating the facts + the applicable law), applicable_law (array of "
        "short statements), rights (array of {text, source}), next_steps (array), "
        "stress_test ({for[], against[], weaknesses[]}), explain_simply (a plain, "
        "jargon-free paragraph the person can read to family), claims (array of "
        f"{{text, cited_chunk_ids}}, max {MAX_CLAIMS})."
    )
    user = f"Situation:\n{situation}\n\nStatute excerpts:\n{numbered}\n\nReturn the JSON analysis."
    raw = call_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2, num_ctx=8192, response_format="json",
    )
    return _parse_json(raw) or {}


def _verify(claims, chunk_by_id, call_llm):
    """Batch-verify claims against their cited excerpts. Returns {claim_id: bool}."""
    if not claims:
        return {}

    def excerpt_block(claim):
        cites = [chunk_by_id[cid] for cid in claim['cited_chunk_ids'] if cid in chunk_by_id]
        joined = "\n".join(f"[{c['chunk_id']}] {c['text'][:VERIFY_EXCERPT]}" for c in cites) or "(no sources)"
        return f"CLAIM {claim['id']}: {claim['text']}\nSOURCES:\n{joined}"

    # Split into batches so a big prompt never overruns context.
    batches, cur, size = [], [], 0
    for claim in claims:
        block = excerpt_block(claim)
        if cur and size + len(block) > VERIFY_BATCH_CHARS:
            batches.append(cur)
            cur, size = [], 0
        cur.append((claim['id'], block))
        size += len(block)
    if cur:
        batches.append(cur)

    verdicts = {}
    system = (
        "You are a strict legal fact-checker. For each CLAIM, decide whether its own "
        "SOURCES actually support it. A claim naming a section is supported only if that "
        "section text is in its sources. Return ONLY JSON: {\"results\": [{\"claim_id\": "
        "\"...\", \"supported\": true|false}]}."
    )
    for batch in batches:
        body = "\n\n".join(block for _, block in batch)
        raw = call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": body}],
            temperature=0.0, num_ctx=8192, response_format="json",
        )
        parsed = _parse_json(raw) or {}
        for r in parsed.get("results", []):
            verdicts[str(r.get("claim_id"))] = bool(r.get("supported"))
    return verdicts


def run_pipeline(situation, chunks, language, call_llm):
    """chunks: [{chunk_id, text, act, section, official_url}]. Returns the six-panel dict."""
    chunk_by_id = {c['chunk_id']: c for c in chunks}
    draft = _draft(situation, chunks, language, call_llm)

    # Assign claim ids + normalise
    claims = []
    for i, c in enumerate(draft.get('claims', [])[:MAX_CLAIMS]):
        if not isinstance(c, dict) or not c.get('text'):
            continue
        cited = [str(x) for x in (c.get('cited_chunk_ids') or []) if str(x) in chunk_by_id]
        claims.append({"id": f"c{i}", "text": c['text'], "cited_chunk_ids": cited, "status": "pending"})

    # Deterministic guard: fabricated section => unverified before any model call.
    survivors = []
    for claim in claims:
        excerpts = [chunk_by_id[cid]['text'] for cid in claim['cited_chunk_ids']]
        if not claim['cited_chunk_ids'] or _uncited_section_references(claim['text'], excerpts):
            claim['status'] = 'unverified'
        else:
            survivors.append(claim)

    # Verify survivors against their sources.
    verdicts = _verify(survivors, chunk_by_id, call_llm)
    for claim in survivors:
        claim['status'] = 'supported' if verdicts.get(claim['id'], False) else 'unsupported'

    supported = [c for c in claims if c['status'] == 'supported']

    # Sources: official_url of chunks cited by SUPPORTED claims only.
    sources, seen = [], set()
    for claim in supported:
        for cid in claim['cited_chunk_ids']:
            c = chunk_by_id[cid]
            url = c.get('official_url')
            if url and url not in seen:
                seen.add(url)
                sources.append({
                    "title": c.get('act') or c.get('title') or "Official source",
                    "act": c.get('act', ''),
                    "section": c.get('section', ''),
                    "url": url,
                })

    verification = [{"claim": c['text'], "cited_chunk_ids": c['cited_chunk_ids'], "status": c['status']}
                    for c in claims]

    st = draft.get('stress_test') or {}
    explain = (draft.get('explain_simply') or '').strip()
    if not explain:
        # deterministic fallback: first ~2 sentences of the restatement
        restate = re.sub(r'[#*`>]', '', draft.get('situation_and_law') or '').strip()
        explain = ' '.join(re.split(r'(?<=[.।])\s+', restate)[:2]) or \
            "Here is a plain summary of your situation and what the law says about it."

    return {
        "situation_and_law": draft.get('situation_and_law', ''),
        "applicable_law": draft.get('applicable_law', []),
        "rights": [r for r in draft.get('rights', []) if isinstance(r, dict) and r.get('text')],
        "next_steps": draft.get('next_steps', []),
        "stress_test": {
            "for": st.get('for', []), "against": st.get('against', []),
            "weaknesses": st.get('weaknesses', []),
        },
        "explain_simply": explain,
        "verification": verification,
        "sources": sources,
    }
