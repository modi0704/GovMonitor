"""Excel export (MASTERPLAN 9). Filled in by P9.2–P9.3."""

import io

import xlsxwriter


def build(sc) -> tuple[bytes, dict]:
    out = io.BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    wb.add_worksheet("SUMMARY").write("A1", "Performance summary")
    wb.close()
    return out.getvalue(), {"offices": len(sc.offices), "sheets": 1}
