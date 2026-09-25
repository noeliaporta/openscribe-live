// Panel de monitoreo: refresca el estado de todas las sesiones cada 3 s.
const rows = document.getElementById('rows');

function cell(text) { const td = document.createElement('td'); td.textContent = text; return td; }

function exportLinks(id) {
  const td = document.createElement('td');
  for (const fmt of ['srt', 'vtt', 'txt']) {
    const a = document.createElement('a');
    a.href = `/api/sessions/${encodeURIComponent(id)}/export?fmt=${fmt}`;
    a.textContent = fmt;
    a.target = '_blank';
    a.style.marginRight = '8px';
    td.appendChild(a);
  }
  return td;
}

async function refresh() {
  const r = await fetch('/api/sessions');
  const data = await r.json();
  rows.textContent = '';
  for (const s of data.sessions) {
    const tr = document.createElement('tr');
    tr.appendChild(cell(s.name || s.id));
    tr.appendChild(cell(`${s.src_lang} → ${s.targets.join(', ')}`));
    tr.appendChild(cell(s.subscribers));
    tr.appendChild(cell(s.cues));
    tr.appendChild(cell(s.latency + 's'));
    const st = document.createElement('td');
    const b = document.createElement('span');
    b.className = 'badge ' + (s.error ? 'err' : 'ok');
    b.textContent = s.error ? 'error' : 'ok';
    st.appendChild(b);
    if (s.error) { st.appendChild(document.createTextNode(' ' + s.error)); }
    tr.appendChild(st);
    tr.appendChild(exportLinks(s.id));
    rows.appendChild(tr);
  }
}

refresh();
setInterval(refresh, 3000);
