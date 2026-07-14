"""
अधिKaar RAG Setup — Ingest legal knowledge into ChromaDB for retrieval.

Run once before starting the server:  python rag_setup.py
Rebuild a single collection without redoing the slow corpus:
    python rag_setup.py --only rights
    python rag_setup.py --only official_law
"""

import argparse
import glob
import json
import os
import re
import sys

import chromadb
from chromadb.utils import embedding_functions

# Windows consoles default to cp1252 and blow up on the emoji in our progress
# output — same guard app.py already uses.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CORPUS_DIR = os.path.join(DATA_DIR, 'corpus')
CHROMA_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')

BATCH_SIZE = 200


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _fresh_collection(client, ef, name, description):
    try:
        client.delete_collection(name)
    except Exception:
        pass
    return client.create_collection(name=name, embedding_function=ef, metadata={"description": description})


def _add_batched(col, documents, metadatas, ids):
    for start in range(0, len(documents), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(documents))
        col.add(documents=documents[start:end], metadatas=metadatas[start:end], ids=ids[start:end])


# ── 1. IPC ↔ BNS Mapping ──
def build_ipc_bns(client, ef):
    print("📚 Loading IPC ↔ BNS mapping...")
    col = _fresh_collection(client, ef, "ipc_bns", "IPC to BNS section mapping")
    data = load_json('ipc_bns_mapping.json')
    documents, metadatas, ids = [], [], []
    for i, entry in enumerate(data):
        documents.append(
            f"IPC Section {entry['ipc_section']} corresponds to BNS Section {entry['bns_section']}. "
            f"Offence: {entry['offence']}. IPC Title: {entry['ipc_title']}. "
            f"BNS Title: {entry['bns_title']}. Description: {entry['description']} "
            f"Punishment: {entry['punishment']}. Key Changes: {entry['key_changes']}. "
            f"Category: {entry['category']}."
        )
        metadatas.append({
            "ipc_section": entry['ipc_section'], "bns_section": entry['bns_section'],
            "offence": entry['offence'], "category": entry['category'], "punishment": entry['punishment'],
        })
        ids.append(f"ipc_bns_{i}")
    _add_batched(col, documents, metadatas, ids)
    print(f"  ✅ Added {len(documents)} IPC-BNS mappings")


