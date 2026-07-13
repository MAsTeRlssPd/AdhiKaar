"""
अधिKaar RAG Setup — Ingest legal knowledge into ChromaDB for retrieval.
Run this once before starting the server.
"""

import json
import os
import sys
import chromadb
from chromadb.utils import embedding_functions

# Windows consoles default to cp1252 and blow up on the emoji in our progress
# output — same guard app.py already uses.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CHROMA_DIR = os.path.join(os.path.dirname(__file__), 'chroma_db')

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def setup_rag():
    print("🔧 Setting up अधिKaar RAG knowledge base...")
    
    # Use default embedding function (all-MiniLM-L6-v2)
    ef = embedding_functions.DefaultEmbeddingFunction()
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    # ── 1. IPC ↔ BNS Mapping Collection ──
    print("📚 Loading IPC ↔ BNS mapping...")
    try:
        client.delete_collection("ipc_bns")
    except:
        pass
    
    ipc_bns_col = client.create_collection(
        name="ipc_bns",
        embedding_function=ef,
        metadata={"description": "IPC to BNS section mapping"}
    )
    
    ipc_bns_data = load_json('ipc_bns_mapping.json')
    
    documents = []
    metadatas = []
    ids = []
    
    for i, entry in enumerate(ipc_bns_data):
        # Create a rich text document for embedding
        doc = (
            f"IPC Section {entry['ipc_section']} corresponds to BNS Section {entry['bns_section']}. "
            f"Offence: {entry['offence']}. "
            f"IPC Title: {entry['ipc_title']}. "
            f"BNS Title: {entry['bns_title']}. "
            f"Description: {entry['description']} "
            f"Punishment: {entry['punishment']}. "
            f"Key Changes: {entry['key_changes']}. "
            f"Category: {entry['category']}."
        )
        documents.append(doc)
        metadatas.append({
            "ipc_section": entry['ipc_section'],
            "bns_section": entry['bns_section'],
            "offence": entry['offence'],
            "category": entry['category'],
            "punishment": entry['punishment']
        })
        ids.append(f"ipc_bns_{i}")
    
    # ChromaDB has a batch limit, add in chunks
    batch_size = 40
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        ipc_bns_col.add(
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end]
        )
    
    print(f"  ✅ Added {len(documents)} IPC-BNS mappings")
    
    # ── 2. Rights Knowledge Collection ──
    print("📚 Loading rights knowledge...")
    try:
        client.delete_collection("rights_knowledge")
    except:
        pass
    
    rights_col = client.create_collection(
        name="rights_knowledge",
        embedding_function=ef,
        metadata={"description": "Legal rights information by case type"}
    )
    
    rights_data = load_json('rights_knowledge.json')
    
    documents = []
    metadatas = []
    ids = []
    doc_count = 0
    
    for case_type in rights_data['case_types']:
        # Create documents for each aspect of the case type
        
        # Main overview document
        scenarios_text = ". ".join(case_type['common_scenarios'])
        rights_text = ". ".join(case_type['rights'])
        steps_text = ". ".join(case_type['steps'])
        docs_text = ", ".join(case_type['documents_needed'])
        keywords_text = ", ".join(case_type['keywords'])
        
        # Overview document
        doc = (
            f"Case Type: {case_type['name']} ({case_type['name_hi']}). "
            f"Keywords: {keywords_text}. "
            f"Common Scenarios: {scenarios_text}. "
            f"Your Rights: {rights_text}."
        )
        documents.append(doc)
        metadatas.append({
            "case_type_id": case_type['id'],
            "case_type_name": case_type['name'],
            "doc_type": "overview"
        })
        ids.append(f"rights_{doc_count}")
        doc_count += 1
        
        # Steps and documents document
        doc = (
            f"Case Type: {case_type['name']}. "
            f"Steps to Take: {steps_text}. "
            f"Documents Needed: {docs_text}."
        )
        documents.append(doc)
        metadatas.append({
            "case_type_id": case_type['id'],
            "case_type_name": case_type['name'],
            "doc_type": "steps"
        })
        ids.append(f"rights_{doc_count}")
        doc_count += 1
        
        # Deadlines document
        if 'deadlines' in case_type:
            deadlines_text = ". ".join(
                [f"{d['action']}: {d['deadline']}" for d in case_type['deadlines']]
            )
            doc = (
                f"Case Type: {case_type['name']}. "
                f"Important Deadlines: {deadlines_text}."
            )
            documents.append(doc)
            metadatas.append({
                "case_type_id": case_type['id'],
                "case_type_name": case_type['name'],
                "doc_type": "deadlines"
            })
            ids.append(f"rights_{doc_count}")
            doc_count += 1
        
        # Relevant sections document
        if 'relevant_sections' in case_type:
            sections = case_type['relevant_sections']
            bns_text = ", ".join(sections.get('bns', []))
            other_text = ", ".join(sections.get('other_laws', []))
            doc = (
                f"Case Type: {case_type['name']}. "
                f"Relevant BNS Sections: {bns_text}. "
                f"Other Relevant Laws: {other_text}."
            )
            documents.append(doc)
            metadatas.append({
                "case_type_id": case_type['id'],
                "case_type_name": case_type['name'],
                "doc_type": "sections"
            })
            ids.append(f"rights_{doc_count}")
            doc_count += 1
    
    # Add legal terms
    for i, term in enumerate(rights_data.get('legal_terms', [])):
        doc = (
            f"Legal Term: {term['term']}. "
            f"Meaning: {term['meaning']}. "
            f"Hindi Meaning: {term.get('meaning_hi', '')}."
        )
        documents.append(doc)
        metadatas.append({
            "case_type_id": "legal_terms",
            "case_type_name": "Legal Terminology",
            "doc_type": "term"
        })
        ids.append(f"rights_{doc_count}")
        doc_count += 1
    
    # Evidence checklists — reviewed document lists, steps and statutory deadlines.
    # Indexed alongside rights so ordinary chat answers can cite them too.
    for tpl in load_json('evidence_checklists.json').get('templates', []):
        parts = [f"Evidence checklist: {tpl['title']} ({tpl.get('title_hi', '')}). {tpl.get('description', '')}"]
        parts += [f"Document needed: {d['name']} — {d.get('why', '')} How to get: {d.get('how_to_get', '')}"
                  for d in tpl.get('documents', [])]
        parts += [f"Step {i}: {s}" for i, s in enumerate(tpl.get('steps', []), 1)]
        parts += [f"Deadline: {dl.get('what', '')} — {dl.get('timeframe', '')}" for dl in tpl.get('deadlines', [])]
        parts += [f"Tip: {t}" for t in tpl.get('tips', [])]
        if tpl.get('helpline'):
            parts.append(f"Helpline: {tpl['helpline']}")

        documents.append(" ".join(parts))
        metadatas.append({
            "type": "evidence_checklist",
            "checklist_id": tpl['id'],
            "category": tpl.get('category', ''),
            "doc_type": "checklist"
        })
        ids.append(f"rights_{doc_count}")
        doc_count += 1

    batch_size = 40
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        rights_col.add(
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end]
        )

    print(f"  ✅ Added {doc_count} rights knowledge documents (incl. evidence checklists)")
    
    # ── 3. Legal Aid Directory Collection ──
    print("📚 Loading legal aid directory...")
    try:
        client.delete_collection("legal_aid")
    except:
        pass
    
    legal_aid_col = client.create_collection(
        name="legal_aid",
        embedding_function=ef,
        metadata={"description": "Legal aid contacts and helplines"}
    )
    
    legal_aid_data = load_json('legal_aid_directory.json')
    
    documents = []
    metadatas = []
    ids = []
    doc_count = 0
    
    # Helplines
    for helpline in legal_aid_data['helplines']:
        doc = (
            f"Helpline: {helpline['name']} ({helpline['name_hi']}). "
            f"Number: {helpline['number']}. "
            f"Description: {helpline['description']}. "
            f"Hours: {helpline['hours']}. "
            f"Toll Free: {'Yes' if helpline['toll_free'] else 'No'}."
        )
        documents.append(doc)
        metadatas.append({
            "type": "helpline",
            "name": helpline['name'],
            "number": helpline['number']
        })
        ids.append(f"legal_aid_{doc_count}")
        doc_count += 1
    
    # State and district contacts
    for state in legal_aid_data['states']:
        slsa = state['slsa']
        doc = (
            f"State: {state['name']} ({state['name_hi']}). "
            f"State Legal Services Authority: {slsa['name']}. "
            f"Phone: {slsa['phone']}. Website: {slsa['website']}. "
            f"Address: {slsa['address']}."
        )
        documents.append(doc)
        metadatas.append({
            "type": "state",
            "state": state['name'],
            "phone": slsa['phone']
        })
        ids.append(f"legal_aid_{doc_count}")
        doc_count += 1
        
        for district in state['districts']:
            doc = (
                f"District Legal Services Authority: {district['name']} "
                f"({district.get('name_hi', '')}) in {state['name']}. "
                f"Address: {district['dlsa_address']}. "
                f"Phone: {district['phone']}."
            )
            documents.append(doc)
            metadatas.append({
                "type": "district",
                "state": state['name'],
                "district": district['name'],
                "phone": district['phone']
            })
            ids.append(f"legal_aid_{doc_count}")
            doc_count += 1
    
    batch_size = 40
    for start in range(0, len(documents), batch_size):
        end = min(start + batch_size, len(documents))
        legal_aid_col.add(
            documents=documents[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end]
        )
    
    print(f"  ✅ Added {doc_count} legal aid entries")
    
    print("\n✅ RAG knowledge base setup complete!")
    print(f"   Database location: {CHROMA_DIR}")
    print("   Collections: ipc_bns, rights_knowledge, legal_aid")

if __name__ == '__main__':
    setup_rag()
