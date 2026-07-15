"""Corpus ingestion sanity: chunk counts, scalar metadata, real source URLs.

Requires the official_law collection to be built (python rag_setup.py --only official_law).
Run: python test_corpus_ingest.py
"""

import glob
import json
import os

import app

CORPUS_DIR = os.path.join(os.path.dirname(__file__), 'data', 'corpus')


def main():
    col = app.official_law_collection
    assert col is not None, "official_law collection not built - run rag_setup.py --only official_law"

    # count == non-empty JSONL lines (proves id uniqueness, no drops)
    non_empty = 0
    for path in glob.glob(os.path.join(CORPUS_DIR, '*.jsonl')):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and (json.loads(line).get('text') or '').strip():
                    non_empty += 1
    assert col.count() == non_empty, f"collection {col.count()} != non-empty lines {non_empty}"

    # a known chunk carries a real https official_url
    res = col.get(ids=["bns_2023_en:preamble"], include=['metadatas'])
    metas = res.get('metadatas') or []
    if metas:
        url = metas[0].get('official_url', '')
        assert url.startswith('https://'), f"expected https official_url, got {url!r}"
        # metadata all scalar
        for k, v in metas[0].items():
            assert isinstance(v, (str, int, float, bool)), f"non-scalar metadata {k}={v!r}"

    # retrieval returns act-tagged statute for a plain query
    chunks = app.retrieve_chunks("punishment for theft", col, n_results=3)
    assert chunks and any(c['act'] for c in chunks), "no act-tagged chunks for a statute query"

    print(f"OK - corpus ingest: {col.count()} chunks, scalar metadata, real source URLs")


if __name__ == '__main__':
    main()
