"""Check release boundaries and the preserved document structure."""

import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("checker", ROOT / "tools/check_repository.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublicationPackageTests(unittest.TestCase):
    def test_main_paper_has_43_explicitly_cited_references(self):
        compact = ROOT / "paper/submission-compact"
        text = (compact / "Main_Manuscript.tex").read_text()
        text += "\n".join(path.read_text() for path in
                          sorted((compact / "sections").glob("main-*.tex")))
        keys = {key.strip() for group in re.findall(r"\\cite\w*\{([^}]+)\}", text)
                for key in group.split(",")}
        self.assertEqual(len(keys), 43)
        self.assertNotIn(r"\nocite", text)
        entries = re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,",
                             (compact / "example.bib").read_text())
        for key in keys:
            self.assertEqual(entries.count(key), 1, key)

    def test_imported_sources_match_documented_digests(self):
        self.assertGreater(checker.verify_imports(), 100)

    def test_import_scan(self):
        checker.scan_imports()

    def test_missing_import_fails(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "provenance").mkdir()
            manifest = {"files": [{"path": "absent.txt", "source_sha256": "0" * 64}]}
            (root / "provenance/import-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                checker.verify_imports(root)

    def test_path_escape_fails(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "provenance").mkdir()
            manifest = {"files": [{"path": "../outside.txt", "source_sha256": "0" * 64}]}
            (root / "provenance/import-manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                checker.verify_imports(root)

    def test_reference_prose_and_math_counts(self):
        report = json.loads((ROOT / "paper/submission-compact/preservation-check.json").read_text())
        self.assertEqual(report["original_citation_keys_preserved"], 51)
        self.assertEqual(report["equations"]["original_blocks"], 48)
        self.assertFalse(report["unmatched_prose_lines"])
        for kind in ("equations", "proofs", "tables", "figures", "original_algorithms"):
            self.assertEqual(report[kind]["missing_or_changed"], 0)


if __name__ == "__main__":
    unittest.main()
