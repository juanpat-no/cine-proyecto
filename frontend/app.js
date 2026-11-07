const $ = (s, el = document) => el.querySelector(s);
const money = n => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(n);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const hora = d => new Date(d).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
const fecha = d => new Date(d).toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });
const hoyLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const PALETA = ['#e63946', '#f4a261', '#2a9d8f', '#457b9d', '#8e6bd1', '#e9c46a', '#16a085', '#d35400'];

const estado = {
  token: localStorage.getItem('token'),
  usuario: JSON.parse(localStorage.getItem('usuario') || 'null'),
};
const vista = $('#vista');

function toast(msg, tipo = 'ok') {
  const el = document.createElement('div');
  el.textContent = msg;
  if (tipo === 'error') el.className = 'error';
  $('#toast').appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

const guard = fn => async (...args) => {
  try { await fn(...args); } catch (e) { toast(e.message, 'error'); }
};

async function api(ruta, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (estado.token) headers.Authorization = 'Bearer ' + estado.token;
  let body = opts.body;
  if (body && !(body instanceof URLSearchParams)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  const r = await fetch(ruta, { method: opts.method || 'GET', headers, body });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    if (r.status === 401 && estado.token) cerrarSesion(false);
    let msg = 'Error ' + r.status;
    if (data && data.detail) {
      msg = typeof data.detail === 'string' ? data.detail : data.detail.map(e => e.msg).join('. ');
    }
    throw new Error(msg);
  }
  return data;
}

/* ---------- Sesión ---------- */
function pintarNav() {
  const u = estado.usuario;
  $('#nav-user').innerHTML = u
    ? `<a href="#/compras">Mis compras</a>
       ${u.rol === 'admin' ? '<a href="#/admin/dashboard">Administración</a>' : ''}
       <span class="chip">${esc(u.nombre.split(' ')[0])}</span>
       <button class="btn ghost small" id="b-out">Salir</button>`
    : '<button class="btn" id="b-in">Ingresar</button>';
  if ($('#b-in')) $('#b-in').onclick = abrirAuth;
  if ($('#b-out')) $('#b-out').onclick = () => cerrarSesion();
}

function cerrarSesion(avisar = true) {
  estado.token = null; estado.usuario = null;
  localStorage.removeItem('token'); localStorage.removeItem('usuario');
  pintarNav();
  if (avisar) toast('Sesión cerrada');
  if (location.hash === '#/' || location.hash === '') router(); else location.hash = '#/';
}

async function iniciarSesion(correo, password) {
  const r = await api('/auth/login', { method: 'POST', body: new URLSearchParams({ username: correo, password }) });
  estado.token = r.access_token; estado.usuario = r.usuario;
  localStorage.setItem('token', r.access_token);
  localStorage.setItem('usuario', JSON.stringify(r.usuario));
  $('#auth').close();
  pintarNav();
  toast('Bienvenido, ' + r.usuario.nombre.split(' ')[0]);
  router();
}

function abrirAuth() { $('#auth').showModal(); }
function tabAuth(login) {
  $('#f-login').hidden = !login; $('#f-reg').hidden = login;
  $('#t-login').className = login ? 'on' : ''; $('#t-reg').className = login ? '' : 'on';
}
$('#t-login').onclick = () => tabAuth(true);
$('#t-reg').onclick = () => tabAuth(false);
$('#cerrar-auth').onclick = () => $('#auth').close();
$('#f-login').onsubmit = guard(async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  await iniciarSesion(d.correo, d.password);
});
$('#f-reg').onsubmit = guard(async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  await api('/auth/registro', { method: 'POST', body: d });
  await iniciarSesion(d.correo, d.password);
});

