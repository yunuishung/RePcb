// 좌표 변환 및 LOD 훅 유틸리티
export function computeFitView(bbox, width, height, padding = 0.1) {
  if (!bbox) {
    return { scale: 1, cx: width / 2, cy: height / 2 };
  }
  const w = bbox.maxx - bbox.minx;
  const h = bbox.maxy - bbox.miny;
  const scaleX = width / (w || 1);
  const scaleY = height / (h || 1);
  const scale = Math.min(scaleX, scaleY) * (1 - padding);
  const cx = (bbox.minx + bbox.maxx) / 2;
  const cy = (bbox.miny + bbox.maxy) / 2;
  return { scale, cx, cy };
}

export function worldToScreen(x, y, state) {
  const { scale, canvasWidth, canvasHeight, viewCx, viewCy } = state;
  const sx = (x - viewCx) * scale + canvasWidth / 2;
  const sy = canvasHeight / 2 - (y - viewCy) * scale;
  return [sx, sy];
}

export function screenToWorld(x, y, state) {
  const { scale, canvasWidth, canvasHeight, viewCx, viewCy } = state;
  const wx = (x - canvasWidth / 2) / scale + viewCx;
  const wy = (canvasHeight / 2 - y) / scale + viewCy;
  return [wx, wy];
}

export function isSegmentVisible(seg, bbox) {
  if (!bbox) return true;
  const minx = Math.min(seg.x0, seg.x1);
  const maxx = Math.max(seg.x0, seg.x1);
  const miny = Math.min(seg.y0, seg.y1);
  const maxy = Math.max(seg.y0, seg.y1);
  return !(maxx < bbox.minx || minx > bbox.maxx || maxy < bbox.miny || miny > bbox.maxy);
}

// TODO: 타일링/LOD/쿼드트리 구현 훅. 현재는 단순 가시성 검사만 수행한다.
