"""Assemble two submission documents by relocating existing source passages.

The parent manuscript is read-only. Line selections refer to its preserved
October revision. This is a mechanical extraction, not a result generator:
no measurements, plotted coordinates, or bibliography records are computed.
Small editorial bridges live separately in editorial-bridges.tex for review.
"""

from pathlib import Path
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent
ORIGINAL = "Rebalancing-Connection-Reference.tex"
records = []
sources = {}
documents = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def take(name, first=1, last=None):
    """Copy an inclusive line range, recording its original content hash."""
    path = SOURCE / name
    sources[name] = digest(path)
    lines = path.read_text().splitlines(keepends=True)
    last = len(lines) if last is None else last
    value = "".join(lines[first - 1:last])
    records.append({"source": name, "first": first, "last": last,
                    "sha256": hashlib.sha256(value.encode()).hexdigest()})
    return value


def original(first, last):
    return take(ORIGINAL, first, last)


def bridge(name):
    text = (ROOT / "editorial-bridges.tex").read_text()
    return text.split(f"% BEGIN {name}\n", 1)[1].split(f"% END {name}", 1)[0]


def save_section(name, value):
    for record in records:
        record.setdefault("destination", "sections/" + name + ".tex")
    documents[name] = value
    return "\\input{sections/" + name + "}\n"


def remove_inputs(value):
    return re.sub(r"\\input\{(?:mumbai-startup-section|live-dql-scaleout-section|ttl-reconnection-section|scaleout-recovery-section)\}", "", value)


def sectionize(value):
    """Promote the first subsection of a standalone trial to an appendix section."""
    value = value.replace("\\subsection{", "\\section{", 1)
    return value.replace("\\subsubsection{", "\\subsection{")


def demote(value):
    return re.sub(r"\\(section|subsection|subsubsection)\{",
                  lambda m: "\\" + {"section": "subsection", "subsection": "subsubsection",
                                      "subsubsection": "paragraph"}[m[1]] + "{", value)


def expand_inputs(value):
    """Inline supporting TeX so each document has an explicit dependency graph."""
    def expand(match):
        name = match[1]
        return expand_inputs(take(name if name.endswith(".tex") else name + ".tex"))
    return re.sub(r"\\input\{([^}]+)\}", expand, value)


main = ""
main += save_section("main-introduction", original(127, 185))
main += save_section("main-related", original(186, 219) + bridge("allocation-context")
                     + original(296, 338) + bridge("adaptation-context")
                     + original(339, 394) + bridge("related"))
main += save_section("main-system", bridge("system") + original(501, 576)
                     + "\\afterpage{\n" + original(405, 413) + "}\n")
main += save_section("main-model", original(601, 787) + original(823, 910) + bridge("model"))
main += save_section("main-policy", original(1147, 1205) + original(911, 956)
                     + bridge("contract") + original(974, 1016)
                     + original(1684, 1709) + bridge("algorithm")
                     + original(1726, 1756) + bridge("runtime"))
main += save_section("main-cloud", take("mumbai-experimental-section.tex", 1, 84)
                     + bridge("timing") + take("mumbai-experimental-section.tex", 112, 136)
                     + take("live-dql-scaleout-section.tex") + bridge("ttl"))
main += save_section("main-scaleout", take("locked-evidence-section.tex", 1, 9)
                     + take("scaleout-recovery-section.tex", 1, 101)
                     + bridge("scaleout"))
main += save_section("main-holdout", bridge("holdout-heading")
                     + take("locked-evidence-section.tex", 87, 96)
                     + take("locked-evidence-section.tex", 124, 173)
                     + take("locked-evidence-section.tex", 244, 279)
                     + take("locked-evidence-section.tex", 295, 307)
                     + bridge("ablation") + take("locked-evidence-section.tex", 521, 534)
                     + bridge("repository"))
main += save_section("main-discussion", original(1869, 1890) + bridge("evaluation-context")
                     + original(1891, 1905) + original(1943, 1949)
                     + original(1950, 1969) + bridge("conclusion"))

# Detailed passages remain intact, with short repeated definitions where a
# supplementary section would otherwise lose its context.
supp = ""
supp += save_section("supp-mathematics", bridge("math-heading") + original(788, 829)
                     + original(1044, 1146))
supp += save_section("supp-notation", take("notation-appendix.tex"))
supp += save_section("supp-runtime", bridge("runtime-heading") + original(958, 972)
                     + original(1017, 1043) + original(1207, 1864))
supp += save_section("supp-features", take("model-implementation-appendix.tex"))
supp += save_section("supp-literature", bridge("literature-heading") + original(220, 295))
supp += save_section("supp-system", original(395, 404) + original(414, 500) + original(577, 600))
supp += save_section("supp-cloud-timing", bridge("cloud-heading")
                     + take("mumbai-experimental-section.tex", 85, 116))