# ── 2. Rights knowledge (+ checklists, case studies, templates, IndicLegalQA) ──
def build_rights(client, ef):
    print("📚 Loading rights knowledge...")
    col = _fresh_collection(client, ef, "rights_knowledge", "Legal rights information by case type")
    rights_data = load_json('rights_knowledge.json')
    documents, metadatas, ids = [], [], []
    doc_count = 0

    def push(doc, meta):
        nonlocal doc_count
        documents.append(doc)
        metadatas.append(meta)
        ids.append(f"rights_{doc_count}")
        doc_count += 1

    for case_type in rights_data['case_types']:
        scenarios_text = ". ".join(case_type['common_scenarios'])
        rights_text = ". ".join(case_type['rights'])
        steps_text = ". ".join(case_type['steps'])
        docs_text = ", ".join(case_type['documents_needed'])
        keywords_text = ", ".join(case_type['keywords'])

        push(f"Case Type: {case_type['name']} ({case_type['name_hi']}). Keywords: {keywords_text}. "
             f"Common Scenarios: {scenarios_text}. Your Rights: {rights_text}.",
             {"case_type_id": case_type['id'], "case_type_name": case_type['name'], "doc_type": "overview"})
        push(f"Case Type: {case_type['name']}. Steps to Take: {steps_text}. Documents Needed: {docs_text}.",
             {"case_type_id": case_type['id'], "case_type_name": case_type['name'], "doc_type": "steps"})
        if 'deadlines' in case_type:
            deadlines_text = ". ".join(f"{d['action']}: {d['deadline']}" for d in case_type['deadlines'])
            push(f"Case Type: {case_type['name']}. Important Deadlines: {deadlines_text}.",
                 {"case_type_id": case_type['id'], "case_type_name": case_type['name'], "doc_type": "deadlines"})
        if 'relevant_sections' in case_type:
            sections = case_type['relevant_sections']
            push(f"Case Type: {case_type['name']}. Relevant BNS Sections: {', '.join(sections.get('bns', []))}. "
                 f"Other Relevant Laws: {', '.join(sections.get('other_laws', []))}.",
                 {"case_type_id": case_type['id'], "case_type_name": case_type['name'], "doc_type": "sections"})

    for term in rights_data.get('legal_terms', []):
        push(f"Legal Term: {term['term']}. Meaning: {term['meaning']}. Hindi Meaning: {term.get('meaning_hi', '')}.",
             {"case_type_id": "legal_terms", "case_type_name": "Legal Terminology", "doc_type": "term"})

    # Evidence checklists — reviewed document lists, steps and statutory deadlines.
    for tpl in load_json('evidence_checklists.json').get('templates', []):
        parts = [f"Evidence checklist: {tpl['title']} ({tpl.get('title_hi', '')}). {tpl.get('description', '')}"]
        parts += [f"Document needed: {d['name']} — {d.get('why', '')} How to get: {d.get('how_to_get', '')}"
                  for d in tpl.get('documents', [])]
        parts += [f"Step {i}: {s}" for i, s in enumerate(tpl.get('steps', []), 1)]
        parts += [f"Deadline: {dl.get('what', '')} — {dl.get('timeframe', '')}" for dl in tpl.get('deadlines', [])]
        parts += [f"Tip: {t}" for t in tpl.get('tips', [])]
        if tpl.get('helpline'):
            parts.append(f"Helpline: {tpl['helpline']}")
        push(" ".join(parts),
             {"type": "evidence_checklist", "checklist_id": tpl['id'], "category": tpl.get('category', ''), "doc_type": "checklist"})

    # Case studies — real-world Q&A pairs that make chat answers concrete.
    for cs in load_json('case_studies.json').get('cases', []):
        push(f"Case study ({cs.get('category', '')}): {cs.get('scenario', '')} "
             f"Question: {cs.get('question', '')} Answer: {cs.get('answer', '')} "
             f"Keywords: {', '.join(cs.get('keywords', []))}",
             {"type": "case_study", "case_id": cs['id'], "category": cs.get('category', ''), "doc_type": "case_study"})

    # Document templates — so answers can point to the right format to file.
    for tpl in load_json('document_templates.json').get('templates', []):
        push(f"Legal document format: {tpl.get('title', '')} ({tpl.get('category', '')}). "
             f"When to use: {tpl.get('when_to_use', '')} Where to submit: {tpl.get('where_to_submit', '')} "
             f"Tips: {' '.join(tpl.get('tips', []))}",
             {"type": "document_template", "template_id": tpl['id'], "category": tpl.get('category', ''), "doc_type": "template"})

    # IndicLegalQA — optional external Q&A dataset. Warn-and-skip if absent.
    qa_added = _ingest_indic_legal_qa(push)

    _add_batched(col, documents, metadatas, ids)
    print(f"  ✅ Added {doc_count} rights knowledge documents (incl. checklists, case studies, templates, "
          f"{qa_added} Q&A pairs)")


def _ingest_indic_legal_qa(push):
    """Add IndicLegalQA pairs if data/raw/indic_legal_qa.json is present."""
    path = os.path.join(DATA_DIR, 'raw', 'indic_legal_qa.json')
    if not os.path.exists(path):
        print("  ℹ️  IndicLegalQA not found (data/raw/indic_legal_qa.json) — skipping. "
              "Download from Kaggle 'kmldas/indiclegalqa-dataset' to include it.")
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        print(f"  ⚠️  Could not read IndicLegalQA: {e} — skipping.")
        return 0

    # Accept a top-level list, or a dict wrapping the list under a common key.
    rows = raw
    if isinstance(raw, dict):
        for k in ('data', 'questions', 'qa', 'rows', 'items'):
            if isinstance(raw.get(k), list):
                rows = raw[k]
                break
    if not isinstance(rows, list):
        print("  ⚠️  IndicLegalQA has an unexpected shape — skipping.")
        return 0

    def field(row, *names):
        for n in names:
            v = row.get(n)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    strip_html = re.compile(r'<[^>]+>')
    seen, kept, dropped = set(), 0, 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            dropped += 1
            continue
        q = strip_html.sub('', field(row, 'question', 'Question', 'query', 'q'))
        a = strip_html.sub('', field(row, 'answer', 'Answer', 'response', 'a'))
        key = q.lower().strip()
        if len(q) < 10 or not (40 <= len(a) <= 3000) or key in seen:
            dropped += 1
            continue
        seen.add(key)
        push(f"Legal Q&A. Question: {q} Answer: {a}",
             {"type": "qa_pair", "doc_type": "qa_pair", "source": "indic_legal_qa"})
        kept += 1
    print(f"  ✅ IndicLegalQA: kept {kept}, dropped {dropped}")
    return kept


