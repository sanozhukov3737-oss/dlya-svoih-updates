"""Correct per-card image positions imported as global batch positions in v49."""
import json
from build_catalog import ROOT, PRODUCTION_CATALOG, PRODUCTION_DATABASE, build


def main():
    data = json.loads(PRODUCTION_CATALOG.read_text(encoding='utf-8'))
    changed = []
    for card in data['cards']:
        manual = [image for image in card['images'] if image['id'].startswith('manual-v49-')]
        if not manual:
            continue
        if len(card['images']) != 1:
            raise ValueError(f'Expected one imported manual image: {card["id"]}')
        image = manual[0]
        if image['position'] != 0:
            changed.append((image['id'], image['position'], 0))
            image['position'] = 0
    data['contentVersion'] = max(data['contentVersion'], 93)
    PRODUCTION_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = build(PRODUCTION_CATALOG, PRODUCTION_DATABASE)
    print(json.dumps({'changed': changed, 'contentVersion': data['contentVersion'], **result}, ensure_ascii=False))


if __name__ == '__main__':
    main()
