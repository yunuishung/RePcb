import { Renderer2D } from './renderer2d.js';
import { computeFitView, screenToWorld } from './geometry.js';

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const statusBox = document.getElementById('upload-status');
const progressBox = document.getElementById('progress');
const layerContainer = document.getElementById('layers');
const fitButton = document.getElementById('fitButton');
const singleColorToggle = document.getElementById('singleColorToggle');
const previewToggle = document.getElementById('previewToggle');
const zoomSlider = document.getElementById('zoomSlider');
const canvas = document.getElementById('viewer');

const worker = new Worker('./worker.js', { type: 'module' });
let mainRenderer = null;
let useOffscreen = false;
let currentProjectId = null;
let currentLayers = [];
let layerVisibility = {};
let currentBBox = null;
let viewState = {
  scale: 1,
  viewCx: 0,
  viewCy: 0,
  canvasWidth: canvas.width,
  canvasHeight: canvas.height,
};
let isPanning = false;
let lastPointer = { x: 0, y: 0 };

function logStatus(message) {
  const line = document.createElement('div');
  line.textContent = message;
  statusBox.prepend(line);
}

function setProgress(message) {
  progressBox.textContent = message;
}

async function ensureProject() {
  if (currentProjectId) return currentProjectId;
  const res = await fetch('/projects/');
  if (res.ok) {
    const data = await res.json();
    if (data.length) {
      currentProjectId = data[0].id;
      logStatus(`프로젝트 사용: ${data[0].name}`);
      return currentProjectId;
    }
  }
  const createRes = await fetch('/projects/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: `Project-${Date.now()}` }),
  });
  const project = await createRes.json();
  currentProjectId = project.id;
  logStatus(`프로젝트 생성: ${project.name}`);
  return currentProjectId;
}

function setupWorker() {
  if (canvas.transferControlToOffscreen) {
    const offscreen = canvas.transferControlToOffscreen();
    useOffscreen = true;
    worker.postMessage({ type: 'init', canvas: offscreen, singleColor: singleColorToggle.checked }, [offscreen]);
  } else {
    useOffscreen = false;
    const ctx = canvas.getContext('2d');
    mainRenderer = new Renderer2D(ctx);
    mainRenderer.updateView(viewState);
    worker.postMessage({ type: 'init', singleColor: singleColorToggle.checked });
  }
}

setupWorker();

function refreshLayersUI(layers) {
  layerContainer.innerHTML = '';
  layerVisibility = {};
  layers.forEach((layer) => {
    layerVisibility[layer.name] = true;
    const div = document.createElement('label');
    div.className = 'layer-item';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = true;
    checkbox.addEventListener('change', () => {
      layerVisibility[layer.name] = checkbox.checked;
      if (useOffscreen) {
        worker.postMessage({ type: 'set-layers', visibility: layerVisibility });
      } else if (mainRenderer) {
        mainRenderer.setVisibility(layerVisibility);
        mainRenderer.draw();
      }
    });
    const span = document.createElement('span');
    span.textContent = layer.name;
    div.appendChild(checkbox);
    div.appendChild(span);
    layerContainer.appendChild(div);
  });
  if (useOffscreen) {
    worker.postMessage({ type: 'set-layers', visibility: layerVisibility });
  } else if (mainRenderer) {
    mainRenderer.setVisibility(layerVisibility);
  }
}

async function uploadToServer(files) {
  const projectId = await ensureProject();
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file, file.name));
  const res = await fetch(`/uploads/?project_id=${projectId}`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`업로드 실패: ${msg}`);
  }
  const uploads = await res.json();
  logStatus(`${uploads.length}개 파일 업로드 완료`);
  const uploadIds = uploads.map((u) => u.id);
  await runPipeline(projectId, uploadIds);
  await loadProjectLayers(projectId);
}

async function runPipeline(projectId, uploadIds) {
  setProgress('파이프라인 실행 중...');
  const res = await fetch('/imports/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, upload_ids: uploadIds }),
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`임포트 실패: ${msg}`);
  }
  const result = await res.json();
  logStatus(`임포트 결과: ${JSON.stringify(result)}`);
}