/* ---------- Componentes ---------- */
function matiz(p) {
  let h = 0;
  for (const c of p.genero + p.titulo) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

function poster(p) {
  const h = matiz(p);
  return `<div class="poster" style="background:linear-gradient(160deg,hsl(${h} 55% 40%),hsl(${(h + 60) % 360} 50% 13%))">
    <span class="clasif">${esc(p.clasificacion)}</span>
    <strong>${esc(p.titulo)}</strong>
    <small>${esc(p.genero)} · ${p.duracion_min} min</small></div>`;
}

/* ---------- Vistas de cliente ---------- */
async function vistaCartelera() {
  const [todas, proximas] = await Promise.all([
    api('/peliculas/?estado=en_cartelera'),
    api('/peliculas/?estado=proximamente'),
  ]);
  const generos = [...new Set(todas.map(p => p.genero))].sort();
  const d = todas.length ? todas[new Date().getDate() % todas.length] : null;
  const banner = d ? (() => {
    const h = matiz(d);
    return `<a class="banner" href="#/pelicula/${d.id}" style="background:linear-gradient(110deg,hsl(${h} 55% 32%),hsl(${(h + 60) % 360} 50% 10%))">
      <div><span class="etq">Destacada</span><h1>${esc(d.titulo)}</h1>
      <p>${esc(d.genero)} · ${d.duracion_min} min · Clasificación ${esc(d.clasificacion)}</p>
      <p class="sin">${esc((d.sinopsis || '').slice(0, 160))}</p>
      <span class="btn">Ver funciones</span></div></a>`;
  })() : '';
  vista.innerHTML = `
    ${banner}
    <h2 class="sub">Cartelera</h2>
    <div class="filtros">
      <input id="f-q" placeholder="Buscar por título…">
      <select id="f-g"><option value="">Todos los géneros</option>${generos.map(g => `<option>${esc(g)}</option>`).join('')}</select>
      <select id="f-c"><option value="">Toda clasificación</option>${['TP', '+7', '+12', '+15', '+18'].map(c => `<option>${c}</option>`).join('')}</select>
    </div>
    <div id="grid" class="grid"></div>
    ${proximas.length ? `<h2 class="sub">Próximamente</h2><div class="grid">${proximas.map(p => `<div class="card soon">${poster(p)}</div>`).join('')}</div>` : ''}`;

  const pintar = guard(async () => {
    const q = new URLSearchParams({ estado: 'en_cartelera' });
    if ($('#f-q').value.trim()) q.set('q', $('#f-q').value.trim());
    if ($('#f-g').value) q.set('genero', $('#f-g').value);
    if ($('#f-c').value) q.set('clasificacion', $('#f-c').value);
    const lista = await api('/peliculas/?' + q);
    $('#grid').innerHTML = lista.length
      ? lista.map(p => `<a class="card" href="#/pelicula/${p.id}">${poster(p)}</a>`).join('')
      : '<p class="vacio">No hay películas con esos filtros.</p>';
  });
  let t;
  $('#f-q').oninput = () => { clearTimeout(t); t = setTimeout(pintar, 300); };
  $('#f-g').onchange = pintar; $('#f-c').onchange = pintar;
  pintar();
}

async function vistaPelicula(id) {
  const [p, funs] = await Promise.all([api('/peliculas/' + id), api('/funciones/?pelicula_id=' + id)]);
  const ahora = new Date();
  const porDia = {};
  funs.filter(f => new Date(f.inicio) > ahora).forEach(f => (porDia[f.inicio.slice(0, 10)] ||= []).push(f));
  const dias = Object.keys(porDia).sort();
  vista.innerHTML = `
    <a href="#/" class="sub" style="color:var(--suave)">← Volver a la cartelera</a>
    <div class="detalle">${poster(p)}
      <div><h1>${esc(p.titulo)}</h1>
        <p>${esc(p.genero)} · ${p.duracion_min} min · Clasificación ${esc(p.clasificacion)}</p>
        <p>${esc(p.sinopsis || 'Sin sinopsis disponible.')}</p></div></div>
    <h2>Funciones disponibles</h2>
    ${dias.length ? dias.map(d => `
      <div class="dia">${fecha(d + 'T00:00:00')}</div>
      <div class="funciones">${porDia[d].map(f => `
        <a class="funcion" href="#/funcion/${f.id}"><b>${hora(f.inicio)}</b>
        <span>${esc(f.tipo_sala)} · ${esc(f.sala)}</span>
        <small>${money(f.precio)} · ${f.capacidad - f.ocupados} libres</small></a>`).join('')}</div>`).join('')
      : '<p class="vacio">No hay funciones programadas.</p>'}`;
}

async function vistaFuncion(id) {
  const f = await api('/funciones/' + id);
  const [p, s, mapa] = await Promise.all([
    api('/peliculas/' + f.pelicula_id), api('/salas/' + f.sala_id), api(`/funciones/${id}/asientos`),
  ]);
  const filas = {};
  mapa.asientos.forEach(a => (filas[a.fila] ||= []).push(a));
  const sel = new Set();
  vista.innerHTML = `
    <a href="#/pelicula/${p.id}" class="sub" style="color:var(--suave)">← ${esc(p.titulo)}</a>
    <h1>${esc(p.titulo)}</h1>
    <p style="color:var(--suave)">${fecha(f.inicio)} · ${hora(f.inicio)} · ${esc(s.nombre)} (${esc(s.tipo)}) · ${money(f.precio)} por boleta</p>
    <div class="sala-wrap">
      <div class="pantalla"></div><div class="pantalla-et">PANTALLA</div>
      ${Object.keys(filas).sort().map(fl => `<div class="fila"><span class="et">${fl}</span>${filas[fl].map(a =>
        `<button class="asiento ${a.estado}" data-c="${a.codigo}" title="${a.codigo}" ${a.estado === 'ocupado' ? 'disabled' : ''}>${a.numero}</button>`).join('')}</div>`).join('')}
    </div>
    <div class="leyenda"><span><i style="background:var(--libre)"></i>Libre</span><span><i style="background:var(--acento)"></i>Seleccionado</span><span><i style="background:#4a2630"></i>Ocupado</span></div>
    <div class="resumen"><div id="r-txt">Selecciona hasta 8 asientos</div><button class="btn" id="b-comprar" disabled>Comprar</button></div>`;

  const actualizar = () => {
    const n = sel.size;
    $('#r-txt').innerHTML = n ? `<b>${[...sel].sort().join(', ')}</b> · ${n} boleta(s) · <b>${money(n * f.precio)}</b>` : 'Selecciona hasta 8 asientos';
    $('#b-comprar').disabled = !n;
  };
  vista.querySelectorAll('.asiento:not(.ocupado)').forEach(b => b.onclick = () => {
    const c = b.dataset.c;
    if (sel.has(c)) { sel.delete(c); b.classList.remove('sel'); }
    else if (sel.size >= 8) toast('Máximo 8 asientos por compra', 'error');
    else { sel.add(c); b.classList.add('sel'); }
    actualizar();
  });
    $('#b-comprar').onclick = guard(async () => {
    if (!estado.token) { toast('Inicia sesión para comprar', 'error'); abrirAuth(); return; }
    let compra;
    try {
      compra = await api('/compras/', { method: 'POST', body: { funcion_id: id, asientos: [...sel] } });
    } catch (e) {
      toast(e.message, 'error');
      vistaFuncion(id);
      return;
    }
    toast('¡Compra realizada!');
    mostrarTicket(compra, p, f, s);
  });
}

async function vistaCompras() {
  if (!estado.token) { vista.innerHTML = '<p class="vacio">Inicia sesión para ver tus compras.</p>'; abrirAuth(); return; }
  const lista = await api('/compras/mias');
  vista.innerHTML = `<h1>Mis compras</h1><p style="color:var(--suave)">Puedes cancelar hasta 2 horas antes de la función.</p>` +
    (lista.length ? lista.slice(0, 30).map(c => {
      const puede = c.estado === 'activa' && new Date(c.inicio) - Date.now() > 2 * 3600 * 1000;
      return `<article class="compra ${c.estado}">
        <div><b>${esc(c.pelicula)}</b> <span class="etiqueta ${c.estado}">${c.estado}</span><br>
        <small>${fecha(c.inicio)} · ${hora(c.inicio)} · ${esc(c.sala)} · Asientos: ${c.asientos.join(', ')}</small></div>
        <div><b>${money(c.total)}</b> ${puede ? `<button class="btn ghost small" data-cancelar="${c.id}">Cancelar</button>` : ''}</div></article>`;
    }).join('') : '<p class="vacio">Aún no tienes compras.</p>');
  vista.querySelectorAll('[data-cancelar]').forEach(b => b.onclick = guard(async () => {
    if (!confirm('¿Cancelar esta compra?')) return;
    await api(`/compras/${b.dataset.cancelar}/cancelar`, { method: 'POST' });
    toast('Compra cancelada');
    vistaCompras();
  }));
}

function mostrarTicket(c, p, f, s) {
  const barras = [...c.id].map(ch => `<i style="width:${1 + (parseInt(ch, 16) || 1) % 4}px"></i>`).join('');
  vista.innerHTML = `
    <div class="ticket-wrap">
      <p class="ok-msg">¡Compra confirmada!</p>
      <article class="ticket">
        <small>CINEAPP</small>
        <h2>${esc(p.titulo)}</h2>
        <p>${fecha(f.inicio)} · ${hora(f.inicio)}</p>
        <div class="t-grid">
          <div><small>Sala</small><b>${esc(s.nombre)}</b></div>
          <div><small>Formato</small><b>${esc(s.tipo)}</b></div>
          <div><small>Asientos</small><b>${c.asientos.join(', ')}</b></div>
          <div><small>Total</small><b>${money(c.total)}</b></div>
        </div>
        <div class="t-corte"></div>
        <div class="t-pie"><div class="barras">${barras}</div><small>N.º ${c.id.slice(-8).toUpperCase()}</small></div>
      </article>
      <div class="acciones"><a class="btn" href="#/compras">Ver mis compras</a><a class="btn ghost" href="#/">Volver a la cartelera</a></div>
    </div>`;
}

/* ---------- Administración ---------- */
async function vistaAdmin(tab = 'dashboard') {
  if (!estado.usuario || estado.usuario.rol !== 'admin') {
    vista.innerHTML = '<p class="vacio">Esta sección es solo para administradores.</p>'; return;
  }
  const tabs = { dashboard: adminDashboard, peliculas: adminPeliculas, salas: adminSalas, funciones: adminFunciones };
  if (!tabs[tab]) tab = 'dashboard';
  vista.innerHTML = `<div class="tabs">${Object.keys(tabs).map(t =>
    `<a class="${t === tab ? 'on' : ''}" href="#/admin/${t}">${t[0].toUpperCase() + t.slice(1)}</a>`).join('')}</div><div id="admin"></div>`;
  await tabs[tab]($('#admin'));
}

function grafico(id, tipo, etiquetas, datos, titulo) {
  new Chart($('#' + id), {
    type: tipo,
    data: { labels: etiquetas, datasets: [{
      label: titulo, data: datos,
      backgroundColor: tipo === 'line' ? 'rgba(230,57,70,.2)' : PALETA,
      borderColor: '#e63946', tension: .3, fill: tipo === 'line',
    }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: tipo === 'doughnut' } },
      scales: tipo === 'doughnut' ? {} : { y: { beginAtZero: true, grid: { color: '#2f2f3d' } }, x: { grid: { display: false } } },
    },
  });
}

