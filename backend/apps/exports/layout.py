"""Office sheet layout of the Excel export (MASTERPLAN 9.1), in one place.

Every column letter, fixed row and header text the writer and the importer use comes from here,
so a paid custom template can override them without touching the writer (P9.2). Rows are 1-based
as in Excel.
"""

from dataclasses import dataclass, field

MONTH_ABBR = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTH_FULL = (
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
)  # fmt: skip


def col_letters(first: str, count: int) -> tuple[str, ...]:
    from xlsxwriter.utility import xl_col_to_name

    start = col_index(first)
    return tuple(xl_col_to_name(start + i) for i in range(count))


def col_index(letters: str) -> int:
    """0-based column index of ``letters`` (A = 0)."""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


@dataclass(frozen=True)
class OfficeSheetLayout:
    # Title block
    fiscal_year_cell: str = "A1"
    agency_cell: str = "A2"
    office_cell: str = "A3"
    as_of_cell: str = "A4"
    header_rows: tuple = (5, 6, 7)
    first_data_row: int = 8
    office_caps_col: str = "A"

    # Outline rows: kind -> column of its text
    outline_cols: dict = field(
        default_factory=lambda: {
            "outcome": "B",
            "outcome_indicator": "C",
            "output": "D",
            "output_indicator": "E",
            "program": "F",
            "project": "G",
            "activity": "H",
        }
    )
    outline_headers: dict = field(
        default_factory=lambda: {
            "B": "OUTCOME STATEMENT",
            "C": "OUTCOME INDICATORS",
            "D": "OUTPUTS",
            "E": "OUTPUT INDICATORS",
            "F": "PROGRAMS",
            "G": "PROJECTS",
            "H": "ACTIVITIES",
        }
    )

    # Activity columns
    target_col: str = "I"
    unit_col: str = "J"
    unit_cost_col: str = "K"
    total_cost_col: str = "L"
    weight_col: str = "M"
    remarks_col: str = "N"
    plan_month_first: str = "O"  # O:Z quantities
    weighted_first: str = "AD"  # AD:AO weighted progress
    empty_cols: tuple = ("AA", "AB", "AC")  # stay empty, as in the source

    targets_header: str = "TARGETS"
    cost_header: str = "PROJECTED COST"
    schedule_header: str = "INDICATIVE SCHEDULE OF IMPLEMENTATION (MONTHLY)"
    qty_header: str = "QTY"
    unit_header: str = "UNIT"
    unit_cost_header: str = "UNIT COST"
    total_cost_header: str = "TOTAL COST"
    weight_header: str = "Wtd%"
    remarks_header: str = "REMARKS"
    plan_marker: str = "PLAN"
    actual_marker: str = "ACTUAL"

    # Total block (offsets from the total row t)
    total_label: str = "TOTAL COST"
    total_label_cols: tuple = ("B", "H")
    label_col: str = "U"
    sublabel_col: str = "W"
    value_col: str = "W"
    plan_label: str = "Plan"
    actual_label: str = "Actual"
    variance_label: str = "Variance"
    periodic_label: str = "Periodic"
    cum_plan_label: str = "Commulative(Plan)"  # spelling kept from the source
    cum_actual_label: str = "Commulative(Actual)"
    cum_variance_label: str = "Commulative(Variance)"
    funds_total_label: str = "FUNDS TOTAL"
    funds_used_label: str = "FUNDS USED"
    funds_remaining_label: str = "FUNDS REMAINING"
    status_label: str = "STATUS"

    # Indicator block (header at t + 13, rows from t + 14)
    indicator_header_offset: int = 13
    indicator_header: str = "OUTPUT INDICATORS"
    indicator_code_col: str = "H"
    indicator_name_col: str = "I"
    indicator_total_col: str = "L"
    indicator_total_header: str = "TOTAL"
    indicator_weight_col: str = "N"
    indicator_weight_header: str = "WTD%"

    recurring_comment: str = "Recurring measure: value computed by the system"
    no_target_comment: str = "No annual target: this activity is not scored"
    profile_comment: str = "Value computed by the system under this year's scoring profile"

    @property
    def month_cols(self) -> tuple[str, ...]:
        return col_letters(self.plan_month_first, 12)

    @property
    def weighted_cols(self) -> tuple[str, ...]:
        return col_letters(self.weighted_first, 12)

    @property
    def last_col(self) -> str:
        return self.weighted_cols[-1]

    def quarter_cols(self, first: str) -> tuple[str, ...]:
        cols = col_letters(first, 12)
        return cols[0], cols[3], cols[6], cols[9]


DEFAULT = OfficeSheetLayout()
