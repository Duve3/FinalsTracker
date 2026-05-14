from typing import Dict, Tuple, List
from ..log_config import get_logger

log = get_logger(__name__)

RegionMap = Dict[str, Tuple[float, float, float, float]]
RegionGroup = Dict[str, RegionMap]

BASE_WIDTH = 2560
BASE_HEIGHT = 1440


def scale_region(region: Tuple[float, float, float, float], win_w: int, win_h: int) -> Tuple[int, int, int, int]:
    l, t, r, b = region
    abs_coords = (
        int(l * win_w),
        int(t * win_h),
        int(r * win_w),
        int(b * win_h),
    )
    log.debug("Scaled region (%.2f,%.2f %.2f,%.2f) -> (%d,%d,%d,%d) at %dx%d",
              l, t, r, b, *abs_coords, win_w, win_h)
    return abs_coords


HUD_REGIONS: RegionMap = {
    "team_score":    (0.023, 0.031, 0.127, 0.235),
    "round_timer":   (0.476, 0.045, 0.524, 0.080),
}

SCOREBOARD_REGIONS: RegionMap = {
    "header":      (0.02, 0.150, 0.68, 0.180),
    "player_1":    (0.14, 0.195, 0.68, 0.231),
    "player_2":    (0.14, 0.231, 0.68, 0.275),
    "player_3":    (0.14, 0.275, 0.68, 0.313),
    "player_4":    (0.14, 0.395, 0.68, 0.435),
    "player_5":    (0.14, 0.435, 0.68, 0.475),
    "player_6":    (0.14, 0.475, 0.68, 0.515),
    "player_7":    (0.14, 0.530, 0.68, 0.570),
    "player_8":    (0.14, 0.570, 0.68, 0.610),
    "player_9":    (0.14, 0.610, 0.68, 0.650),
}

# sub-regions within each scoreboard row for individual cell OCR
# OFFSET because im genuinely too lazy to do subtraction
_OFFSET = 0.14
SCOREBOARD_COLUMNS: List[Tuple[str, float, float]] = [
    ("name",            0.140, 0.395),
    ("kills",           0.395, 0.415),
    ("assists",         0.415, 0.435),
    ("deaths",          0.435, 0.460),
    ("revives",         0.460, 0.485),
    ("combat_score",    0.510, 0.560),
    ("support_score",   0.570, 0.620),
    ("objective_score", 0.635, 0.670)
]

for v in SCOREBOARD_COLUMNS:
    v[1] -= _OFFSET
    v[2] -= _OFFSET

# inaccurate
SUMMARY_REGIONS: RegionMap = {
    "match_result": (0.35, 0.10, 0.65, 0.16),
    "final_score":  (0.35, 0.18, 0.65, 0.24),
}


def get_player_cell_region(row_region: Tuple[float, float, float, float],
                           col_name: str) -> Tuple[float, float, float, float]:
    """Get a sub-region within a scoreboard row for a specific column."""
    _, row_top, _, row_bottom = row_region
    for name, col_left, col_right in SCOREBOARD_COLUMNS:
        if name == col_name:
            return col_left, row_top, col_right, row_bottom
    return row_region