async function adminDashboard(el) {
  el.innerHTML = '<p class="vacio">Cargando reportes…</p>';
  const [r, top, periodo, genero, dia, ocup, baja, clientes] = await Promise.all([
    api('/reportes/resumen'), api('/reportes/peliculas-top?limite=6'),
    api('/reportes/ventas-por-periodo?agrupar=dia&dias=21'), api('/reportes/ingresos-por-genero'),
    api('/reportes/ventas-por-dia-semana'), api('/reportes/ocupacion-por-sala'),
    api('/reportes/funciones-baja-ocupacion'), api('/reportes/clientes-top?limite=5'),
  ]);
  el.innerHTML = `
    <div class="kpis">
      <div class="kpi"><small>Ingresos</small><b>${money(r.ingresos)}</b></div>
      <div class="kpi"><small>Boletas vendidas</small><b>${r.boletas.toLocaleString('es-CO')}</b></div>
      <div class="kpi"><small>Tasa de cancelación</small><b>${r.tasa_cancelacion_pct}%</b></div>
      <div class="kpi"><small>Funciones futuras</small><b>${r.funciones_futuras}</b></div>
      <div class="kpi"><small>Películas en cartelera</small><b>${r.peliculas_en_cartelera}</b></div>
    </div>
    <div class="charts">
      <div class="chart"><h3>Ingresos por película (top)</h3><div><canvas id="g1"></canvas></div></div>
      <div class="chart"><h3>Ingresos por día (últimos 21 días)</h3><div><canvas id="g2"></canvas></div></div>
      <div class="chart"><h3>Ingresos por género</h3><div><canvas id="g3"></canvas></div></div>
      <div class="chart"><h3>Ingresos por día de la semana</h3><div><canvas id="g4"></canvas></div></div>
      <div class="chart"><h3>Ocupación por sala (%)</h3><div><canvas id="g5"></canvas></div></div>
    </div>
    <h2>Funciones con baja ocupación (para reprogramar)</h2>
    <div class="tabla-wrap"><table><tr><th>Película</th><th>Sala</th><th>Fecha</th><th>Ocupación</th></tr>
      ${baja.length ? baja.map(b => `<tr><td>${esc(b.pelicula)}</td><td>${esc(b.sala)}</td><td>${fecha(b.inicio)} ${hora(b.inicio)}</td><td>${b.ocupados}/${b.capacidad} (${b.ocupacion_pct}%)</td></tr>`).join('') : '<tr><td colspan="4">Sin funciones con baja ocupación.</td></tr>'}</table></div>
    <h2>Mejores clientes</h2>
    <div class="tabla-wrap"><table><tr><th>Cliente</th><th>Compras</th><th>Boletas</th><th>Ticket promedio</th><th>Gasto total</th></tr>
      ${clientes.map(c => `<tr><td>${esc(c.cliente)}</td><td>${c.compras}</td><td>${c.boletas}</td><td>${money(c.ticket_promedio)}</td><td>${money(c.gasto)}</td></tr>`).join('')}</table></div>`;
  Chart.defaults.color = '#9a9aab';
  grafico('g1', 'bar', top.map(x => x.pelicula), top.map(x => x.ingresos), 'Ingresos');
  grafico('g2', 'line', periodo.map(x => x.periodo.slice(5)), periodo.map(x => x.ingresos), 'Ingresos');
  grafico('g3', 'doughnut', genero.map(x => x.genero), genero.map(x => x.ingresos), 'Ingresos');
  grafico('g4', 'bar', dia.map(x => x.dia), dia.map(x => x.ingresos), 'Ingresos');
  grafico('g5', 'bar', ocup.map(x => x.sala), ocup.map(x => x.ocupacion_pct), 'Ocupación %');
}

