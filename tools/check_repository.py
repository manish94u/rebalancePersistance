"""Verify imported research bytes and scan the release boundary without a network.

This is a packaging check, not an experimental validity test or a full secret
scanner. It reports names of suspect files, never matching secret values.
The evidence has its own exact-file-set manifest; the larger import manifest
tracks the manuscripts, figures, and simulator sources copied for this release.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "resource identifier": re.compile(rb"ocid1\.[a-z0-9]+\.[a-z0-9.-]{30,}"),
    "internal endpoint": re.compile(rb"(?:oraclecorp\.com|oraclevcn\.com)", re.I),
    "author-local path": re.compile(rb"/(?:Users|scratch)/[A-Za-z0-9_-]+/"),
}


def digest(path):
    """Hash actual bytes so a changed value cannot hide behind reformatting."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_imports(root=ROOT):
    manifest = json.loads((root / "provenance/import-manifest.json").read_text())
    seen = set()
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in seen:
            raise ValueError("Unsafe or duplicate import path")
        seen.add(relative.as_posix())
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing/non-regular import: " + relative.as_posix())
        if digest(path) != entry.get("packaged_sha256", entry["source_sha256"]):
            raise ValueError("Imported bytes changed: " + relative.as_posix())
    return len(seen)


def scan_bytes(name, data):
    """Return classifications only; do not expose matched credentials in logs."""
    return [name + ": " + label for label, regex in SENSITIVE_PATTERNS.items()
            if regex.search(data)]


def scan_imports(root=ROOT):
    manifest = json.loads((root / "provenance/import-manifest.json").read_text())
    issues = []
    for entry in manifest["files"]:
        name = entry["path"]
        path = root / name
        if path.suffix == ".zip":
            # ZIP members are scanned without extracting untrusted paths.
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    if member.file_size > 50_000_000:
                        raise ValueError("Oversized archive member: " + member.filename)
                    issues.extend(scan_bytes(name + "!" + member.filename, archive.read(member)))
        else:
            issues.extend(scan_bytes(name, path.read_bytes()))
    if issues:
        raise ValueError("Release-boundary scan requires review:\n" + "\n".join(issues))


def main():
    imports = verify_imports()
    scan_imports()
    # Load the archived utility by path: no package install and no execution of
    # its command-line main routine are required for the manifest verification.
    spec = importlib.util.spec_from_file_location("archived_analysis", ROOT / "evidence/reanalyse.py")
    analysis = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analysis)
    evidence_files = analysis.verify_manifest(ROOT / "evidence")
    checkpoint = json.loads((ROOT / "evidence/model/frozen-policy.json").read_text())
    parameters = analysis.validate_checkpoint(checkpoint)
    print(json.dumps({"imported_files_verified": imports,
                      "evidence_files_verified": evidence_files,
                      "parameters_per_network": parameters,
                      "release_boundary_scan": "passed"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, AssertionError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
