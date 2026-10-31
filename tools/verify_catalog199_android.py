"""Accept only complete, successful Android results for the exact candidate."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from restore_catalog199_candidate import EXPECTED_SHA256

CLASS = 'ru.dlyasvoih.app.CatalogReview199Test'
EXPECTED = {
    'favoritesReadingAndStableIdentitiesSurvivePackImportAndReopen',
    'repeatedReleaseIsRejectedWithoutChangingInstalledContent',
    'mismatchedAnnouncedVersionIsRejectedWithoutChangingCatalog198',
}

def verify(reports, output):
    files = sorted(Path(reports).glob('TEST-*.xml'))
    assert files, 'Missing Android reports'
    cases = []
    for path in files:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
        assert suites, 'Missing test suite'
        for suite in suites:
            assert int(suite.attrib['tests']) == len(suite.findall('testcase'))
            assert all(int(suite.attrib.get(key,0)) == 0 for key in ('failures','errors','skipped','disabled'))
            for case in suite.findall('testcase'):
                assert case.attrib.get('classname') == CLASS, 'Wrong Android test class'
                assert not any(case.find(tag) is not None for tag in ('failure','error','skipped'))
                cases.append(case.attrib['name'])
    assert len(cases) == len(EXPECTED) and set(cases) == EXPECTED, 'Incomplete or duplicate Android test results'
    proof = dict(androidApi=30, androidVersion='11', testClass=CLASS, tests=cases,
        failures=0, errors=0, skipped=0, actualReleaseZipImported=True,
        candidateSha256=EXPECTED_SHA256, previousCatalog=198, contentVersion=199,
        stablePreviousIdentities=2855, finalCards=2855, finalImages=2403,
        favoritesAndAllReadingFieldsPreserved=True, newImagesDecodedOnAndroid=86,
        repeatImportRejected=True, mismatchedVersionRejected=True)
    Path(output).write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))
    return proof

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    verify(args.reports,args.output)
