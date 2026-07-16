/* ======================================================================
   SELENE-AI Mission Console
   All numbers rendered on this page are read from the embedded JSON blob
   above, which is a direct export of the Python pipeline's real output.
   Nothing here is hand-typed placeholder data.
====================================================================== */
const DATA = JSON.parse(document.getElementById('selene-data').textContent);

/* ---------------- color ramps ---------------- */
function lerp(a,b,t){ return a + (b-a)*t; }
function mix(c1, c2, t){
  return [ Math.round(lerp(c1[0],c2[0],t)), Math.round(lerp(c1[1],c2[1],t)), Math.round(lerp(c1[2],c2[2],t)) ];
}
function rampColor(stops, t){
  t = Math.max(0, Math.min(1, t));
  const seg = 1/(stops.length-1);
  const idx = Math.min(stops.length-2, Math.floor(t/seg));
  const localT = (t - idx*seg)/seg;
  return mix(stops[idx], stops[idx+1], localT);
}

const RAMPS = {
  ice_likelihood_pct: [[10,13,18],[16,44,46],[46,120,112],[95,211,196],[210,255,246]],
  cpr:                [[10,13,18],[26,42,58],[38,92,112],[95,211,196],[230,255,250]],
  dop:                [[15,10,22],[60,32,86],[124,58,110],[210,110,96],[248,196,120]],
  slope_deg:          [[10,13,18],[54,38,26],[140,86,42],[226,145,79],[255,214,160]],
  roughness:          [[10,13,18],[48,36,22],[132,86,40],[226,145,79],[255,220,168]],
  elevation_m:        [[8,10,14],[34,44,56],[70,96,110],[150,190,190],[232,238,236]],
  illumination_hours: [[10,13,18],[52,44,20],[132,108,34],[224,186,70],[255,232,150]],
};

const LAYER_LABELS = {
  ice_likelihood_pct: 'Ice likelihood', cpr: 'CPR', dop: 'DOP', slope_deg: 'Slope',
  roughness: 'Roughness', elevation_m: 'Elevation', illumination_hours: 'Solar illumination',
};
const LAYER_UNITS = {
  ice_likelihood_pct: '%', cpr: '', dop: '', slope_deg: ' deg', roughness: '', elevation_m: ' m', illumination_hours: ' h',
};

function gridMinMax(g){
  let min = Infinity, max = -Infinity;
  for(const row of g) for(const v of row){ if(v<min)min=v; if(v>max)max=v; }
  return [min, max];
}

function drawGrid(canvas, gridName, overlayFn){
  const grid = DATA.grids[gridName];
  const n = DATA.meta.grid_size;
  const ramp = RAMPS[gridName] || RAMPS.ice_likelihood_pct;
  const [min, max] = gridMinMax(grid);
  const range = (max - min) || 1;

  const off = document.createElement('canvas');
  off.width = n; off.height = n;
  const octx = off.getContext('2d');
  const img = octx.createImageData(n, n);
  for(let r=0; r<n; r++){
    for(let c=0; c<n; c++){
      const v = grid[r][c];
      const t = (v - min)/range;
      const [rr,gg,bb] = rampColor(ramp, t);
      const i = (r*n + c)*4;
      img.data[i]=rr; img.data[i+1]=gg; img.data[i+2]=bb; img.data[i+3]=255;
    }
  }
  octx.putImageData(img, 0, 0);

  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
  if(overlayFn) overlayFn(ctx, canvas.width/n, canvas.height/n);
  return [min, max];
}

/* ---------------- problem compare ---------------- */
(function(){
  const n = DATA.meta.grid_size;
  const cprGrid = DATA.grids.cpr;
  const cprOnly = [];
  for(let r=0;r<n;r++){ const row=[]; for(let c=0;c<n;c++){ row.push(cprGrid[r][c] > 1.0 ? 1 : 0); } cprOnly.push(row); }
  DATA.grids.__cpr_only_mask = cprOnly;
  drawGrid(document.getElementById('baselineCanvas'), '__cpr_only_mask');

  const iceGrid = DATA.grids.ice_likelihood_pct;
  const tripleMask = [];
  for(let r=0;r<n;r++){ const row=[]; for(let c=0;c<n;c++){ row.push(iceGrid[r][c] > 40 ? 1 : 0); } tripleMask.push(row); }
  DATA.grids.__triple_mask = tripleMask;
  drawGrid(document.getElementById('tripleCanvas'), '__triple_mask');

  document.getElementById('cprOnlyCount').textContent = DATA.fp_stats.cpr_only_pixel_count + ' px';
  document.getElementById('tripleCount').textContent = DATA.fp_stats.triple_evidence_pixel_count + ' px';
  document.getElementById('reductionPct').textContent = DATA.fp_stats.area_reduction_pct + '%';
})();

