"""Converter matching: section normalization + offence-name search (bug 5).

Run: python test_convert_match.py
"""

import app

IPC_NAME_FIELDS = ['offence', 'ipc_title', 'bns_title', 'description']
CRPC_NAME_FIELDS = ['offence', 'crpc_title', 'bnss_title', 'description']


def ipc(q, field='ipc_section'):
    return app._match_entries(app.IPC_BNS_DATA, q, field, IPC_NAME_FIELDS)


def crpc(q, field='crpc_section'):
    return app._match_entries(app.BNSS_CRPC_DATA, q, field, CRPC_NAME_FIELDS)


def main():
    # subsection-insensitive number match: stored as '303(2)', query '303'
    r = ipc('303', 'bns_section')
    assert any(e['ipc_section'] in ('378', '379') for e in r), r

    # exact forward number
    assert ipc('302')[0]['bns_section'] == '103', ipc('302')

    # offence-name substring search works (UI promises it)
    assert ipc('cheating'), "name search 'cheating' returned nothing"
    assert ipc('murder'), "name search 'murder' returned nothing"

    # CrPC forward
    assert crpc('154')[0]['bnss_section'] == '173', crpc('154')

    # case-insensitive name
    assert ipc('MURDER'), "case-insensitive name search failed"

    # unknown number => empty
    assert ipc('99999') == [], "unknown section should return nothing"

    print("OK - converter matching: normalization + name search + case-insensitivity")


if __name__ == '__main__':
    main()
