// Vista de audiencia: elige sesión + idioma y muestra subtítulos en vivo.
// Usa textContent (nunca innerHTML) para insertar texto de forma segura.
const sessionSel = document.getElementById('session');
const langSel = document.getElementById('lang');
const caption = document.getElementById('caption');
const dot = document.getElementById('dot');
const statusText = document.getElementById('statusText');
let ws = null;

async function loadSessions() {
  const r = await fetch('/api/sessions');
  const data = await r.json();
  sessionSel.textContent = '';
  for (const s of data.sessions) {
    const o = document.createElement('option');
    o.value = s.id;
    o.textContent = s.name || s.id;
    sessionSel.appendChild(o);
  }
  if (data.sessions.length && !ws) connect();
}

function setStatus(live, text) {
  dot.classList.toggle('live', !!live);
  statusText.textContent = text;
}

function connect() {
  const sid = sessionSel.value;
  if (!sid) return;
  if (ws) { ws.close(); ws = null; }
  caption.textContent = '';
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/subtitles/${encodeURIComponent(sid)}`);
  ws.onopen = () => setStatus(true, 'en vivo');
  ws.onclose = () => setStatus(false, 'desconectado');
  ws.onerror = () => setStatus(false, 'error de conexión');
  ws.onmessage = (ev) => render(JSON.parse(ev.data));
}

function render(sub) {
  const lang = langSel.value;
  let text;
  if (lang === 'original') text = sub.original;
  else text = sub.translations[lang] || sub.original;
  if (!text) return;
  const div = document.createElement('div');
  div.className = 'cue';
  const main = document.createElement('div');
  main.textContent = text;
  div.appendChild(main);
  if (lang !== 'original' && lang !== sub.lang) {
    const orig = document.createElement('div');
    orig.className = 'orig';
    orig.textContent = sub.original;
    div.appendChild(orig);
  }
  caption.appendChild(div);
  // mantener solo las últimas 8 líneas visibles
  while (caption.children.length > 8) caption.removeChild(caption.firstChild);
  window.scrollTo(0, document.body.scrollHeight);
}

sessionSel.addEventListener('change', connect);
langSel.addEventListener('change', () => {});
loadSessions();
setInterval(loadSessions, 15000);
