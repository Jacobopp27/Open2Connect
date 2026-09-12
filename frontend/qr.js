'use strict';
/* Generador QR mínimo (versión 1-6, ECC nivel L, modo byte). Sin dependencias
   ni CDN. Validado fuera de este repo generando PNGs y decodificándolos con
   jsQR (un lector independiente) para las versiones 1, 2, 3, 5 y 6 — ver
   docs/KIOSK.md. Si el texto no cabe en la versión 6 (134 bytes con ECC L),
   se usa igual el enlace visible como respaldo.

   Expone `window.renderQR(container, text, size)`: dibuja el QR (SVG) dentro
   de `container` y añade debajo un enlace de texto con el `text` original.
   `size` es opcional (ancho/alto en px del SVG; por defecto se ajusta a su
   contenido natural vía viewBox y CSS `width:100%`). Cárgalo con
   <script src="/qr.js"> ANTES del script que lo use (kiosk.js, agent.js). */
const QR = (() => {
  const GF_EXP = new Array(512);
  const GF_LOG = new Array(256);
  (function initGF() {
    let x = 1;
    for (let i = 0; i < 255; i++) { GF_EXP[i] = x; GF_LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11d; }
    for (let i = 255; i < 512; i++) GF_EXP[i] = GF_EXP[i - 255];
  })();
  const gfMul = (a, b) => (a === 0 || b === 0) ? 0 : GF_EXP[GF_LOG[a] + GF_LOG[b]];
  const polyMul = (a, b) => {
    const result = new Array(a.length + b.length - 1).fill(0);
    for (let i = 0; i < a.length; i++) for (let j = 0; j < b.length; j++) result[i + j] ^= gfMul(a[i], b[j]);
    return result;
  };
  const rsGenPoly = (degree) => { let poly = [1]; for (let i = 0; i < degree; i++) poly = polyMul(poly, [1, GF_EXP[i]]); return poly; };
  const rsEncode = (data, ecCount) => {
    const gen = rsGenPoly(ecCount);
    const res = data.concat(new Array(ecCount).fill(0));
    for (let i = 0; i < data.length; i++) {
      const coef = res[i];
      if (coef !== 0) for (let j = 0; j < gen.length; j++) res[i + j] ^= gfMul(gen[j], coef);
    }
    return res.slice(data.length);
  };
  // version, tamaño en módulos, capacidad en bytes (modo byte, ECC L), codewords totales, EC por bloque, nº de bloques.
  const VERSIONS = [
    { v: 1, size: 21, capacity: 17, totalCw: 26, ecCw: 7, blocks: 1 },
    { v: 2, size: 25, capacity: 32, totalCw: 44, ecCw: 10, blocks: 1 },
    { v: 3, size: 29, capacity: 53, totalCw: 70, ecCw: 15, blocks: 1 },
    { v: 4, size: 33, capacity: 78, totalCw: 100, ecCw: 20, blocks: 1 },
    { v: 5, size: 37, capacity: 106, totalCw: 134, ecCw: 26, blocks: 1 },
    { v: 6, size: 41, capacity: 134, totalCw: 172, ecCw: 18, blocks: 2 },
  ];
  function encodeSegment(bytes) {
    const v = VERSIONS.find((x) => bytes.length <= x.capacity);
    if (!v) throw new Error('Texto demasiado largo para el QR (máx 134 bytes).');
    const bits = [];
    const pushBits = (val, len) => { for (let i = len - 1; i >= 0; i--) bits.push((val >> i) & 1); };
    pushBits(0b0100, 4); // modo byte
    pushBits(bytes.length, 8); // contador (válido para v1-9)
    for (const b of bytes) pushBits(b, 8);
    const dataCwCount = v.totalCw - v.ecCw * v.blocks;
    const termLen = Math.min(4, Math.max(0, dataCwCount * 8 - bits.length));
    for (let i = 0; i < termLen; i++) bits.push(0);
    while (bits.length % 8 !== 0) bits.push(0);
    const codewords = [];
    for (let i = 0; i < bits.length; i += 8) {
      let byte = 0;
      for (let j = 0; j < 8; j++) byte = (byte << 1) | bits[i + j];
      codewords.push(byte);
    }
    const PAD = [0xec, 0x11];
    for (let p = 0; codewords.length < dataCwCount; p++) codewords.push(PAD[p % 2]);
    const perBlock = dataCwCount / v.blocks;
    const blocks = [];
    for (let i = 0; i < v.blocks; i++) blocks.push(codewords.slice(i * perBlock, (i + 1) * perBlock));
    const ecBlocks = blocks.map((b) => rsEncode(b, v.ecCw));
    const finalData = [];
    const maxLen = Math.max(...blocks.map((b) => b.length));
    for (let i = 0; i < maxLen; i++) for (const b of blocks) if (i < b.length) finalData.push(b[i]);
    const maxEcLen = Math.max(...ecBlocks.map((b) => b.length));
    for (let i = 0; i < maxEcLen; i++) for (const b of ecBlocks) if (i < b.length) finalData.push(b[i]);
    return { version: v.v, size: v.size, codewords: finalData };
  }
  function computeFormatBits(ecBits, maskBits) {
    const data = (ecBits << 3) | maskBits;
    let value = data << 10;
    const gen = 0b10100110111;
    for (let i = 14; i >= 10; i--) if (value & (1 << i)) value ^= gen << (i - 10);
    return ((data << 10) | value) ^ 0b101010000010010;
  }
  function placeFormatBits(m, size, fmt) {
    const bits = [];
    for (let i = 14; i >= 0; i--) bits.push((fmt >> i) & 1);
    const copy1 = [[8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8], [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8]];
    copy1.forEach(([r, c], i) => { m[r][c] = bits[i]; });
    for (let i = 0; i < 8; i++) m[8][size - 1 - i] = bits[i];
    for (let i = 0; i < 7; i++) m[size - 7 + i][8] = bits[8 + i];
  }
  function buildMatrix(version, size, codewords) {
    const m = Array.from({ length: size }, () => new Array(size).fill(null));
    const setFinder = (r, c) => {
      for (let i = -1; i <= 7; i++) for (let j = -1; j <= 7; j++) {
        const rr = r + i, cc = c + j;
        if (rr < 0 || cc < 0 || rr >= size || cc >= size) continue;
        const inside = i >= 0 && i <= 6 && j >= 0 && j <= 6;
        if (!inside) { m[rr][cc] = 0; continue; }
        const isBorder = i === 0 || i === 6 || j === 0 || j === 6;
        const isCore = i >= 2 && i <= 4 && j >= 2 && j <= 4;
        m[rr][cc] = (isBorder || isCore) ? 1 : 0;
      }
    };
    setFinder(0, 0); setFinder(0, size - 7); setFinder(size - 7, 0);
    for (let i = 8; i < size - 8; i++) { m[6][i] = i % 2 === 0 ? 1 : 0; m[i][6] = i % 2 === 0 ? 1 : 0; }
    const ALIGN = { 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34] };
    const positions = ALIGN[version] || [];
    for (const r of positions) for (const c of positions) {
      if ((r === 6 && c === 6) || (r === 6 && c === size - 7) || (r === size - 7 && c === 6)) continue;
      for (let i = -2; i <= 2; i++) for (let j = -2; j <= 2; j++) m[r + i][c + j] = Math.max(Math.abs(i), Math.abs(j)) !== 1 ? 1 : 0;
    }
    m[4 * version + 9][8] = 1; // módulo oscuro fijo
    for (let i = 0; i < 9; i++) { if (m[8][i] === null) m[8][i] = -1; if (m[i][8] === null) m[i][8] = -1; }
    for (let i = 0; i < 8; i++) { if (m[8][size - 1 - i] === null) m[8][size - 1 - i] = -1; if (m[size - 1 - i][8] === null) m[size - 1 - i][8] = -1; }
    const maskFn = (r, c) => (r + c) % 2 === 0; // máscara 0, fija (siempre decodificable; no se optimiza penalización)
    const totalBits = codewords.length * 8;
    const bitAt = (i) => (codewords[i >> 3] >> (7 - (i & 7))) & 1;
    let bitIndex = 0, dir = -1;
    for (let col = size - 1; col > 0; col -= 2) {
      if (col === 6) col--;
      for (let n = 0; n < size; n++) {
        const row = dir < 0 ? size - 1 - n : n;
        for (const c of [col, col - 1]) {
          if (m[row][c] !== null) continue;
          const bit = bitIndex < totalBits ? bitAt(bitIndex) : 0;
          bitIndex++;
          m[row][c] = bit ^ (maskFn(row, c) ? 1 : 0);
        }
      }
      dir = -dir;
    }
    placeFormatBits(m, size, computeFormatBits(0b01, 0)); // nivel L, máscara 0
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) if (m[r][c] === -1) m[r][c] = 0;
    return m;
  }
  return { matrix: (text) => { const bytes = Array.from(new TextEncoder().encode(text)); const { version, size, codewords } = encodeSegment(bytes); return buildMatrix(version, size, codewords); } };
})();

