"""Render every page and produce contact sheets plus geometric QA diagnostics."""

from pathlib import Path
import json
import shutil
import subprocess

import pdfplumber
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
pdftoppm = shutil.which("pdftoppm") or str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm")
report = {}
for name in ("Main_Manuscript", "Online_Appendix"):
    output = ROOT / "tmp" / "pdfs" / name
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([pdftoppm, "-r", "80", "-png", str(ROOT / (name + ".pdf")),
                    str(output / "page")], check=True)
    records = []
    with pdfplumber.open(ROOT / (name + ".pdf")) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words(x_tolerance=1)
            outside = [w["text"] for w in words if w["x0"] < -1 or w["x1"] > page.width + 1
                       or w["top"] < -1 or w["bottom"] > page.height + 1]
            text = page.extract_text() or ""
            records.append({"page": number, "words": len(words), "outside": outside,
                            "undefined_marker": "??" in text,
                            "opening": " ".join(text.split()[:30])})
    pages = sorted(output.glob("page-*.png"))[:len(records)]
    for start in range(0, len(pages), 6):
        sheet = Image.new("RGB", (1530, 1400), "#eeeeee")
        draw = ImageDraw.Draw(sheet)
        for offset, path in enumerate(pages[start:start + 6]):
            page = Image.open(path).convert("RGB")
            page.thumbnail((490, 650))
            x, y = (offset % 3) * 510 + 10, (offset // 3) * 700 + 35
            sheet.paste(page, (x, y))
            draw.text((x, y - 22), f"{name}: page {start + offset + 1}", fill="black")
        sheet.save(output / f"sheet-{start // 6 + 1:02d}.png")
    report[name] = {"pages": len(records), "records": records}
    print(name, len(records), "pages; low-text pages:",
          [(r["page"], r["words"]) for r in records if r["words"] < 120])
(ROOT / "tmp" / "pdfs" / "layout-diagnostics.json").write_text(json.dumps(report, indent=2) + "\n")
assert report["Main_Manuscript"]["pages"] <= 30
assert not any(r["outside"] or r["undefined_marker"]
               for doc in report.values() for r in doc["records"])
