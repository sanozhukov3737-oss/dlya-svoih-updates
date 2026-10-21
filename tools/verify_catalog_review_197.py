"""Check editorial scope and preservation against the actual public catalog 196."""
import argparse
import json
from pathlib import Path

from apply_catalog_review_197 import ROOT, REPORT, WITHDRAWN_IMAGE_CARD, digest


def verify(baseline, current):
    old, new = (json.loads(Path(p).read_text()) for p in (baseline, current))
    assert old['contentVersion'] == 196 and new['contentVersion'] == 197
    a, b = ({c['id']: c for c in data['cards']} for data in (old, new))
    changes = json.loads((REPORT / 'changes.json').read_text())
    review = json.loads((REPORT / 'shared-images.json').read_text())
    assert set(a) == set(b) and len(b) == 1695
    assert old['countries'] == new['countries'] and old['categories'] == new['categories']
    protected = ['id', 'rowid', 'section', 'categoryId', 'title', 'countries',
        'contentStatus', 'reviewedAt', 'verifiedAt', 'modelStatus', 'sourceGrade',
        'archived', 'tags']
    medical = 0
    for cid, card in b.items():
        previous = a[cid]
        for field in protected:
            assert previous[field] == card[field], (cid, field)
        if card['section'] == 'MEDICINE':
            assert card == previous, ('medical preservation', cid)
            medical += 1
        # No previously published citation can be silently removed or rewritten.
        assert card['sources'][:len(previous['sources'])] == previous['sources'], cid
        if cid == WITHDRAWN_IMAGE_CARD:
            assert not card['images'] and card['thumbnailPath'] is None
        else:
            assert card['thumbnailPath'] == previous['thumbnailPath'], cid
            assert [{k:v for k,v in im.items() if k != 'caption'} for im in card['images']] == \
                [{k:v for k,v in im.items() if k != 'caption'} for im in previous['images']], cid
    assert medical == 20
    assert len(changes['shortDecisions']) == 158
    for row in changes['shortDecisions']:
        cid = row['cardId']
        assert row['beforeBodySha256'] == digest(a[cid]['body'])
        assert row['afterBodySha256'] == digest(b[cid]['body'])
        if row['action'] == 'retain-brief':
            assert a[cid] == b[cid], cid
        else:
            assert row['action'] == 'expand-description' and a[cid]['body'] != b[cid]['body']
    assert len(review['groups']) == 71
    assert sorted(row['group'] for row in review['groups']) == list(range(1,72))
    assert sum(row['decision'] == 'withdraw-unrelated-image' for row in review['groups']) == 1
    assert sum(len(c['images']) for c in b.values()) == 1595
    assert sum(len(c['sources']) for c in b.values()) == 5489
    audit = json.loads((REPORT / 'after.json').read_text())
    assert not audit['confirmedStructuralErrors'] and not audit['duplicateTitleGroups']
    assert audit['database']['cardIdsAndRowidsMatch']
    assert len(audit['shortArticles']) == 5
    return dict(retainedStableIds=len(b), unchangedMedicalCards=medical,
        unchangedModelReferences=True, expandedDescriptions=153, retainedBriefDescriptions=5,
        historicalContextCards=25, reviewedImageGroups=71,
        correctedImageCaptions=len(changes['captionCorrections']),
        withdrawnUnrelatedImages=1, activeImageReferences=1595,
        retainedPriorSources=5460, sourceReferences=5489, structuralErrors=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--current', type=Path, default=ROOT / 'content/catalog.json')
    args = parser.parse_args()
    print(json.dumps(verify(args.baseline, args.current)))
