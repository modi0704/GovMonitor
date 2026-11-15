"""PowerPoint export layout (MASTERPLAN 10, P10.1): slide geometry, sizes and fixed texts in one
place. Colours, report title, footer text and logo come from the export template (P10.2); the
defaults here are the system template's."""

from dataclasses import dataclass, field

from pptx.util import Inches, Pt

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)  # 16:9
FONT = "Arial"
MAX_TABLE_ROWS = 12  # rows per ranking / indicator slide before "continued"

SLIDE_GROUPS = ("overall", "offices", "rankings", "indicators")

DEFAULT_SETTINGS = {
    "report_title": "Performance Monitoring Report",
    "primary_color": "1F4E79",  # header bars, plan series
    "accent_color": "F2C14E",  # chips on the header bar
    "actual_color": "2E8B57",  # actual series
    "footer_text": "",
    "currency_symbol": "₱",
}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    def emu(self):
        return Inches(self.x), Inches(self.y), Inches(self.w), Inches(self.h)

    @property
    def width_pt(self) -> float:
        return self.w * 72


@dataclass(frozen=True)
class DeckLayout:
    margin: float = 0.4
    header: Box = Box(0.4, 0.3, 12.53, 0.62)
    header_title_size: Pt = Pt(20)
    header_chip_w: float = 2.2
    # Office dashboard slide
    tiles: Box = Box(0.4, 1.15, 2.5, 3.9)  # PLAN / ACTUAL / VARIANCE / STATUS stacked
    tile_label_size: Pt = Pt(11)
    tile_value_size: Pt = Pt(24)
    line_chart: Box = Box(3.1, 1.15, 6.7, 5.55)
    line_chart_with_children: Box = Box(3.1, 1.15, 6.7, 3.15)
    children_chart: Box = Box(3.1, 4.4, 6.7, 2.3)
    doughnut: Box = Box(10.0, 1.15, 2.93, 2.9)
    funds_text: Box = Box(10.0, 4.1, 2.93, 1.2)
    indicator_tile: Box = Box(10.0, 5.4, 2.93, 1.3)
    office_path: Box = Box(0.4, 5.2, 2.5, 1.5)
    # Tables
    table: Box = Box(0.4, 1.2, 12.53, 5.5)
    table_font: Pt = Pt(12)
    table_header_font: Pt = Pt(12)
    # Footer
    footer: Box = Box(0.4, 7.0, 12.53, 0.35)
    footer_size: Pt = Pt(9)
    # Title slide
    logo: Box = Box(5.92, 0.8, 1.5, 1.5)
    title_lines: tuple = field(default=(2.6, 3.4, 4.6, 5.3))  # agency, report title, as of, label

    status_colors: dict = field(
        default_factory=lambda: {
            "ahead": ("E3F4EA", "1B6E3C"),
            "on_time": ("E3EEFA", "155E9C"),
            "delayed": ("FBE7E3", "A8321F"),
        }
    )
    tile_colors: dict = field(
        default_factory=lambda: {
            "plan": ("E3EEFA", "1F4E79"),
            "actual": ("E3F4EA", "1B6E3C"),
            "variance": ("FFF4D6", "8A5A00"),
        }
    )


DEFAULT = DeckLayout()
