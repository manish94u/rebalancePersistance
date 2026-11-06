"""Check that extraction preserves the original research and source files.

This checks the two-document union: an item moved to the supplement is not a
deletion. Cross-document reference macros and heading levels are navigation
changes, so they are normalized before comparing protected source blocks.
"""

from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent
manifest = json.loads((ROOT / "relocation-manifest.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for name, sha in manifest["source_hashes"].items():
    assert digest(SOURCE / name) == sha, f"Original changed: {name}"
for name, sha in manifest["copied_assets"].items():
    assert digest(ROOT / name) == sha, f"Copied asset changed: {name}"

original = "\n".join((SOURCE / name).read_text()
                     for name in manifest["source_hashes"] if name.endswith(".tex"))
revised = "\n".join(p.read_text() for p in (ROOT / "sections").glob("*.tex"))
revised += (ROOT / "Main_Manuscript.tex").read_text()


def normalize(value):
    value = re.sub(r"\\(?:suppref|mainref)\{([^}]+)\}", r"\\ref{\1}", value)
    value = re.sub(r"\\(ref|eqref)\{[MS]-([^}]+)\}", r"\\\1{\2}", value)
    value = re.sub(r"\(\\ref\{([^}]+)\}\)", r"\\eqref{\1}", value)
    return re.sub(r"\s+", "", value)


def blocks(text, names):
    result = []
    for name in names:
        pattern = r"\\begin\{" + re.escape(name) + r"\}.*?\\end\{" + re.escape(name) + r"\}"
        result.extend(re.findall(pattern, text, re.S))
    return result


report = {"original_files_unchanged": len(manifest["source_hashes"]),
          "copied_assets_byte_identical": len(manifest["copied_assets"])}
for kind, names in {
    "equations": ["equation", "align", "align*"],
    "proofs": ["proof", "proposition"],
    "tables": ["table", "table*", "longtable"],
    "figures": ["figure", "figure*"],
    "original_algorithms": ["algorithm"],
}.items():
    protected = blocks(original, names)
    available = {normalize(b) for b in blocks(revised, names)}
    missing = [b for b in protected if normalize(b) not in available]
    report[kind] = {"original_blocks": len(protected), "missing_or_changed": len(missing)}
    if missing:
        print(kind, "MISSING", [b[:180] for b in missing])
    assert not missing, f"Protected {kind} changed or lost"


def citations(text):
    return {key.strip() for group in re.findall(r"\\cite\w*\{([^}]+)\}", text)
            for key in group.split(",")}


assert citations(original) <= citations(revised), "Cited reference was lost"
report["original_citation_keys_preserved"] = len(citations(original))

# Every nontrivial prose line in the original body must remain in one of the
# documents. Heading level, document wrappers, and layout directives may move.
corpus = normalize(revised)
missing_lines = []
for name in manifest["source_hashes"]:
    if not name.endswith(".tex"):
        continue
    lines = (SOURCE / name).read_text().splitlines()
    if name == "Rebalancing-Connection-Reference.tex":
        lines = lines[126:2000]
    for line in lines:
        clean = line.strip()
        if len(clean) < 25 or clean.startswith(("\\", "%", "<")):
            continue
        if normalize(clean) not in corpus:
            missing_lines.append({"source": name, "line": clean})
report["unmatched_prose_lines"] = missing_lines
assert not missing_lines, "Prose lines were dropped rather than relocated"
(ROOT / "preservation-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
