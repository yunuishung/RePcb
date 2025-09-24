import { isSegmentVisible, worldToScreen } from './geometry.js';

export class Renderer2D {
  constructor(ctx) {
    this.ctx = ctx;
    this.layers = [];
    this.visibility = new Map();
    this.singleColor = false;
    this.cropPercent = 1.0;
    this.viewState = {
      scale: 1,
      viewCx: 0,
      viewCy: 0,
      canvasWidth: ctx.canvas.width,
      canvasHeight: ctx.canvas.height,
    };
  }

  setLayers(layers) {
    this.layers = layers;
    for (const layer of layers) {
      if (!this.visibility.has(layer.name)) {
        this.visibility.set(layer.name, true);
      }
    }
  }

  setVisibility(visibility) {
    Object.entries(visibility).forEach(([name, value]) => {
      this.visibility.set(name, value);
    });
  }

  setStyle({ singleColor }) {
    this.singleColor = singleColor;
  }

  setCrop(percent) {
    this.cropPercent = percent;
  }

  updateView(viewState) {
    this.viewState = { ...this.viewState, ...viewState };
  }

  draw() {
    const ctx = this.ctx;
    const { canvasWidth, canvasHeight } = this.viewState;
    ctx.save();
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    ctx.fillStyle = '#0b1220';
    ctx.fillRect(0, 0, canvasWidth, canvasHeight);
    for (const layer of this.layers) {
      if (!this.visibility.get(layer.name)) continue;
      this._drawLayer(layer);
    }
    ctx.restore();
  }

  _drawLayer(layer) {
    const ctx = this.ctx;
    const state = this.viewState;
    const color = this.singleColor ? '#7dd3fc' : layer.color || '#93c5fd';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    const bbox = this._computeCropBBox(layer);
    ctx.beginPath();
    for (const seg of layer.segments || []) {
      if (!isSegmentVisible(seg, bbox)) continue;
      const [x0, y0] = worldToScreen(seg.x0, seg.y0, state);
      const [x1, y1] = worldToScreen(seg.x1, seg.y1, state);
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
    }
    ctx.stroke();
    for (const flash of layer.flashes || []) {
      const [sx, sy] = worldToScreen(flash.x, flash.y, state);
      ctx.beginPath();
      ctx.fillStyle = color;
      const diameter = flash.params?.diameter || 0.01;
      const radius = Math.max(1, (diameter * state.scale) / 2);
      ctx.arc(sx, sy, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _computeCropBBox(layer) {
    if (!layer.bbox || this.cropPercent >= 1.0) {
      return layer.bbox;
    }
    const { minx, miny, maxx, maxy } = layer.bbox;
    const width = maxx - minx;
    const height = maxy - miny;
    const cx = (minx + maxx) / 2;
    const cy = (miny + maxy) / 2;
    const factor = this.cropPercent;
    return {
      minx: cx - (width * factor) / 2,
      maxx: cx + (width * factor) / 2,
      miny: cy - (height * factor) / 2,
      maxy: cy + (height * factor) / 2,
    };
  }
}
