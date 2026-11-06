"""Build both PDFs, resolving their cross-document references in both directions."""

from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
latexmk = shutil.which("latexmk") or "/Library/TeX/texbin/latexmk"
env = dict(os.environ)
env["PATH"] = str(Path(latexmk).parent) + os.pathsep + env.get("PATH", "")
for key in ("TEXINPUTS", "BSTINPUTS"):
    env[key] = str(ROOT / "vendor") + os.pathsep + env.get(key, "")

# The first passes create both auxiliary files. The second pair resolves any
# changed page/equation numbers without touching the parent reference version.
# Force each pass: on a clean checkout latexmk may not yet know that the other
# document's previously absent .aux is an external dependency of this one.
for name in ("Online_Appendix", "Main_Manuscript", "Online_Appendix", "Main_Manuscript"):
    subprocess.run([latexmk, "-g", "-pdf", "-silent", "-interaction=nonstopmode",
                    "-halt-on-error", name + ".tex"], cwd=ROOT, env=env, check=True)
for name in ("Main_Manuscript", "Online_Appendix"):
    log = (ROOT / (name + ".log")).read_text(errors="replace")
    for marker in ("There were undefined references", "multiply defined", "Overfull"):
        if marker in log:
            raise RuntimeError(f"Check {name}.log: {marker}")
    print(next(line for line in log.splitlines() if line.startswith("Output written")))