async function loadProjectLayers(projectId) {
  const res = await fetch(`/query/gerber/${projectId}`);
  if (!res.ok) {
    throw new Error('레이어 목록 조회 실패');
  }
  const layerList = await res.json();
  const detailed = await Promise.all(
    layerList.map(async (layer) => {
      const detailRes = await fetch(`/query/gerber/layer/${layer.id}`);
      const detail = await detailRes.json();
      return {
        name: layer.name,
        color: layer.color,
        bbox: detail.data?.bbox || layer.bbox,
        segments: detail.data?.segments || [],
        flashes: detail.data?.flashes || [],
      };
    })
  );
  const bbox = computeGlobalBBox(detailed);
  const payload = {
    units: 'IN',
    bbox,
    layers: detailed,
  };
  currentLayers = detailed;
  currentBBox = bbox;
  refreshLayersUI(detailed);
  if (useOffscreen) {
    worker.postMessage({ type: 'load-json', payload: JSON.stringify(payload) });
  } else if (mainRenderer) {
    mainRenderer.setLayers(detailed);
    mainRenderer.setStyle({ singleColor: singleColorToggle.checked });
    mainRenderer.setCrop(previewToggle.checked ? 0.1 : 1.0);
    fitView();
    mainRenderer.draw();
  }
}