async function adminPeliculas(el) {
  const lista = await api('/peliculas/');
  const estados = ['en_cartelera', 'proximamente', 'retirada'];
  el.innerHTML = `
    <h2>Nueva película</h2>
    <form id="f-pel" class="form">
      <input name="titulo" placeholder="Título" required>
      <input name="genero" placeholder="Género" required>
      <input name="duracion_min" type="number" min="1" max="400" placeholder="Minutos" required style="width:110px">
      <select name="clasificacion">${['TP', '+7', '+12', '+15', '+18'].map(c => `<option>${c}</option>`).join('')}</select>
      <select name="estado">${estados.map(e => `<option>${e}</option>`).join('')}</select>
      <input name="sinopsis" placeholder="Sinopsis" style="flex:1;min-width:200px">
      <button class="btn">Crear</button>
    </form>
    <div class="tabla-wrap"><table><tr><th>Título</th><th>Género</th><th>Min</th><th>Clasif.</th><th>Estado</th><th></th></tr>
      ${lista.map(p => `<tr><td>${esc(p.titulo)}</td><td>${esc(p.genero)}</td><td>${p.duracion_min}</td><td>${esc(p.clasificacion)}</td>
        <td><select data-estado="${p.id}">${estados.map(e => `<option ${e === p.estado ? 'selected' : ''}>${e}</option>`).join('')}</select></td>
        <td><button class="btn ghost small" data-del="${p.id}">Eliminar</button></td></tr>`).join('')}</table></div>`;
  $('#f-pel').onsubmit = guard(async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    d.duracion_min = Number(d.duracion_min);
    await api('/peliculas/', { method: 'POST', body: d });
    toast('Película creada'); adminPeliculas(el);
  });
  el.querySelectorAll('[data-estado]').forEach(s => s.onchange = guard(async () => {
    await api('/peliculas/' + s.dataset.estado, { method: 'PUT', body: { estado: s.value } });
    toast('Estado actualizado');
  }));
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = guard(async () => {
    if (!confirm('¿Eliminar esta película?')) return;
    await api('/peliculas/' + b.dataset.del, { method: 'DELETE' });
    toast('Película eliminada'); adminPeliculas(el);
  }));
}

