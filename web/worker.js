import { Renderer2D } from './renderer2d.js';
import { computeFitView } from './geometry.js';

let renderer = null;
let canvasRef = null;
let hasCanvas = false;
let layers = [];
let visibility = {};
let viewState = { scale: 1, cx: 0, cy: 0 };
let singleColor = false;
let cropPercent = 1.0;
let pendingDraw = false;

self.postMessage({ type: 'ready' });

function ensureRenderer(canvas) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  hasCanvas = true;
  renderer = new Renderer2D(ctx);
  renderer.setLayers(layers);
  renderer.setStyle({ singleColor });
  renderer.setCrop(cropPercent);
  const fit = computeFitView(globalBBox(), canvas.width, canvas.height);
  renderer.updateView({
    scale: fit.scale,
    viewCx: fit.cx,
    viewCy: fit.cy,
    canvasWidth: canvas.width,
    canvasHeight: canvas.height,
  });
}

function globalBBox() {
  if (!layers.length) return null;
  const xs = [];
  const ys = [];
  for (const layer of layers) {
    if (!layer.bbox) continue;
    xs.push(layer.bbox.minx, layer.bbox.maxx);
    ys.push(layer.bbox.miny, layer.bbox.maxy);
  }
  if (!xs.length) return null;
  return {
    minx: Math.min(...xs),
    miny: Math.min(...ys),
    maxx: Math.max(...xs),
    maxy: Math.max(...ys),
  };
}

function scheduleDraw() {
  if (!renderer || pendingDraw) return;
  pendingDraw = true;
  setTimeout(() => {
    pendingDraw = false;
    renderer.draw();
    const ctx = renderer.ctx;
    if (ctx.commit) ctx.commit();
  }, 0);
}

async function handleLoadJson(payload) {
  postProgress('parse', 0.1);
  let data;
  if (payload instanceof ArrayBuffer) {
    const text = new TextDecoder('utf-8').decode(payload);
    data = JSON.parse(text);
  } else if (typeof payload === 'string') {
    data = JSON.parse(payload);
  } else {
    throw new Error('지원하지 않는 payload 타입');
  }
  layers = (data.layers || []).map((layer) => ({
    name: layer.name,
    color: layer.color || '#90cdf4',
    segments: layer.segments || [],
    flashes: layer.flashes || [],
    bbox: layer.bbox || data.bbox,
  }));
  renderer?.setLayers(layers);
  renderer?.setStyle({ singleColor });
  renderer?.setCrop(cropPercent);
  const bbox = globalBBox();
  if (renderer && bbox) {
    const fit = computeFitView(bbox, renderer.ctx.canvas.width, renderer.ctx.canvas.height);
    renderer.updateView({
      scale: fit.scale,
      viewCx: fit.cx,
      viewCy: fit.cy,
    });
  }
  postProgress('index', 0.8);
  self.postMessage({ type: 'loaded', bbox, layers: layers.map((l) => l.name), payload: hasCanvas ? undefined : layers });
  scheduleDraw();
  postProgress('render', 1.0);
}