function computeGlobalBBox(layers) {
  const xs = [];
  const ys = [];
  layers.forEach((layer) => {
    if (!layer.bbox) return;
    xs.push(layer.bbox.minx, layer.bbox.maxx);
    ys.push(layer.bbox.miny, layer.bbox.maxy);
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

async function handleLocalFiles(files) {
  const jsonFile = files.find((file) => file.name.toLowerCase().endsWith('.json'));
  if (jsonFile) {
    const buf = await jsonFile.arrayBuffer();
    worker.postMessage({ type: 'load-json', payload: buf }, [buf]);
    return;
  }
  const gerberBuffers = await Promise.all(
    files.map(async (file) => ({ name: file.name, buf: await file.arrayBuffer() }))
  );
  const transfer = gerberBuffers.map((item) => item.buf);
  worker.postMessage({ type: 'load-gerbers', files: gerberBuffers }, transfer);
}

function shouldHandleLocally(files) {
  return files.every((file) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    return ['json', 'gbr', 'ger', 'pho', 'gtl', 'gbl', 'gto', 'gbo'].includes(ext || '');
  });
}

async function handleFiles(files) {
  try {
    setProgress('파일 처리 중...');
    if (files.length && shouldHandleLocally(files)) {
      logStatus('로컬 Worker 파싱 시작');
      await handleLocalFiles(files);
    } else {
      await uploadToServer(files);
    }
  } catch (err) {
    console.error(err);
    logStatus(`오류: ${err.message}`);
  } finally {
    setProgress('');
  }
}

function fitView() {
  if (!currentBBox) return;
  const fit = computeFitView(currentBBox, canvas.width, canvas.height);
  viewState = {
    ...viewState,
    scale: fit.scale,
    viewCx: fit.cx,
    viewCy: fit.cy,
  };
  zoomSlider.value = viewState.scale.toFixed(2);
  if (useOffscreen) {
    worker.postMessage({ type: 'set-view', cx: viewState.viewCx, cy: viewState.viewCy, scale: viewState.scale });
    worker.postMessage({ type: 'draw' });
  } else if (mainRenderer) {
    mainRenderer.updateView(viewState);
    mainRenderer.draw();
  }
}

function applyZoom(factor, centerX, centerY) {
  const prevScale = viewState.scale;
  const sliderMax = parseFloat(zoomSlider.max);
  const sliderMin = parseFloat(zoomSlider.min);
  const newScale = Math.min(sliderMax, Math.max(sliderMin, prevScale * factor));
  const [worldX, worldY] = screenToWorld(centerX, centerY, viewState);
  viewState.scale = newScale;
  viewState.viewCx = worldX - (centerX - canvas.width / 2) / newScale;
  viewState.viewCy = worldY + (centerY - canvas.height / 2) / newScale;
  zoomSlider.value = newScale.toFixed(2);
  if (useOffscreen) {
    worker.postMessage({ type: 'set-view', cx: viewState.viewCx, cy: viewState.viewCy, scale: viewState.scale });
    worker.postMessage({ type: 'draw' });
  } else if (mainRenderer) {
    mainRenderer.updateView(viewState);
    mainRenderer.draw();
  }
}

function setupInteractions() {
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  });
  fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files || []);
    handleFiles(files);
  });
  fitButton.addEventListener('click', () => fitView());
  singleColorToggle.addEventListener('change', () => {
    if (useOffscreen) {
      worker.postMessage({ type: 'set-style', singleColor: singleColorToggle.checked });
      worker.postMessage({ type: 'draw' });
    } else if (mainRenderer) {
      mainRenderer.setStyle({ singleColor: singleColorToggle.checked });
      mainRenderer.draw();
    }
  });
  previewToggle.addEventListener('change', () => {
    const percent = previewToggle.checked ? 0.1 : 1.0;
    if (useOffscreen) {
      worker.postMessage({ type: 'crop-percent', v: percent });
      worker.postMessage({ type: 'draw' });
    } else if (mainRenderer) {
      mainRenderer.setCrop(percent);
      mainRenderer.draw();
    }
  });
  zoomSlider.addEventListener('input', () => {
    const newScale = parseFloat(zoomSlider.value);
    const factor = newScale / viewState.scale;
    applyZoom(factor, canvas.width / 2, canvas.height / 2);
  });

  canvas.addEventListener('pointerdown', (e) => {
    isPanning = true;
    lastPointer = { x: e.offsetX, y: e.offsetY };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!isPanning) return;
    const dx = e.offsetX - lastPointer.x;
    const dy = e.offsetY - lastPointer.y;
    lastPointer = { x: e.offsetX, y: e.offsetY };
    viewState.viewCx -= dx / viewState.scale;
    viewState.viewCy += dy / viewState.scale;
    if (useOffscreen) {
      worker.postMessage({ type: 'set-view', cx: viewState.viewCx, cy: viewState.viewCy, scale: viewState.scale });
      worker.postMessage({ type: 'draw' });
    } else if (mainRenderer) {
      mainRenderer.updateView(viewState);
      mainRenderer.draw();
    }
  });
  canvas.addEventListener('pointerup', (e) => {
    isPanning = false;
    canvas.releasePointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointerleave', () => {
    isPanning = false;
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const factor = Math.exp(-e.deltaY / 500);
    applyZoom(factor, e.offsetX, e.offsetY);
  });
}

setupInteractions();

worker.addEventListener('message', (event) => {
  const msg = event.data;
  switch (msg.type) {
    case 'ready':
      logStatus('Worker 준비 완료');
      break;
    case 'progress':
      setProgress(`${msg.phase}: ${(msg.value * 100).toFixed(0)}%`);
      break;
    case 'loaded': {
      currentBBox = msg.bbox;
      if (!useOffscreen && msg.payload) {
        currentLayers = msg.payload;
        refreshLayersUI(currentLayers);
        mainRenderer.setLayers(currentLayers);
        mainRenderer.setStyle({ singleColor: singleColorToggle.checked });
        mainRenderer.setCrop(previewToggle.checked ? 0.1 : 1.0);
        fitView();
        mainRenderer.draw();
      } else {
        if (msg.payload) {
          currentLayers = msg.payload;
        }
        const layerItems = currentLayers.length
          ? currentLayers
          : msg.layers.map((name) => ({ name, color: '#93c5fd', segments: [], flashes: [] }));
        refreshLayersUI(layerItems);
        fitView();
      }
      break;
    }
    case 'error':
      logStatus(`Worker 오류: ${msg.message}`);
      break;
    default:
      console.warn('알 수 없는 Worker 메시지', msg);
  }
});