async function adminSalas(el) {
  const lista = await api('/salas/');
  el.innerHTML = `
    <h2>Nueva sala</h2>
    <form id="f-sala" class="form">
      <input name="nombre" placeholder="Nombre" required>
      <select name="tipo"><option>2D</option><option>3D</option><option>VIP</option></select>
      <input name="filas" type="number" min="1" max="26" placeholder="Filas" required style="width:100px">
      <input name="columnas" type="number" min="1" max="30" placeholder="Columnas" required style="width:110px">
      <button class="btn">Crear</button>
    </form>
    <div class="tabla-wrap"><table><tr><th>Sala</th><th>Tipo</th><th>Distribución</th><th>Capacidad</th><th></th></tr>
      ${lista.map(s => `<tr><td>${esc(s.nombre)}</td><td>${esc(s.tipo)}</td><td>${s.filas} filas × ${s.columnas} columnas</td><td>${s.capacidad}</td>
        <td><button class="btn ghost small" data-del="${s.id}">Eliminar</button></td></tr>`).join('')}</table></div>`;
  $('#f-sala').onsubmit = guard(async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    d.filas = Number(d.filas); d.columnas = Number(d.columnas);
    await api('/salas/', { method: 'POST', body: d });
    toast('Sala creada'); adminSalas(el);
  });
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = guard(async () => {
    if (!confirm('¿Eliminar esta sala?')) return;
    await api('/salas/' + b.dataset.del, { method: 'DELETE' });
    toast('Sala eliminada'); adminSalas(el);
  }));
}