/* ---------------- telemetry strip ---------------- */
(function(){
  const balanced = DATA.profiles.balanced.sites;
  const cells = [
    [DATA.fp_stats.area_reduction_pct + '%', 'False-positive reduction'],
    [balanced.length, 'Candidate sites ranked'],
    [DATA.rover.total_distance_m + ' m', 'Rover traverse planned'],
    [DATA.validation.filter(c=>c.passed===true).length + '/' + DATA.validation.filter(c=>c.passed!==null).length, 'Validation checks passed'],
  ];
  const el = document.getElementById('telemetryStrip');
  el.innerHTML = cells.map(([num,lbl]) => `<div class="telemetry-cell"><span class="num">${num}</span><span class="lbl">${lbl}</span></div>`).join('');
})();
document.getElementById('craterName').textContent = DATA.meta.crater_name.split('(')[0].trim();

/* ---------------- console: profile tabs ---------------- */
const PROFILE_META = {
  science_first: { name: 'Science-First', desc: 'Maximize ice-detection value' },
  safety_first:  { name: 'Safety-First',  desc: 'Minimize landing & terrain risk' },
  balanced:      { name: 'Balanced',      desc: 'Trade off science and safety' },
};
let activeProfile = 'balanced';
let activeLayer = 'ice_likelihood_pct';

function renderProfileTabs(){
  const el = document.getElementById('profileTabs');
  el.innerHTML = Object.keys(PROFILE_META).map(key => {
    const m = PROFILE_META[key];
    return `<button class="profile-tab ${key===activeProfile?'active':''}" data-profile="${key}">
      <span class="t-name">${m.name}</span><span class="t-desc">${m.desc}</span>
    </button>`;
  }).join('');
  el.querySelectorAll('.profile-tab').forEach(btn=>{
    btn.addEventListener('click', () => { activeProfile = btn.dataset.profile; renderAll(); });
  });
}

function renderWeightBars(){
  const weights = DATA.profiles[activeProfile].weights;
  const labels = { ice:'Ice', slope:'Slope', solar:'Solar', roughness:'Rough', distance:'Dist.' };
  const el = document.getElementById('weightBars');
  el.innerHTML = Object.keys(labels).map(k => {
    const pct = Math.round(weights[k]*100);
    return `<div class="weight-row">
      <span class="wl">${labels[k]}</span>
      <div class="weight-track"><div class="weight-fill" style="width:${pct}%"></div></div>
      <span class="wv">${pct}%</span>
    </div>`;
  }).join('');
}

/* ---------------- console: layer toggle ---------------- */
function renderLayerToggle(){
  const el = document.getElementById('layerToggle');
  el.innerHTML = Object.keys(LAYER_LABELS).map(key =>
    `<button class="layer-btn ${key===activeLayer?'active':''}" data-layer="${key}">${LAYER_LABELS[key]}</button>`
  ).join('');
  el.querySelectorAll('.layer-btn').forEach(btn=>{
    btn.addEventListener('click', () => { activeLayer = btn.dataset.layer; renderMap(); });
  });
}

