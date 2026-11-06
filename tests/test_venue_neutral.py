"""Keep publication metadata generic without changing scientific records."""

import hashlib
import json
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class VenueNeutralTests(unittest.TestCase):
    def test_document_preambles_are_venue_neutral(self):
        for relative in ("paper/Rebalancing-Connection-Reference.tex",
                         "paper/submission-compact/Main_Manuscript.tex",
                         "paper/submission-compact/Online_Appendix.tex"):
            with self.subTest(document=relative):
                text = (ROOT / relative).read_text()
                self.assertIn("\\documentclass[manuscript,nonacm]{acmart}", text)
                self.assertNotIn("\\acmJournal{", text)

    def test_non_publication_fields_are_preserved(self):
        manifest = json.loads((ROOT / "provenance/venue-neutral-check.json").read_text())
        self.assertEqual(len(manifest["files"]), 4)
        for entry in manifest["files"]:
            with self.subTest(file=entry["file"]):
                record = json.loads((ROOT / "evidence" / entry["file"]).read_text())
                payload = {k: v for k, v in record.items()
                           if k not in entry["excluded_metadata_keys"]}
                actual = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
                self.assertEqual(actual, entry["preserved_payload_sha256"])
                self.assertNotIn("venue_target", record)

    def test_archives_match_the_evidence_directory(self):
        manifest = json.loads((ROOT / "evidence/MANIFEST.json").read_text())
        names = set(manifest["files"]) | {"MANIFEST.json"}
        for relative in ("paper/reviewer-evidence.zip", "paper/submission-compact/reviewer-evidence.zip"):
            with self.subTest(archive=relative), zipfile.ZipFile(ROOT / relative) as archive:
                self.assertEqual(set(archive.namelist()), {"reviewer-evidence/" + name for name in names})
                for name in names:
                    self.assertEqual(archive.read("reviewer-evidence/" + name),
                                     (ROOT / "evidence" / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
