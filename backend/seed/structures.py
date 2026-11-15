"""Demo structures (sample data only). Nested dicts: code -> (name, {children}).

Sample Ministry: three levels (Ministry → Service → Division/Center), with provincial field centers
and two office groups. Sample Bureau: five levels. Nothing in backend/apps depends on these names.
"""

MINISTRY_LEVELS = ["Ministry", "Service", "Division"]
MINISTRY_TREE = {
    "ODS": (
        "Office of the Director for Services",
        {
            "PME": ("Planning, Monitoring and Evaluation Division", {}),
            "HRM": ("Human Resource Management Division", {}),
        },
    ),
    "RDS": (
        "Research and Development Services",
        {
            "RDI": ("Research, Development and Innovation Division", {}),
            "AST": ("Applied Science and Technology Division", {}),
            "ILD": ("Industry and Livelihood Development Division", {}),
        },
    ),
    "FAS": (
        "Finance and Administrative Services",
        {
            "GAS": ("General Administrative Services Division", {}),
        },
    ),
    "FOS": (
        "Field Operations Services",
        {
            "PC-BAS": ("Provincial Center — Basilan", {}),
            "PC-MAG": ("Provincial Center — Maguindanao", {}),
            "PC-SGA": ("Provincial Center — Special Geographic Area", {}),
            "PC-LDS": ("Provincial Center — Lanao del Sur", {}),
            "PC-COT": ("Provincial Center — Cotabato City", {}),
            "PC-TAW": ("Provincial Center — Tawi-Tawi", {}),
            "PC-SUL": ("Provincial Center — Sulu", {}),
        },
    ),
}
MINISTRY_GROUPS = {
    "Mainland centers": ["PC-MAG", "PC-SGA", "PC-LDS", "PC-COT"],
    "Island centers": ["PC-BAS", "PC-TAW", "PC-SUL"],
}

BUREAU_LEVELS = ["Bureau", "Region", "Province", "District", "Unit"]
BUREAU_TREE = {
    "R1": (
        "Region One",
        {
            "R1-P1": (
                "Province Alpha",
                {
                    "R1-P1-D1": (
                        "District North",
                        {
                            "R1-P1-D1-U1": ("Unit 1", {}),
                            "R1-P1-D1-U2": ("Unit 2", {}),
                        },
                    ),
                    "R1-P1-D2": ("District South", {"R1-P1-D2-U1": ("Unit 3", {})}),
                },
            ),
        },
    ),
    "R2": (
        "Region Two",
        {
            "R2-P1": (
                "Province Beta",
                {
                    "R2-P1-D1": ("District East", {"R2-P1-D1-U1": ("Unit 4", {})}),
                },
            ),
        },
    ),
}