/**
 * Dibuja un QR SVG de `text` dentro de `container` (se limpia primero) y añade
 * debajo un enlace de texto con el propio `text`. `size` (opcional) fija el
 * ancho/alto en px del SVG; si se omite, el SVG escala al 100% del contenedor
 * vía CSS (ver clase .qr-svg en kiosk.css/agent.css).
 */
function renderQR(container, text, size) {
  container.innerHTML = '';
  try {
    const m = QR.matrix(text);
    const quiet = 4, n = m.length, cell = 6, vb = (n + quiet * 2) * cell;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', `0 0 ${vb} ${vb}`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Código QR: ' + text);
    svg.classList.add('qr-svg');
    if (size) { svg.setAttribute('width', size); svg.setAttribute('height', size); }
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', vb); bg.setAttribute('height', vb); bg.setAttribute('fill', '#fff');
    svg.appendChild(bg);
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (m[r][c]) {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', (c + quiet) * cell); rect.setAttribute('y', (r + quiet) * cell);
      rect.setAttribute('width', cell); rect.setAttribute('height', cell); rect.setAttribute('fill', '#102e29');
      svg.appendChild(rect);
    }
    container.appendChild(svg);
  } catch (e) {
    console.warn('QR no generado, se muestra solo el enlace:', e.message);
  }
  const link = document.createElement('a');
  link.href = text; link.textContent = text; link.className = 'qr-link'; link.target = '_blank'; link.rel = 'noopener';
  container.appendChild(link);
}

window.renderQR = renderQR;
