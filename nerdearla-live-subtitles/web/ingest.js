// Captura el micrófono, lo resamplea a 16 kHz PCM 16-bit mono y lo envía por
// WebSocket a /ws/ingest/{sid}. Una pestaña = un escenario.
const btn = document.getElementById('btn');
const log = document.getElementById('log');
const SR = 16000;
let ws = null, ctx = null, node = null, stream = null, running = false;

function print(msg) { log.textContent += msg + '\n'; }

function floatTo16BitPCM(input) {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function downsample(buffer, inRate) {
  if (inRate === SR) return buffer;
  const ratio = inRate / SR;
  const outLen = Math.round(buffer.length / ratio);
  const out = new Float32Array(outLen);
  let oi = 0, ii = 0;
  while (oi < outLen) {
    const next = Math.round((oi + 1) * ratio);
    let sum = 0, cnt = 0;
    for (; ii < next && ii < buffer.length; ii++) { sum += buffer[ii]; cnt++; }
    out[oi++] = cnt ? sum / cnt : 0;
  }
  return out;
}

async function start() {
  const sid = document.getElementById('sid').value.trim();
  const name = document.getElementById('name').value.trim();
  await fetch('/api/sessions', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: sid, name, src_lang: 'auto', targets: ['es', 'en'] })
  });
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  const source = ctx.createMediaStreamSource(stream);
  node = ctx.createScriptProcessor(4096, 1, 1);
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/ingest/${encodeURIComponent(sid)}`);
  ws.binaryType = 'arraybuffer';
  node.onaudioprocess = (e) => {
    if (!ws || ws.readyState !== 1) return;
    const ds = downsample(e.inputBuffer.getChannelData(0), ctx.sampleRate);
    ws.send(floatTo16BitPCM(ds).buffer);
  };
  source.connect(node);
  node.connect(ctx.destination);
  running = true;
  btn.textContent = 'Detener captura';
  btn.classList.add('stop');
  print('Captura iniciada → sesión "' + sid + '"');
}

function stop() {
  running = false;
  if (node) node.disconnect();
  if (ctx) ctx.close();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ws) ws.close();
  btn.textContent = 'Iniciar captura';
  btn.classList.remove('stop');
  print('Captura detenida.');
}

btn.addEventListener('click', () => { running ? stop() : start().catch(e => print('Error: ' + e.message)); });
