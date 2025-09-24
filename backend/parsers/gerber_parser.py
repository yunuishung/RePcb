"""RS-274X Gerber 파서 (최소 구현)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

INCH_PER_MM = 1 / 25.4


@dataclass
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    width: Optional[float]


@dataclass
class Flash:
    x: float
    y: float
    shape: str
    params: Dict[str, float] = field(default_factory=dict)


class RS274XParser:
    """간단한 RS-274X 파서."""

    def __init__(self) -> None:
        self.units = "inch"
        self.format = (2, 5)
        self.zero_omission = "leading"
        self.absolute = True
        self.current_x = None
        self.current_y = None
        self.current_aperture = None
        self.apertures: Dict[str, Dict[str, float]] = {}
        self.segments: List[Segment] = []
        self.flashes: List[Flash] = []
        self.last_point: Tuple[Optional[float], Optional[float]] = (None, None)

    def parse(self, text: str) -> None:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("G04"):
                continue
            if line.startswith("%"):
                self._parse_attribute(line)
                continue
            if line.endswith("*"):
                for part in line.split("*"):
                    part = part.strip()
                    if part:
                        self._parse_command(part)
            else:
                self._parse_command(line)

    # --- Attribute parsing -------------------------------------------------
    def _parse_attribute(self, line: str) -> None:
        line = line.strip("%")
        if line.startswith("FS"):
            # 예: FSLAX24Y24
            match = re.match(r"FS([LA])([AI])X(\d)(\d)Y(\d)(\d)", line)
            if match:
                self.zero_omission = "leading" if match.group(1) == "L" else "trailing"
                self.absolute = match.group(2) == "A"
                self.format = (int(match.group(3)), int(match.group(4)))
        elif line.startswith("MO"):
            if "MM" in line.upper():
                self.units = "mm"
            else:
                self.units = "inch"
        elif line.startswith("AD"):
            # %ADD10C,0.010*%
            match = re.match(r"AD(D?\d+)([A-Z])?(.*)", line)
            if match:
                code = match.group(1)
                shape = match.group(2) or "C"
                params = match.group(3).strip(",")
                parsed_params = [float(p) for p in params.split("X") if p]
                info: Dict[str, float] = {"shape": shape}
                if parsed_params:
                    info["diameter"] = parsed_params[0]
                    if len(parsed_params) > 1:
                        info["height"] = parsed_params[1]
                self.apertures[code] = info
        # AM(아퍼처 매크로)는 단순화하여 무시한다.

    # --- Command parsing ---------------------------------------------------
    def _parse_command(self, cmd: str) -> None:
        if cmd.startswith("G"):
            # G01/G02 등은 현재 단순화하여 무시한다.
            return
        if cmd.startswith("M02"):
            return
        if cmd.startswith("D") and len(cmd) <= 4:
            self.current_aperture = cmd[1:]
            return
        coord_match = re.match(r"(X[-+]?\d+)?(Y[-+]?\d+)?(I[-+]?\d+)?(J[-+]?\d+)?(D0[123])?", cmd)
        if coord_match:
            x_token, y_token, _, _, op_token = coord_match.groups()
            x = self._parse_coord(x_token, axis="x") if x_token else self.current_x
            y = self._parse_coord(y_token, axis="y") if y_token else self.current_y
            if x is None or y is None:
                return
            op = op_token or "D01"
            if op == "D02":
                self.current_x, self.current_y = x, y
                self.last_point = (x, y)
            elif op == "D01":
                if self.current_x is not None and self.current_y is not None:
                    self._add_segment(self.current_x, self.current_y, x, y)
                self.current_x, self.current_y = x, y
            elif op == "D03":
                self._add_flash(x, y)
                self.current_x, self.current_y = x, y

    def _parse_coord(self, token: str, *, axis: str) -> Optional[float]:
        token = token[1:]  # drop axis letter
        sign = -1 if token.startswith("-") else 1
        token = token.lstrip("+-")
        int_digits, dec_digits = self.format
        token = token.zfill(int_digits + dec_digits)
        integer = int(token[:int_digits]) if token[:int_digits] else 0
        decimal = int(token[int_digits:]) if dec_digits else 0
        value = sign * (integer + decimal / (10 ** dec_digits))
        if self.units == "mm":
            value *= INCH_PER_MM
        if not self.absolute:
            ref = self.current_x if axis == "x" else self.current_y
            if ref is None:
                ref = 0.0
            value = ref + value
        return value

    def _add_segment(self, x0: float, y0: float, x1: float, y1: float) -> None:
        width = None
        if self.current_aperture and self.current_aperture in self.apertures:
            info = self.apertures[self.current_aperture]
            width = info.get("diameter")
            if width and self.units == "mm":
                width *= INCH_PER_MM
        self.segments.append(Segment(x0, y0, x1, y1, width))

    def _add_flash(self, x: float, y: float) -> None:
        shape = "C"
        params: Dict[str, float] = {}
        if self.current_aperture and self.current_aperture in self.apertures:
            info = self.apertures[self.current_aperture]
            shape = str(info.get("shape", "C"))
            if "diameter" in info:
                d = info["diameter"]
                if self.units == "mm":
                    d *= INCH_PER_MM
                params["diameter"] = d
            if "height" in info:
                h = info["height"]
                if self.units == "mm":
                    h *= INCH_PER_MM
                params["height"] = h
        self.flashes.append(Flash(x, y, shape, params))


def parse_gerber(path: Path) -> Tuple[Dict, List[Dict], List[Dict]]:
    parser = RS274XParser()
    text = path.read_text(errors="ignore")
    parser.parse(text)
    # bbox 계산
    xs = []
    ys = []
    for seg in parser.segments:
        xs.extend([seg.x0, seg.x1])
        ys.extend([seg.y0, seg.y1])
    for fl in parser.flashes:
        xs.append(fl.x)
        ys.append(fl.y)
    if xs and ys:
        bbox = {
            "minx": min(xs),
            "miny": min(ys),
            "maxx": max(xs),
            "maxy": max(ys),
        }
    else:
        bbox = {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0}
    segments = [seg.__dict__ for seg in parser.segments]
    flashes = [fl.__dict__ for fl in parser.flashes]
    meta = {"units": "IN", "bbox": bbox}
    return meta, segments, flashes
