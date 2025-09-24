"""여러 Gerber 파일을 하나의 pcb.json으로 병합하는 유틸."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.parsers.gerber_parser import parse_gerber


def compute_bbox(layers):
    xs = []
    ys = []
    for layer in layers:
        bbox = layer.get("bbox")
        if not bbox:
            continue
        xs.extend([bbox["minx"], bbox["maxx"]])
        ys.extend([bbox["miny"], bbox["maxy"]])
    if not xs:
        return {"minx": 0, "miny": 0, "maxx": 0, "maxy": 0}
    return {
        "minx": min(xs),
        "miny": min(ys),
        "maxx": max(xs),
        "maxy": max(ys),
    }


def main():
    parser = argparse.ArgumentParser(description="Gerber 파일을 pcb.json으로 병합")
    parser.add_argument("inputs", nargs="+", help="Gerber 파일 경로")
    parser.add_argument("--output", "-o", default="pcb.json", help="출력 파일 경로")
    args = parser.parse_args()

    layers = []
    for path_str in args.inputs:
        path = Path(path_str)
        meta, segments, flashes = parse_gerber(path)
        layers.append(
            {
                "name": path.name,
                "color": "#93c5fd",
                "segments": segments,
                "flashes": flashes,
                "bbox": meta["bbox"],
            }
        )
    payload = {"units": "IN", "bbox": compute_bbox(layers), "layers": layers}
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(f"저장 완료: {args.output}")


if __name__ == "__main__":
    main()