/* ---------------- console: map with sites + rover path ---------------- */
function renderMap(){
  document.getElementById('activeLayerLabel').textContent = LAYER_LABELS[activeLayer];
  const canvas = document.getElementById('mapCanvas');
  const n = DATA.meta.grid_size;

  const [min, max] = drawGrid(canvas, activeLayer, (ctx, cw, ch) => {
    // PSR floor boundary
    ctx.strokeStyle = 'rgba(231,236,243,0.35)';
    ctx.lineWidth = 1;
    const floor = DATA.grids.floor_mask;
    ctx.beginPath();
    for(let r=0;r<n;r++){
      for(let c=0;c<n;c++){
        if(floor[r][c] > 0.5){
          const isEdge = (r>0 && floor[r-1][c]<0.5) || (r<n-1 && floor[r+1][c]<0.5) ||
                         (c>0 && floor[r][c-1]<0.5) || (c<n-1 && floor[r][c+1]<0.5);
          if(isEdge){ ctx.rect(c*cw, r*ch, cw, ch); }
        }
      }
    }
    ctx.stroke();

    // rover path
    const wp = DATA.rover.waypoints;
    if(wp && wp.length){
      ctx.strokeStyle = '#5FD3C4';
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      wp.forEach(([r,c], i) => {
        const x = c*cw + cw/2, y = r*ch + ch/2;
        if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
      });
      ctx.stroke();
    }

    // candidate sites
    const sites = DATA.profiles[activeProfile].sites;
    sites.forEach(site => {
      const x = site.col*cw + cw/2, y = site.row*ch + ch/2;
      ctx.beginPath();
      ctx.arc(x, y, site.rank===1 ? 7 : 5, 0, Math.PI*2);
      ctx.fillStyle = site.rank===1 ? '#E2594F' : '#E2914F';
      ctx.fill();
      ctx.strokeStyle = '#0A0D12';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = '#E7ECF3';
      ctx.font = '600 11px "IBM Plex Mono", monospace';
      ctx.fillText(site.site_id.replace('Site-',''), x+9, y+4);
    });
  });

  document.getElementById('legendMin').textContent = min.toFixed(2) + LAYER_UNITS[activeLayer];
  document.getElementById('legendMax').textContent = max.toFixed(2) + LAYER_UNITS[activeLayer];
  const ramp = RAMPS[activeLayer] || RAMPS.ice_likelihood_pct;
  const stops = ramp.map(c => `rgb(${c[0]},${c[1]},${c[2]})`).join(',');
  document.getElementById('legendRamp').style.background = `linear-gradient(90deg, ${stops})`;

  // hover tooltip
  const tip = document.getElementById('mapTip');
  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    const col = Math.min(n-1, Math.max(0, Math.floor(x*n)));
    const row = Math.min(n-1, Math.max(0, Math.floor(y*n)));
    const v = DATA.grids[activeLayer][row][col];
    tip.style.display = 'block';
    tip.style.left = (e.clientX - rect.left + 14) + 'px';
    tip.style.top = (e.clientY - rect.top + 10) + 'px';
    tip.innerHTML = `row ${row}, col ${col}<br><b>${v.toFixed(2)}${LAYER_UNITS[activeLayer]}</b>`;
  };
  canvas.onmouseleave = () => { tip.style.display = 'none'; };
}

/* ---------------- console: ranked site table ---------------- */
function renderSiteTable(){
  const sites = DATA.profiles[activeProfile].sites;
  const body = document.getElementById('siteTableBody');
  body.innerHTML = sites.map(s => `
    <tr class="${s.rank===1?'rank1':''}">
      <td class="num">${s.rank}</td>
      <td class="site-id">${s.site_id}</td>
      <td><span class="score-pill">${s.score}</span></td>
      <td class="num">${s.ice_pct}</td>
      <td class="num">${s.slope_deg}</td>
      <td class="num">${s.solar_hours}</td>
      <td class="num">${s.distance_to_ice_m} m</td>
      <td class="tradeoff">${s.trade_off}</td>
    </tr>
  `).join('');
}

