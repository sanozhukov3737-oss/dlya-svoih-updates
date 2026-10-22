#!/usr/bin/env python3
"""Summarize measured events without treating emulator/debug timings as phone latency."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'medianMs': round(statistics.median(values), 3),
            'p95Ms': round(values[max(0, math.ceil(0.95*len(values))-1)], 3),
            'maxMs': round(values[-1], 3)}


def delta(a, b):
    return (b['atNs']-a['atNs'])/1e6


def summarize(raw):
    assert raw['passed'] is True
    events = raw['events']
    requests = defaultdict(dict)
    draws = {}
    for event in events:
        if 'requestId' in event:
            requests[event['requestId']][event['kind']] = event
        if event['kind'] == 'firstDraw':
            draws.setdefault(event['requestIdentity'], event)
    heroes = {card['heroPath'] for card in raw['cards'] if card['heroPath']}
    request_rows = []
    for number, event in sorted(requests.items()):
        first = event.get('requestStart')
        if not first:
            continue
        final = event.get('requestSuccess')
        row = {'id': number, 'batch': first['startedBatch'], 'phase': first['startedPhase'],
               'path': first['data'].removeprefix('file:///android_asset/'),
               'status': ('success' if final else 'error' if 'requestError' in event
                          else 'cancel' if 'requestCancel' in event else 'unfinishedAtCapture'),
               'source': final.get('source') if final else None}
        row['hero'] = row['path'] in heroes
        if final:
            row.update(totalMs=delta(first, final), width=final['width'],
                       height=final['height'], bytes=final['bytes'])
            drawn = draws.get(final['requestIdentity'])
            if drawn:
                row['successToFirstDrawMs'] = delta(final, drawn)
                row['startToFirstDrawMs'] = delta(first, drawn)
        for start, end, label in (('resolveStart', 'resolveEnd', 'resolveMs'),
                                  ('fetchStart', 'fetchEnd', 'fetchMs'),
                                  ('decodeStart', 'decodeEnd', 'decodeMs')):
            if start in event and end in event:
                row[label] = delta(event[start], event[end])
        if 'decodeStart' in event:
            row['decodeThread'] = event['decodeStart']['thread']
        request_rows.append(row)
    sections = []
    for batch in range(1, 4):
        for phase in ('open', 'forward', 'return'):
            for hero_only in (False, True):
                rows = [r for r in request_rows if r['batch'] == batch and r['phase'] == phase
                        and (not hero_only or r['hero'])]
                success = [r for r in rows if r['status'] == 'success']
                hits = sum(r['source'] == 'MEMORY_CACHE' for r in success)
                sections.append({'batch': batch, 'phase': phase, 'scope': 'hero' if hero_only else 'all',
                    'requests': len(rows), 'status': dict(Counter(r['status'] for r in rows)),
                    'sources': dict(Counter(r['source'] for r in success)),
                    'memoryHitRatePct': round(hits/len(success)*100, 2) if success else None,
                    'request': distribution([r['totalMs'] for r in success]),
                    'decode': distribution([r['decodeMs'] for r in rows if 'decodeMs' in r]),
                    'successToFirstDraw': distribution([r['successToFirstDrawMs'] for r in success
                                                       if 'successToFirstDrawMs' in r])})
    observations = []
    for phase in ('open', 'forward', 'return'):
        rows = [r for r in raw['observations'] if r['leg'] == phase and r['path']]
        samples = [(r['firstDrawAtNs']-r['inputAtNs'])/1e6 for r in rows]
        observations.append({'phase': phase, 'n': len(rows),
            'drawAlreadyRecordedBeforeInput': sum(t < 0 for t in samples),
            'inputToFirstDrawNonNegative': distribution([max(0, t) for t in samples])})
    succeeded = [r for r in request_rows if r['status'] == 'success']
    return {'api': raw['sdk'], 'passed': True, 'sourceCommit': raw['sourceCommit'],
        'packageName': raw['packageName'], 'cacheMaxBytes': raw['cacheMaxBytes'],
        'memoryClassMiB': raw['memoryClassMiB'], 'isLowRamDevice': raw['isLowRamDevice'],
        'diskCacheEnabled': raw['diskCacheEnabled'], 'observationCount': len(raw['observations']),
        'requestCount': len(request_rows), 'status': dict(Counter(r['status'] for r in request_rows)),
        'sources': dict(Counter(r['source'] for r in succeeded)),
        'decode': distribution([r['decodeMs'] for r in request_rows if 'decodeMs' in r]),
        'fileRequest': distribution([r['totalMs'] for r in succeeded if r['source'] != 'MEMORY_CACHE']),
        'cachedRequest': distribution([r['totalMs'] for r in succeeded if r['source'] == 'MEMORY_CACHE']),
        'successToFirstDraw': distribution([r['successToFirstDrawMs'] for r in succeeded
                                           if 'successToFirstDrawMs' in r]),
        'decodeThreads': dict(Counter(r['decodeThread'] for r in request_rows if 'decodeThread' in r)),
        'cacheSnapshots': raw['cacheSnapshots'], 'byBatchAndPhase': sections,
        'firstDrawObservations': observations, 'requests': request_rows,
        'limits': ['instrumented debug sources, not the published optimized APK',
                   'emulator only; no physical-phone speed claim',
                   'firstDraw is a CPU painter call, not actual display presentation; adjacent pages can draw during a swipe',
                   'input marker precedes test gesture injection; includes gesture and test scheduling',
                   'cache is emptied per batch; OS file cache and JIT are not reset',
                   'hit rate counts image requests, not every navigation; retained painters need no request',
                   'prefetch request belongs to the phase in which it began']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('raw', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(json.loads(args.raw.read_text()))
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ('requests', 'byBatchAndPhase', 'cacheSnapshots')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
