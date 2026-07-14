"""Convert the official RTI Act 2005 PDF into a corpus JSONL chunk file.

Download the official PDF first and place it at:
    data/raw/rti_act_2005.pdf
(source: https://rti.dopt.gov.in/rtiact.html)

Then run:
    python scripts/rti_to_jsonl.py

Output: data/corpus/rti_act_2005_en.jsonl  (same shape as the other corpus files,
so rag_setup.py's build_official_law picks it up automatically).
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(ROOT, 'data', 'raw', 'rti_act_2005.pdf')
OUT_PATH = os.path.join(ROOT, 'data', 'corpus', 'rti_act_2005_en.jsonl')

OFFICIAL_URL = "https://rti.dopt.gov.in/Writereaddata/RTI%20Act,%202005%20(Amended)-English%20Version.PDF"
OFFICIAL_LANDING = "https://rti.dopt.gov.in/rtiact.html"

SECTION_RE = re.compile(r'(?m)^\s*(\d+[A-Z]?)\.\s')  # "6. ", "19A. " at line start
MAX_CHARS = 1500


def _chunks_from_text(full_text):
    """Split by section-heading markers; fall back to fixed windows."""
    marks = list(SECTION_RE.finditer(full_text))
    if len(marks) >= 5:
        for i, m in enumerate(marks):
            start = m.start()
            end = marks[i + 1].start() if i + 1 < len(marks) else len(full_text)
            body = full_text[start:end].strip()
            if body:
                yield m.group(1), body
        return
    # Fallback: fixed windows
    for i in range(0, len(full_text), MAX_CHARS):
        body = full_text[i:i + MAX_CHARS].strip()
        if body:
            yield str(i // MAX_CHARS), body


def main():
    if not os.path.exists(PDF_PATH):
        print(f"RTI Act PDF not found at {PDF_PATH}")
        print("Download the official PDF from https://rti.dopt.gov.in/rtiact.html and save it there, then rerun.")
        return 0

    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf is not installed. Run: pip install pypdf")
        return 1

    reader = PdfReader(PDF_PATH)
    # keep a page index so we can record page_start on each chunk
    page_texts = [(p + 1, (page.extract_text() or '')) for p, page in enumerate(reader.pages)]
    full_text = "\n".join(t for _, t in page_texts)
    full_text = re.sub(r'[ \t]+', ' ', full_text)

    # crude page lookup: cumulative char offsets
    offsets, acc = [], 0
    for pno, t in page_texts:
        offsets.append((acc, pno))
        acc += len(t) + 1

    def page_for(pos):
        page = 1
        for off, pno in offsets:
            if pos >= off:
                page = pno
            else:
                break
        return page

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    count = 0
    with open(OUT_PATH, 'w', encoding='utf-8') as out:
        pos = 0
        for sec, body in _chunks_from_text(full_text):
            page = page_for(full_text.find(body, max(0, pos)))
            pos += len(body)
            rec = {
                "chunk_id": f"rti_act_2005_en:section-{sec}",
                "heading": f"Section {sec}",
                "section_id": f"section-{sec}",
                "source_id": "rti_act_2005_en",
                "page_start": page,
                "page_end": page,
                "text": body,
                "metadata": {
                    "act": "The Right to Information Act, 2005",
                    "title": f"RTI Act, 2005 — Section {sec}",
                    "jurisdiction": "India",
                    "document_type": "act",
                    "language": "en",
                    "status": "in_force",
                    "official_url": OFFICIAL_URL,
                    "official_landing_url": OFFICIAL_LANDING,
                },
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"Wrote {count} RTI Act chunks -> {OUT_PATH}")
    print("Spot-check a few chunks, then rebuild: python rag_setup.py --only official_law")
    return 0


if __name__ == '__main__':
    sys.exit(main())
