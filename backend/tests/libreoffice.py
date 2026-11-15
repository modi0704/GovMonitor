"""Recalculate workbooks with LibreOffice headless (MASTERPLAN 9.3), when it is installed.

LibreOffice keeps the cached results of an .xlsx by default; a throwaway profile sets "always
recalculate on load" so the values it saves come from the formulas alone.
"""

import shutil
import subprocess
from pathlib import Path

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")

PROFILE = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse">
<value>0</value></prop></item>
</oor:items>
"""


def recalculate(files: list[Path], workdir: Path) -> list[Path]:
    """Open, recalculate and save each file; returns the recalculated copies."""
    profile = workdir / "lo-profile"
    (profile / "user").mkdir(parents=True, exist_ok=True)
    (profile / "user" / "registrymodifications.xcu").write_text(PROFILE)
    out = workdir / "recalculated"
    out.mkdir(exist_ok=True)
    subprocess.run(  # noqa: S603 — fixed program, test-made file paths
        [
            SOFFICE,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--calc",
            "--convert-to",
            "xlsx:Calc MS Excel 2007 XML",
            "--outdir",
            str(out),
            *map(str, files),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return [out / f.name for f in files]