/* ---------------- rover panel ---------------- */
function renderRover(){
  const r = DATA.rover;
  const el = document.getElementById('roverStats');
  el.innerHTML = `
    <div class="stat-card"><span class="num">${r.total_distance_m} m</span><span class="lbl">Total distance</span></div>
    <div class="stat-card"><span class="num">${r.total_energy_cost}</span><span class="lbl">Relative energy cost</span></div>
    <div class="stat-card"><span class="num">${r.n_segments}</span><span class="lbl">Path segments</span></div>
    <div class="stat-card ${r.battery_budget_ok ? 'ok' : ''}"><span class="num">${r.max_consecutive_dark_steps}</span><span class="lbl">Max dark steps ${r.battery_budget_ok ? '(within budget)' : '(EXCEEDS budget)'}</span></div>
  `;

  // elevation-along-path chart, sampled from the real elevation grid
  const wp = r.waypoints;
  const elev = DATA.grids.elevation_m;
  const samples = wp.map(([row,col]) => elev[row][col]);
  const minE = Math.min(...samples), maxE = Math.max(...samples);
  const rangeE = (maxE - minE) || 1;
  const w = 600, h = 160, pad = 10;
  const pts = samples.map((v,i) => {
    const x = pad + (i/(samples.length-1)) * (w-2*pad);
    const y = h - pad - ((v-minE)/rangeE) * (h-2*pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  const svg = document.getElementById('elevChart');
  svg.innerHTML = `
    <polyline points="${pts}" fill="none" stroke="#5FD3C4" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
    <polyline points="${pad},${h-pad} ${pts} ${w-pad},${h-pad}" fill="rgba(95,211,196,0.08)" stroke="none"/>
    <line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#262D3A" stroke-width="1"/>
  `;
  document.getElementById('elevCaption').textContent =
    `Elevation range along path: ${minE.toFixed(1)} m to ${maxE.toFixed(1)} m over ${samples.length} waypoints (start: rim, end: PSR floor target)`;
}

/* ---------------- pipeline ---------------- */
function renderPipeline(){
  const stages = [
    { n:'01', t:'Feature extraction', d:'CPR, DOP and m-chi decomposition (surface / volume / double-bounce scattering power) computed per pixel, alongside slope, roughness and illumination.', meta: `Triple-evidence footprint: ${DATA.fp_stats.triple_evidence_pixel_count} px vs. ${DATA.fp_stats.cpr_only_pixel_count} px for CPR-only` },
    { n:'02', t:'Ice likelihood estimation', d:'A Random Forest trained on Stage-1 pseudo-labels produces a per-pixel ice probability with a bootstrap confidence interval across trees.', meta: DATA.feature_importance ? `Top feature: volume_power (${(DATA.feature_importance.volume_power*100).toFixed(0)}% importance)` : '' },
    { n:'03', t:'Candidate site generation', d:'Locally-safe, illuminated patches near the permanently shadowed floor are scanned and shortlisted, respecting hard slope and solar constraints.', meta: `${DATA.profiles.balanced.sites.length} candidate sites shortlisted` },
    { n:'04', t:'Mission suitability scoring', d:'Each site is scored against configurable weights (Science-First / Safety-First / Balanced) with a full per-factor contribution breakdown.', meta: 'Re-run live in the console above' },
    { n:'05', t:'Energy-aware rover planning', d:'A traverse graph is built over the scene and searched with Dijkstra\u2019s algorithm under a slope-and-roughness energy cost, not raw distance.', meta: `${DATA.rover.total_distance_m} m planned in ${DATA.rover.n_segments} segments` },
  ];
  document.getElementById('pipelineStages').innerHTML = stages.map(s => `
    <div class="stage">
      <div class="idx">${s.n}</div>
      <div>
        <h4>${s.t}</h4>
        <p>${s.d}</p>
        <div class="stage-meta">${s.meta}</div>
      </div>
    </div>
  `).join('');
}

/* ---------------- validation ---------------- */
function renderValidation(){
  const el = document.getElementById('validationGrid');
  el.innerHTML = DATA.validation.map(c => {
    const status = c.passed === null ? 'na' : (c.passed ? 'pass' : 'fail');
    const statusLabel = c.passed === null ? 'N/A' : (c.passed ? 'PASS' : 'FAIL');
    const resultText = c.result_pct === null ? 'Manual step' : `${c.result_pct}%`;
    return `<div class="val-card ${status}">
      <div class="vhead"><h4>${c.check}</h4><span class="val-status ${status}">${statusLabel}</span></div>
      <div class="vresult">${resultText}</div>
      <div class="vtarget">Target: ${c.target}</div>
      <div class="vnote">${c.note}</div>
    </div>`;
  }).join('');
}

/* ---------------- footer ---------------- */
document.getElementById('footTimestamp').textContent = 'Generated ' + new Date().toISOString().slice(0,16).replace('T',' ') + ' UTC';

/* ---------------- 3D crater terrain background (signature element) ----
   A single persistent WebGL scene, fixed behind the entire page, built
   directly from the same elevation_m / ice_likelihood_pct / roughness
   grids used everywhere else here. The camera flies to a different
   vantage point as you scroll through each section, plus a small
   mouse-parallax offset and slow idle drift. Falls back to a plain CSS
   gradient (already the page background) if WebGL is unavailable --
   the rest of the page is fully functional either way.
------------------------------------------------------------------------ */
function initBackground3D(){
  if (typeof THREE === 'undefined') throw new Error('three.js failed to load');

  const canvas = document.getElementById('bgCanvas');
  const n = DATA.meta.grid_size;
  const elev = DATA.grids.elevation_m;
  const ice = DATA.grids.ice_likelihood_pct;
  const rough = DATA.grids.roughness;

  const [elevMin, elevMax] = gridMinMax(elev);
  const elevRange = (elevMax - elevMin) || 1;
  const [roughMin, roughMax] = gridMinMax(rough);
  const roughRange = (roughMax - roughMin) || 1;

  const SCENE_SIZE = 9;
  const HEIGHT_SCALE = 2.8;

  function heightAt(r, c){
    const hNorm = (elev[r][c] - elevMin) / elevRange;
    return hNorm * HEIGHT_SCALE - HEIGHT_SCALE * 0.55;
  }

  // ---- geometry: built directly from the grid, not a primitive ----
  const positions = new Float32Array(n*n*3);
  const colors = new Float32Array(n*n*3);
  for(let r=0; r<n; r++){
    for(let c=0; c<n; c++){
      const i = r*n + c;
      const x = (c/(n-1) - 0.5) * SCENE_SIZE;
      const z = (r/(n-1) - 0.5) * SCENE_SIZE;
      positions[i*3] = x; positions[i*3+1] = heightAt(r,c); positions[i*3+2] = z;

      const iceNorm = Math.max(0, Math.min(1, ice[r][c] / 100));
      const roughNorm = (rough[r][c] - roughMin) / roughRange;
      const base = rampColor(RAMPS.ice_likelihood_pct, iceNorm);
      const rockTint = rampColor(RAMPS.roughness, roughNorm);
      const col = mix(base, rockTint, 0.3 * roughNorm);
      colors[i*3] = col[0]/255; colors[i*3+1] = col[1]/255; colors[i*3+2] = col[2]/255;
    }
  }

  const indices = [];
  for(let r=0; r<n-1; r++){
    for(let c=0; c<n-1; c++){
      const a = r*n + c, b = a+1, cc = a+n, d = cc+1;
      indices.push(a, cc, b,  b, cc, d);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setIndex(indices);
  geo.computeVertexNormals();

  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true, flatShading: true, roughness: 0.92, metalness: 0.04,
  });
  const terrain = new THREE.Mesh(geo, mat);

  const scene = new THREE.Scene();
  scene.add(terrain);

  // grazing low-angle "polar sun" -- the same geometry that creates the
  // permanently shadowed region this whole system exists to characterize
  const sun = new THREE.DirectionalLight(0xfff2df, 1.4);
  sun.position.set(-6, 0.9, 3.4);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x5fa8d3, 0.4);
  fill.position.set(4, 2, -3);
  scene.add(fill);
  scene.add(new THREE.AmbientLight(0x1a2230, 0.6));

  // rover traverse path, elevated slightly above the surface
  const wp = DATA.rover.waypoints || [];
  if(wp.length){
    const pathPts = wp.map(([r,c]) => {
      const x = (c/(n-1) - 0.5) * SCENE_SIZE;
      const z = (r/(n-1) - 0.5) * SCENE_SIZE;
      return new THREE.Vector3(x, heightAt(r,c) + 0.06, z);
    });
    const pathGeo = new THREE.BufferGeometry().setFromPoints(pathPts);
    const pathMat = new THREE.LineBasicMaterial({ color: 0x5fd3c4, linewidth: 2 });
    scene.add(new THREE.Line(pathGeo, pathMat));
  }

  // candidate site beacons (balanced profile)
  const beaconGeo = new THREE.OctahedronGeometry(0.1, 0);
  DATA.profiles.balanced.sites.forEach(site => {
    const x = (site.col/(n-1) - 0.5) * SCENE_SIZE;
    const z = (site.row/(n-1) - 0.5) * SCENE_SIZE;
    const y = heightAt(site.row, site.col) + 0.18;
    const color = site.rank === 1 ? 0xe2594f : 0xe2914f;
    const beacon = new THREE.Mesh(beaconGeo, new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.45 }));
    beacon.position.set(x, y, z);
    scene.add(beacon);
  });

  let renderer;
  try{
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch(e){
    throw new Error('WebGL context could not be created');
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const camera = new THREE.PerspectiveCamera(44, window.innerWidth / window.innerHeight, 0.1, 100);

  // ---- scroll-driven camera keyframes: the camera slowly revolves and
  // reframes as each section scrolls into view, rather than being an
  // isolated widget the user has to drag ----
  const KEYFRAMES = [
    { p: 0.00, theta: 0.55, phi: 1.12, radius: 9.4, lookY: -0.15 },
    { p: 0.14, theta: 1.35, phi: 0.92, radius: 7.2, lookY: -0.05 },
    { p: 0.32, theta: 2.35, phi: 0.55, radius: 6.1, lookY: -0.30 },
    { p: 0.50, theta: 3.35, phi: 1.02, radius: 5.3, lookY: -0.10 },
    { p: 0.68, theta: 4.30, phi: 1.22, radius: 8.6, lookY: -0.20 },
    { p: 0.84, theta: 5.15, phi: 1.02, radius: 7.6, lookY: -0.18 },
    { p: 1.00, theta: 6.05, phi: 1.12, radius: 9.6, lookY: -0.15 },
  ];
  function keyframeAt(p){
    p = Math.max(0, Math.min(1, p));
    for(let i=0; i<KEYFRAMES.length-1; i++){
      const a = KEYFRAMES[i], b = KEYFRAMES[i+1];
      if(p >= a.p && p <= b.p){
        const t = (p - a.p) / (b.p - a.p || 1);
        return {
          theta: lerp(a.theta, b.theta, t),
          phi: lerp(a.phi, b.phi, t),
          radius: lerp(a.radius, b.radius, t),
          lookY: lerp(a.lookY, b.lookY, t),
        };
      }
    }
    return KEYFRAMES[KEYFRAMES.length-1];
  }

  let curTheta = KEYFRAMES[0].theta, curPhi = KEYFRAMES[0].phi;
  let curRadius = KEYFRAMES[0].radius, curLookY = KEYFRAMES[0].lookY;
  let mouseNX = 0, mouseNY = 0;
  let idleSpin = 0;

  window.addEventListener('mousemove', (e) => {
    mouseNX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseNY = (e.clientY / window.innerHeight - 0.5) * 2;
  }, { passive: true });

  function scrollProgress(){
    const max = document.documentElement.scrollHeight - window.innerHeight;
    return max > 0 ? window.scrollY / max : 0;
  }

  function resize(){
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  function animate(){
    requestAnimationFrame(animate);
    idleSpin += 0.0004;

    const target = keyframeAt(scrollProgress());
    curTheta += (target.theta - curTheta) * 0.045;
    curPhi += (target.phi - curPhi) * 0.06;
    curRadius += (target.radius - curRadius) * 0.05;
    curLookY += (target.lookY - curLookY) * 0.06;

    const theta = curTheta + idleSpin + mouseNX * 0.05;
    const phi = Math.max(0.3, Math.min(1.4, curPhi + mouseNY * 0.025));

    const x = curRadius * Math.sin(phi) * Math.sin(theta);
    const y = curRadius * Math.cos(phi);
    const z = curRadius * Math.sin(phi) * Math.cos(theta);
    camera.position.set(x, y, z);
    camera.lookAt(0, curLookY, 0);

    renderer.render(scene, camera);
  }
  animate();
}

try{
  initBackground3D();
} catch(err){
  console.warn('3D background unavailable, using flat gradient fallback:', err.message);
  const bg = document.getElementById('bgCanvas');
  if(bg) bg.style.display = 'none';
}

/* ---------------- ambient 3D tilt on panel cards ---------------- */
function attachTilt(el, maxDeg){
  let raf = null;
  el.addEventListener('pointermove', (e) => {
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    if(raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      el.style.transform = `perspective(700px) rotateX(${(-py*maxDeg).toFixed(2)}deg) rotateY(${(px*maxDeg).toFixed(2)}deg) translateZ(2px)`;
    });
  });
  el.addEventListener('pointerleave', () => {
    if(raf) cancelAnimationFrame(raf);
    el.style.transform = 'perspective(700px) rotateX(0deg) rotateY(0deg)';
  });
}
const prefersReducedMotion = typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------------- boot ---------------- */
function renderAll(){
  renderProfileTabs();
  renderWeightBars();
  renderMap();
  renderSiteTable();
}
renderLayerToggle();
renderAll();
renderRover();
renderPipeline();
renderValidation();

// tilt + scroll-reveal are attached AFTER all dynamic content above exists,
// since stat-cards / val-cards / pipeline stages are generated at runtime
if(!prefersReducedMotion){
  document.querySelectorAll('.compare-card, .stat-card, .val-card, .stage').forEach(el => {
    el.classList.add('tilt');
    attachTilt(el, 5);
  });
}

(function initScrollReveal(){
  const targets = document.querySelectorAll('.panel, .compare-card, .stat-card, .val-card, .stage, .honesty');
  if(!('IntersectionObserver' in window) || prefersReducedMotion){
    return; // elements are visible by default; nothing further needed
  }
  targets.forEach(el => el.classList.add('reveal-pending'));
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if(entry.isIntersecting){
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });
  targets.forEach(el => io.observe(el));
})();