supp += save_section("supp-startup", sectionize(take("mumbai-startup-section.tex")))
supp += save_section("supp-ttl", sectionize(expand_inputs(take("ttl-reconnection-section.tex"))))
supp += save_section("supp-scaleout", bridge("scaleout-heading")
                     + take("scaleout-recovery-section.tex", 102))
supp += save_section("supp-holdout", bridge("holdout-detail-heading")
                     + take("locked-evidence-section.tex", 12))
supp += save_section("supp-diagnostics", take("action-diagnostics-appendix.tex"))
supp += save_section("supp-discussion", bridge("discussion-heading")
                     + original(1893, 1949) + demote(original(1950, 1999)))

for name, value in list(documents.items()):
    documents[name] = expand_inputs(value)

# Cross-document references are explicit in the printed text and use local
# PDF links. Imports have prefixes so equal label names in explanatory
# material never shadow main-paper labels.
groups = {"main": {}, "supp": {}}
for name, value in documents.items():
    group = name.split("-", 1)[0]
    groups[group][name] = value
labels = {g: set(re.findall(r"\\label\{([^}]+)\}", "\n".join(values.values())))
          for g, values in groups.items()}
external = {"main": set(), "supp": set()}
for group, values in groups.items():
    other = "supp" if group == "main" else "main"
    prefix = "S-" if group == "main" else "M-"
    for name, value in values.items():
        def reference(match):
            key = match[2]
            if key in labels[group]:
                return match[0]
            if key not in labels[other]:
                raise ValueError(f"Unknown reference {key} in {name}")
            external[group].add(key)
            command = "suppref" if group == "main" else "mainref"
            # eqref retains parentheses; the reference macro states the document.
            ref = "\\" + command + "{" + key + "}"
            return "(" + ref + ")" if match[1] == "eqref" else ref
        value = re.sub(r"\\(ref|eqref)\{([^}]+)\}", reference, value)
        value = re.sub(r"(\\suppref\{[^}]+\})\s+of the Online\s+Supplementary Material", r"\1", value)
        # Float barriers are not evidence; keep them only at appendix boundaries.
        value = value.replace("\\FloatBarrier", "")
        documents[name] = value

preamble = "\\ifdefined\\pdfminorversion\\pdfminorversion=7\\fi\n\\RequirePackage{xr-hyper}\n" + original(1, 30)
preamble += r"""
\usepackage{afterpage}
\newcommand{\suppref}[1]{\ref{S-#1} of the Online Supplementary Material}
\newcommand{\mainref}[1]{\ref{M-#1} of the main paper}
"""
front = original(31, 126)
main_text = preamble + "\\externaldocument[S-]{Online_Appendix}\n" + front + main
main_text += "\\FloatBarrier\n\\bibliographystyle{ACM-Reference-Format}\n\\bibliography{example}\n\\end{document}\n"

supp_front = original(31, 52)
supp_front = re.sub(r"\\title\[[^\n]+\n", r"\\title[Online Supplementary Material]{Online Supplementary Material: Probe-Guided Rebalancing of Persistent Subscription Connections}\n", supp_front)
supp_front += "\\begin{CCSXML}" + front.split("\\begin{CCSXML}", 1)[1].split("\\maketitle", 1)[0]
supp_text = preamble + "\\externaldocument[M-]{Main_Manuscript}\n" + supp_front
supp_text += bridge("supp-front") + supp
supp_text += "\\FloatBarrier\n\\bibliographystyle{ACM-Reference-Format}\n\\bibliography{example}\n\\end{document}\n"

for name, value in documents.items():
    dest = ROOT / "sections" / (name + ".tex")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(value)
(ROOT / "Main_Manuscript.tex").write_text(main_text)
(ROOT / "Online_Appendix.tex").write_text(supp_text)

# Only copy assets used by these sources, not confidential raw archives.
assets = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", "\n".join(documents.values()))
assets += ["example.bib", "vendor/acmart.cls", "vendor/ACM-Reference-Format.bst", "reviewer-evidence.zip"]
asset_hashes = {}
for name in sorted(set(assets)):
    source = SOURCE / name
    if not source.exists():
        raise FileNotFoundError(source)
    dest = ROOT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    asset_hashes[name] = digest(source)

sources["Rebalancing-Connection-Reference.pdf"] = digest(SOURCE / "Rebalancing-Connection-Reference.pdf")
manifest = {"source_hashes": sources, "passages": records, "copied_assets": asset_hashes,
            "main_labels": sorted(labels["main"]), "supp_labels": sorted(labels["supp"]),
            "external_references": {k: sorted(v) for k, v in external.items()}}
manifest_path = ROOT / "relocation-manifest.json"
if manifest_path.exists():
    old = json.loads(manifest_path.read_text())
    for name, sha in old["source_hashes"].items():
        if digest(SOURCE / name) != sha:
            raise ValueError(f"Original changed since extraction: {name}")
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"sections": len(documents), "copied_assets": len(asset_hashes),
                  "originals_unchanged": True, "external_references":
                  {k: len(v) for k, v in external.items()}}, indent=2))
