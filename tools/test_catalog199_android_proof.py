import contextlib
import io
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from verify_catalog199_android import CLASS, EXPECTED, verify

class AndroidProofGateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)

    def report(self, names=None, **attributes):
        names = sorted(EXPECTED) if names is None else names
        suite = ET.Element('testsuite',dict(tests=str(len(names)),failures='0',errors='0',skipped='0'))
        suite.attrib.update(attributes)
        for name in names: ET.SubElement(suite,'testcase',dict(classname=CLASS,name=name))
        ET.ElementTree(suite).write(self.root/'TEST-import.xml')
        return suite

    def check(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify(self.root,self.root/'proof.json')

    def test_complete_run_is_accepted(self):
        self.report(); self.assertEqual(86,self.check()['newImagesDecodedOnAndroid'])

    def test_missing_reports_are_rejected(self):
        with self.assertRaises(AssertionError): self.check()

    def test_partial_or_duplicate_run_is_rejected(self):
        for names in (sorted(EXPECTED)[:2],[sorted(EXPECTED)[0]]*3):
            self.report(names)
            with self.assertRaises(AssertionError): self.check()

    def test_failures_errors_and_skips_are_rejected(self):
        for key in ('failures','errors','skipped'):
            self.report(**{key:'1'})
            with self.assertRaises(AssertionError): self.check()

    def test_case_level_failure_or_wrong_class_is_rejected(self):
        for tag in ('failure','error','skipped'):
            suite=self.report(); ET.SubElement(suite.find('testcase'),tag)
            ET.ElementTree(suite).write(self.root/'TEST-import.xml')
            with self.assertRaises(AssertionError): self.check()
        suite=self.report(); suite.find('testcase').set('classname','OtherTest')
        ET.ElementTree(suite).write(self.root/'TEST-import.xml')
        with self.assertRaises(AssertionError): self.check()

if __name__ == '__main__': unittest.main()