function parseGerberText(name, text) {
  const lines = text.split(/\r?\n/);
  let units = 'inch';
  let format = [2, 5];
  let absolute = true;
  let currentAperture = null;
  const apertures = new Map();
  const segments = [];
  const flashes = [];
  let cx = 0;
  let cy = 0;
  let curX = null;
  let curY = null;

  const toNumber = (token, axis) => {
    if (!token) return axis === 'x' ? curX : curY;
    token = token.slice(1);
    const sign = token.startsWith('-') ? -1 : 1;
    token = token.replace(/^[-+]/, '');
    const [intDigits, decDigits] = format;
    token = token.padStart(intDigits + decDigits, '0');
    const integer = parseInt(token.slice(0, intDigits) || '0', 10);
    const decimal = parseInt(token.slice(intDigits) || '0', 10);
    let value = sign * (integer + decimal / 10 ** decDigits);
    if (units === 'mm') {
      value /= 25.4;
    }
    if (!absolute) {
      const ref = axis === 'x' ? curX || 0 : curY || 0;
      value = ref + value;
    }
    return value;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('G04')) continue;
    if (line.startsWith('%')) {
      if (line.includes('FS')) {
        const match = line.match(/FS([LA])([AI])X(\d)(\d)Y(\d)(\d)/);
        if (match) {
          absolute = match[2] === 'A';
          format = [parseInt(match[3], 10), parseInt(match[4], 10)];
        }
      } else if (line.includes('MO')) {
        units = line.includes('MM') ? 'mm' : 'inch';
      } else if (line.includes('AD')) {
        const match = line.match(/ADD?(\d+)([A-Z])?,?(.*)/);
        if (match) {
          const code = match[1];
          const shape = match[2] || 'C';
          const params = match[3]
            .replace(/[\*%]/g, '')
            .split('X')
            .filter(Boolean)
            .map((v) => parseFloat(v));
          apertures.set(code, { shape, params });
        }
      }
      continue;
    }
    const parts = line.split('*');
    for (const part of parts) {
      if (!part) continue;
      if (/^D\d+$/.test(part)) {
        currentAperture = part.slice(1);
        continue;
      }
      const match = part.match(/(X[-+]?\d+)?(Y[-+]?\d+)?(D0[123])?/);
      if (!match) continue;
      const [, xTok, yTok, opTok] = match;
      const x = toNumber(xTok, 'x');
      const y = toNumber(yTok, 'y');
      if (x === null || y === null) continue;
      const op = opTok || 'D01';
      if (op === 'D02') {
        curX = x;
        curY = y;
      } else if (op === 'D01') {
        if (curX !== null && curY !== null) {
          segments.push({ x0: curX, y0: curY, x1: x, y1: y, width: null });
        }
        curX = x;
        curY = y;
      } else if (op === 'D03') {
        const aperture = apertures.get(currentAperture) || { params: [] };
        const params = aperture.params || [];
        flashes.push({
          x,
          y,
          shape: aperture.shape || 'C',
          params: { diameter: params[0] ? params[0] / (units === 'mm' ? 25.4 : 1) : 0.01 },
        });
        curX = x;
        curY = y;
      }
    }
  }
  const bbox = computeBBox(segments, flashes);
  return { name, color: '#c084fc', segments, flashes, bbox };
}

function computeBBox(segments, flashes) {
  const xs = [];
  const ys = [];
  segments.forEach((seg) => {
    xs.push(seg.x0, seg.x1);
    ys.push(seg.y0, seg.y1);
  });
  flashes.forEach((fl) => {
    xs.push(fl.x);
    ys.push(fl.y);
  });
  if (!xs.length) {
    return { minx: 0, miny: 0, maxx: 0, maxy: 0 };
  }
  return {
    minx: Math.min(...xs),
    miny: Math.min(...ys),
    maxx: Math.max(...xs),
    maxy: Math.max(...ys),
  };
}

async function handleLoadGerbers(files) {
  postProgress('parse', 0.05);
  const decoder = new TextDecoder('utf-8');
  layers = [];
  for (const { name, buf } of files) {
    const text = decoder.decode(buf);
    const layer = parseGerberText(name, text);
    layers.push(layer);
  }
  renderer?.setLayers(layers);
  renderer?.setStyle({ singleColor });
  renderer?.setCrop(cropPercent);
  const bbox = globalBBox();
  if (renderer && bbox) {
    const fit = computeFitView(bbox, renderer.ctx.canvas.width, renderer.ctx.canvas.height);
    renderer.updateView({
      scale: fit.scale,
      viewCx: fit.cx,
      viewCy: fit.cy,
    });
  }
  self.postMessage({ type: 'loaded', bbox, layers: layers.map((l) => l.name), payload: hasCanvas ? undefined : layers });
  scheduleDraw();
  postProgress('render', 1.0);
}

function postProgress(phase, value) {
  self.postMessage({ type: 'progress', phase, value });
}

self.onmessage = async (event) => {
  const msg = event.data;
  switch (msg.type) {
    case 'init': {
      canvasRef = msg.canvas || canvasRef;
      if (canvasRef) {
        ensureRenderer(canvasRef);
      }
      singleColor = msg.singleColor ?? singleColor;
      if (renderer) {
        renderer.setStyle({ singleColor });
      }
      scheduleDraw();
      break;
    }
    case 'load-json': {
      await handleLoadJson(msg.payload);
      break;
    }
    case 'load-gerbers': {
      await handleLoadGerbers(msg.files);
      break;
    }
    case 'set-view': {
      if (renderer) {
        renderer.updateView({
          viewCx: msg.cx,
          viewCy: msg.cy,
          scale: msg.scale,
        });
        scheduleDraw();
      }
      break;
    }
    case 'set-layers': {
      visibility = msg.visibility;
      renderer?.setVisibility(visibility);
      scheduleDraw();
      break;
    }
    case 'set-style': {
      singleColor = msg.singleColor;
      renderer?.setStyle({ singleColor });
      scheduleDraw();
      break;
    }
    case 'crop-percent': {
      cropPercent = msg.v;
      renderer?.setCrop(cropPercent);
      scheduleDraw();
      break;
    }
    case 'draw': {
      scheduleDraw();
      break;
    }
    default:
      console.warn('알 수 없는 메시지', msg);
  }
};