async function adminFunciones(el, dia = hoyLocal()) {
  const [pelis, salas, funs] = await Promise.all([api('/peliculas/'), api('/salas/'), api('/funciones/?fecha=' + dia)]);
  el.innerHTML = `
    <h2>Programar función</h2>
    <form id="f-fun" class="form">
      <select name="pelicula_id">${pelis.filter(p => p.estado !== 'retirada').map(p => `<option value="${p.id}">${esc(p.titulo)}</option>`).join('')}</select>
      <select name="sala_id">${salas.map(s => `<option value="${s.id}">${esc(s.nombre)} (${esc(s.tipo)})</option>`).join('')}</select>
      <input name="inicio" type="datetime-local" required>
      <input name="precio" type="number" min="1000" step="500" placeholder="Precio" required style="width:120px">
      <button class="btn">Programar</button>
    </form>
    <div class="filtros"><label class="campo">Ver funciones del día<input type="date" id="f-dia" value="${dia}"></label></div>
    <div class="tabla-wrap"><table><tr><th>Hora</th><th>Película</th><th>Sala</th><th>Precio</th><th>Ocupación</th><th></th></tr>
      ${funs.length ? funs.map(f => `<tr><td>${hora(f.inicio)} – ${hora(f.fin)}</td><td>${esc(f.pelicula)}</td><td>${esc(f.sala)}</td><td>${money(f.precio)}</td><td>${f.ocupados}/${f.capacidad}</td>
        <td><button class="btn ghost small" data-del="${f.id}">Eliminar</button></td></tr>`).join('') : '<tr><td colspan="6">No hay funciones ese día.</td></tr>'}</table></div>`;
  $('#f-dia').onchange = e => adminFunciones(el, e.target.value || hoyLocal());
  $('#f-fun').onsubmit = guard(async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    d.precio = Number(d.precio); d.inicio = d.inicio + ':00';
    await api('/funciones/', { method: 'POST', body: d });
    toast('Función programada'); adminFunciones(el, d.inicio.slice(0, 10));
  });
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = guard(async () => {
    if (!confirm('¿Eliminar esta función?')) return;
    await api('/funciones/' + b.dataset.del, { method: 'DELETE' });
    toast('Función eliminada'); adminFunciones(el, dia);
  }));
}

/* ---------- Router ---------- */
function esqueleto() {
  return '<div class="grid">' + '<div class="sk"></div>'.repeat(8) + '</div>';
}

async function router() {
  const [, ruta, id] = location.hash.split('/');
  window.scrollTo(0, 0);
  vista.innerHTML = esqueleto();
  try {
    if (ruta === 'pelicula') await vistaPelicula(id);
    else if (ruta === 'funcion') await vistaFuncion(id);
    else if (ruta === 'compras') await vistaCompras();
    else if (ruta === 'admin') await vistaAdmin(id);
    else await vistaCartelera();
  } catch (e) {
    vista.innerHTML = `<p class="vacio">${esc(e.message)}</p>`;
  }
}

window.addEventListener('hashchange', router);
pintarNav();
router();