# ── 3. Legal aid directory ──
def build_legal_aid(client, ef):
    print("📚 Loading legal aid directory...")
    col = _fresh_collection(client, ef, "legal_aid", "Legal aid contacts and helplines")
    data = load_json('legal_aid_directory.json')
    documents, metadatas, ids = [], [], []
    doc_count = 0

    for helpline in data['helplines']:
        documents.append(
            f"Helpline: {helpline['name']} ({helpline['name_hi']}). Number: {helpline['number']}. "
            f"Description: {helpline['description']}. Hours: {helpline['hours']}. "
            f"Toll Free: {'Yes' if helpline['toll_free'] else 'No'}."
        )
        metadatas.append({"type": "helpline", "name": helpline['name'], "number": helpline['number']})
        ids.append(f"legal_aid_{doc_count}")
        doc_count += 1

    for state in data['states']:
        slsa = state['slsa']
        documents.append(
            f"State: {state['name']} ({state['name_hi']}). State Legal Services Authority: {slsa['name']}. "
            f"Phone: {slsa.get('phone', '')}. Website: {slsa.get('website', '')}. Address: {slsa.get('address', '')}."
        )
        metadatas.append({"type": "state", "state": state['name'], "phone": slsa.get('phone', '')})
        ids.append(f"legal_aid_{doc_count}")
        doc_count += 1
        for district in state['districts']:
            documents.append(
                f"District Legal Services Authority: {district['name']} ({district.get('name_hi', '')}) "
                f"in {state['name']}. Address: {district.get('dlsa_address', '')}. Phone: {district.get('phone', '')}."
            )
            metadatas.append({"type": "district", "state": state['name'],
                              "district": district['name'], "phone": district.get('phone', '')})
            ids.append(f"legal_aid_{doc_count}")
            doc_count += 1

    _add_batched(col, documents, metadatas, ids)
    print(f"  ✅ Added {doc_count} legal aid entries")


# ── 4. Official law corpus (Nyaya Navigator JSONL) ──
# Chroma metadata must be flat scalars — no None, lists or dicts. Keep the fields
# a citation actually needs.
_KEEP_META = ("act", "title", "section_id", "heading", "source_id", "language",
              "status", "effective_from", "priority", "official_url", "official_landing_url",
              "page_start", "page_end")


def _flatten_meta(record):
    meta = dict(record.get('metadata') or {})
    # top-level fallbacks the corpus sometimes keeps outside metadata
    for k in ("heading", "section_id", "source_id", "page_start", "page_end"):
        meta.setdefault(k, record.get(k))
    out = {}
    for k in _KEEP_META:
        v = meta.get(k)
        if v is None or isinstance(v, (list, dict)):
            continue
        out[k] = v
    return out


def build_official_law(client, ef):
    print("📚 Loading official-law corpus (this is the slow one)...")
    col = _fresh_collection(client, ef, "official_law", "Official Indian statute text with source URLs")
    files = sorted(glob.glob(os.path.join(CORPUS_DIR, '*.jsonl')))
    if not files:
        print(f"  ⚠️  No corpus files in {CORPUS_DIR} — skipping official_law.")
        return

    documents, metadatas, ids = [], [], []
    seen_ids, skipped_empty = set(), 0
    for path in files:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                text = (rec.get('text') or '').strip()
                if not text:
                    skipped_empty += 1
                    continue
                cid = rec.get('chunk_id') or f"{rec.get('source_id', 'doc')}:{len(seen_ids)}"
                if cid in seen_ids:  # ids must be unique
                    cid = f"{cid}:{len(seen_ids)}"
                seen_ids.add(cid)
                documents.append(text)
                metadatas.append(_flatten_meta(rec))
                ids.append(cid)

    _add_batched(col, documents, metadatas, ids)
    print(f"  ✅ Added {len(documents)} official-law chunks from {len(files)} files (skipped {skipped_empty} empty)")


BUILDERS = {
    "ipc_bns": build_ipc_bns,
    "rights": build_rights,
    "legal_aid": build_legal_aid,
    "official_law": build_official_law,
}


def setup_rag(only="all"):
    print("🔧 Setting up अधिKaar RAG knowledge base...")
    ef = embedding_functions.DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    targets = BUILDERS.keys() if only == "all" else [only]
    for name in targets:
        BUILDERS[name](client, ef)

    print("\n✅ RAG knowledge base setup complete!")
    print(f"   Database location: {CHROMA_DIR}")
    print(f"   Collections built: {', '.join(targets)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Build AdhiKaar RAG collections.")
    parser.add_argument('--only', choices=list(BUILDERS.keys()) + ['all'], default='all',
                        help="Build a single collection instead of all.")
    args = parser.parse_args()
    setup_rag(args.only)
