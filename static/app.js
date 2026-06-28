/* ============================================================================
 * CampusRadar — capa de presentación (cliente).
 *
 * Responsabilidad única: orquestar la interacción del usuario con la API REST.
 * No contiene reglas de negocio (viven en el backend/dominio); aquí solo se
 * consumen endpoints, se cachea el estado de la vista y se renderiza el DOM.
 * ========================================================================== */

"use strict";

/* ----------------------------- Estado global ----------------------------- */
const state = {
  token: localStorage.getItem("cr_token") || null,
  me: null,            // perfil del usuario autenticado (GET /api/auth/me)
  reportes: [],        // último feed cargado
  vista: "feed",       // feed | mis | mapa | usuarios | moderacion
  filtroTipo: "",
  filtroEstado: "",
  filtroTag: "",
  orden: "relevancia",
  q: "",
};

// Coordenadas aproximadas de cada edificio del campus Beauchef.
const EDIFICIOS = {
  "Hall Sur":           [-33.458069, -70.663432],
  "Biblioteca":         [-33.457467, -70.663448],
  "Edificio Civil":     [-33.457325, -70.661887],
  "Casino Central":     [-33.456716, -70.663708],
  "Edificio Electrica": [-33.458047, -70.661970],
};

// Etiqueta legible para cada estado interno (el backend usa "Critico" sin tilde).
const ESTADO_LABEL = {
  Nuevo: "Nuevo", Verificado: "Verificado", Controvertido: "Controvertido",
  Critico: "Crítico", Expirado: "Expirado", Archivado: "Archivado",
};
const TIPO_ICONO = {
  Infraestructura: "🏗️", Emergencia: "🚨", Evento: "🎉",
  Logistica: "🍕", Actividad: "⚡",
};

// Objetos Leaflet (se crean perezosamente la primera vez que se necesitan).
let pickerMap = null, pickerMarker = null;
let fullMap = null, fullLayer = null;
let comentReporteId = null;
let searchTimer = null;

/* ------------------------------ Utilidades ------------------------------- */
function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
function hace(fechaIso) {
  const diff = (Date.now() - new Date(fechaIso).getTime()) / 60000; // minutos
  if (diff < 1) return "ahora";
  if (diff < 60) return `hace ${Math.floor(diff)} min`;
  if (diff < 1440) return `hace ${Math.floor(diff / 60)} h`;
  return `hace ${Math.floor(diff / 1440)} d`;
}

/* ------------------------- Cliente HTTP genérico -------------------------- */
async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 401) {            // token vencido o ausente
    logout();
    throw new Error("Sesión expirada. Vuelve a ingresar.");
  }
  let data = null;
  const texto = await res.text();
  if (texto) { try { data = JSON.parse(texto); } catch { data = texto; } }
  if (!res.ok) {
    const detalle = (data && data.detail) ? data.detail : `Error ${res.status}`;
    throw new Error(detalle);
  }
  return data;
}

/* -------------------------------- Toasts --------------------------------- */
let toastTimer = null;
function showToast(titulo, cuerpo) {
  el("toast-title").textContent = titulo;
  el("toast-body").textContent = cuerpo;
  const t = el("toast");
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 4000);
}

/* ============================ AUTENTICACIÓN ============================== */
function setAuthTab(modo) {
  const esRegistro = modo === "register";
  el("tab-login").classList.toggle("active", !esRegistro);
  el("tab-register").classList.toggle("active", esRegistro);
  el("register-fields").style.display = esRegistro ? "block" : "none";
  el("auth-submit").textContent = esRegistro ? "Crear cuenta" : "Ingresar";
  el("auth-error").textContent = "";
}

async function submitAuth() {
  const esRegistro = el("tab-register").classList.contains("active");
  const email = el("a-email").value.trim();
  const password = el("a-password").value;
  el("auth-error").textContent = "";

  try {
    let resp;
    if (esRegistro) {
      resp = await api("/api/auth/register", {
        method: "POST",
        body: {
          nombre: el("a-nombre").value.trim(),
          apellido: el("a-apellido").value.trim(),
          carrera: el("a-carrera").value.trim(),
          email, password,
        },
      });
    } else {
      // El backend expone login como OAuth2 password flow (username = email).
      resp = await api("/api/auth/login", {
        method: "POST",
        form: { username: email, password },
      });
    }
    state.token = resp.access_token;
    localStorage.setItem("cr_token", state.token);
    await iniciarApp();
  } catch (e) {
    el("auth-error").textContent = e.message;
  }
}

function logout() {
  state.token = null;
  state.me = null;
  localStorage.removeItem("cr_token");
  el("auth-screen").classList.remove("hidden");
  el("notif-panel").classList.add("hidden");
}

/* ============================ ARRANQUE DE APP ============================ */
async function iniciarApp() {
  try {
    state.me = await api("/api/auth/me");
  } catch {
    logout();
    return;
  }
  el("auth-screen").classList.add("hidden");
  pintarPerfil();

  // Los moderadores y administradores ven la pestaña de moderación.
  const esMod = state.me.rol === "moderador" || state.me.rol === "administrador";
  el("nav-moderacion").style.display = esMod ? "flex" : "none";

  await Promise.all([cargarFeed(), actualizarStats(), cargarComunidad(), cargarNotifs()]);
}

function pintarPerfil() {
  const m = state.me;
  const iniciales = (m.nombre[0] || "") + (m.apellido[0] || "");
  el("my-avatar").textContent = iniciales.toUpperCase();
  el("my-name").textContent = m.nombre;
  el("my-rep").textContent = `REP: ${m.reputacion}`;
  el("my-name-2").textContent = `${m.nombre} ${m.apellido}`;
  el("my-level-badge").textContent = `– ${m.nivel}`;
  // Barra de reputación: 0–100 (se satura visualmente en el nivel Verificado).
  const pct = Math.min(100, (m.reputacion / 100) * 100);
  el("rep-bar").style.width = `${pct}%`;
}

/* =============================== FEED ================================== */
function construirQuery() {
  const p = new URLSearchParams();
  if (state.filtroTipo) p.set("tipo", state.filtroTipo);
  if (state.filtroEstado) p.set("estado", state.filtroEstado);
  if (state.filtroTag) p.set("tag", state.filtroTag);
  if (state.q) p.set("q", state.q);
  if (state.vista === "mis") p.set("mios", "true");
  p.set("orden", state.orden);
  return p.toString();
}

async function cargarFeed() {
  try {
    state.reportes = await api(`/api/reportes?${construirQuery()}`);
  } catch (e) {
    showToast("Error", e.message);
    return;
  }
  if (state.vista === "mapa") renderMapaCompleto();
  else renderFeed();
}

function renderFeed() {
  const cont = el("feed-content");
  if (!state.reportes.length) {
    let msg = "No hay reportes que coincidan con los filtros.";
    if (state.vista === "mis") msg = "Aún no has publicado reportes.";
    cont.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div>${msg}</div>`;
    return;
  }
  let banner = "";
  if (state.filtroTag) {
    banner = `<div class="report-card" style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
      <span>Filtrando por <b style="color:var(--accent)">#${esc(state.filtroTag)}</b></span>
      <span>
        <button class="action-btn" onclick="seguirTag('${esc(state.filtroTag)}')">🔔 Seguir tag</button>
        <button class="action-btn" onclick="limpiarTag()">✕ Quitar filtro</button>
      </span></div>`;
  }
  cont.innerHTML = banner + state.reportes.map(renderCard).join("");
}

function renderCard(r) {
  const estado = r.estado;
  const label = ESTADO_LABEL[estado] || estado;
  const terminal = (estado === "Expirado" || estado === "Archivado");
  const tags = r.tags.map((t) =>
    `<span class="tag" onclick="filterByTag('${esc(t)}')">#${esc(t)}</span>`).join("");

  // Acciones sociales (deshabilitadas si el reporte ya no está activo).
  let acciones = "";
  if (!terminal) {
    acciones = `
      <button class="action-btn confirmar" onclick="confirmarReporte(${r.id})">✓ Confirmar (${r.total_confirmaciones})</button>
      <button class="action-btn desmentir" onclick="desmentirReporte(${r.id})">✕ Desmentir (${r.total_desmentidos})</button>
      <button class="action-btn" onclick="abrirComentarios(${r.id})">💬 ${r.total_comentarios}</button>
      <button class="action-btn" onclick="denunciarReporte(${r.id})">🚩 Denunciar</button>`;
  } else {
    acciones = `<span class="ubicacion-info">Reporte ${label.toLowerCase()} — sin interacciones</span>`;
  }

  // Acciones de moderación (solo visibles para moderador/administrador).
  let mod = "";
  if (state.me && (state.me.rol === "moderador" || state.me.rol === "administrador") && !terminal) {
    mod = `<button class="action-btn" onclick="archivarReporte(${r.id})">🗄️ Archivar</button>`;
  }

  return `
  <div class="report-card ${esc(estado)}">
    <div class="card-header">
      <div>
        <div class="card-type">${TIPO_ICONO[r.tipo] || ""} ${esc(r.tipo)}</div>
        <div class="card-title">${esc(r.titulo)}</div>
      </div>
      <span class="estado-badge estado-${esc(estado)}">${esc(label)}</span>
    </div>
    <div class="card-desc">${esc(r.descripcion)}</div>
    <div class="card-tags">${tags}</div>
    <div class="protocolo">${esc(r.protocolo)}</div>
    <div class="card-meta">
      <span class="ubicacion-info">📍 ${esc(r.ubicacion.edificio)} · Piso ${r.ubicacion.piso}</span>
      <span>👤 ${esc(r.autor.nombre)} (${esc(r.autor.nivel)})</span>
      <span>🕑 ${hace(r.fecha_creacion)}</span>
      <span>⭐ ${r.relevancia}</span>
    </div>
    <div class="card-actions">${acciones}${mod}</div>
  </div>`;
}

/* --------------------------- Filtros y búsqueda -------------------------- */
function filterType(elem, tipo) {
  document.querySelectorAll("#type-filters .filter-chip")
    .forEach((c) => c.classList.remove("active"));
  elem.classList.add("active");
  state.filtroTipo = tipo;
  cargarFeed();
}

function filterState(elem, estado) {
  document.querySelectorAll("#state-filters .filter-chip")
    .forEach((c) => c.classList.remove("active"));
  elem.classList.add("active");
  state.filtroEstado = estado;
  cargarFeed();
}

function setOrden(valor) { state.orden = valor; cargarFeed(); }

function searchReports(valor) {
  state.q = valor.trim();
  clearTimeout(searchTimer);
  searchTimer = setTimeout(cargarFeed, 250); // debounce
}

function filterByTag(tag) {
  state.filtroTag = tag;
  if (state.vista !== "feed" && state.vista !== "mis") setView("feed");
  else cargarFeed();
}
function limpiarTag() { state.filtroTag = ""; cargarFeed(); }

async function seguirTag(tag) {
  try {
    const r = await api("/api/suscripciones", { method: "POST", body: { nombre_tag: tag } });
    showToast("Suscripción", r.detail);
  } catch (e) { showToast("Error", e.message); }
}

/* ============================ NAVEGACIÓN ============================== */
function setView(vista) {
  state.vista = vista;
  document.querySelectorAll(".nav-item").forEach((n) =>
    n.classList.toggle("active", n.dataset.view === vista));

  const feed = el("feed-content");
  const mapa = el("map-full");
  const moder = el("moderacion-content");
  feed.style.display = "none"; mapa.style.display = "none"; moder.style.display = "none";

  if (vista === "moderacion") {
    moder.style.display = "block";
    cargarModeracion();
  } else if (vista === "mapa") {
    mapa.style.display = "block";
    cargarFeed();          // recarga y dibuja el mapa
  } else if (vista === "usuarios") {
    feed.style.display = "block";
    renderComunidadFeed();
  } else {                 // feed | mis
    feed.style.display = "block";
    if (vista === "feed") state.filtroTag = "";
    cargarFeed();
  }
}

/* =============================== MAPA ================================== */
function renderMapaCompleto() {
  if (!fullMap) {
    fullMap = L.map("map-full").setView(CAMPUS_CENTRO, 17);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap", maxZoom: 19,
    }).addTo(fullMap);
  }
  if (fullLayer) fullLayer.clearLayers();
  fullLayer = L.layerGroup().addTo(fullMap);

  state.reportes.forEach((r) => {
    function colorPiso(piso) {
  if (piso < 0) return "#000000";      // subterráneo
  if (piso === 1) return "#3b82f6";   // azul
  if (piso === 2) return "#22c55e";   // verde
  if (piso === 3) return "#f97316";   // naranjo
  return "#ef4444";                   // rojo
}

const m = L.circleMarker(
  [r.ubicacion.lat, r.ubicacion.lon],
  {
    radius: 10,
    color: colorPiso(r.ubicacion.piso),
    fillColor: colorPiso(r.ubicacion.piso),
    fillOpacity: 0.9,
    weight: 2
  }
).addTo(fullLayer);
    m.bindPopup(
      `<b>${esc(r.titulo)}</b><br>${TIPO_ICONO[r.tipo] || ""} ${esc(r.tipo)} · ${esc(ESTADO_LABEL[r.estado] || r.estado)}` +
      `<br>📍 ${esc(r.ubicacion.edificio)} (Piso ${r.ubicacion.piso})`
    );
  });
  // El contenedor estaba oculto al crearse: recalcular dimensiones.
  setTimeout(() => fullMap.invalidateSize(), 300);
}

/* ============================ COMUNIDAD =============================== */
async function cargarComunidad() {
  let usuarios;
  try { usuarios = await api("/api/usuarios"); } catch { return; }
  state._comunidad = usuarios;
  const panel = el("user-list-panel");
  panel.innerHTML = usuarios.slice(0, 6).map((u) => `
    <div class="user-row">
      <div class="avatar" style="width:20px;height:20px;font-size:9px;">${esc((u.nombre[0] || "") + (u.apellido[0] || ""))}</div>
      <span class="user-name">${esc(u.nombre)} ${esc(u.apellido)}</span>
      <span class="user-level">${esc(u.nivel)} · ${u.reputacion}</span>
    </div>`).join("");
  if (state.vista === "usuarios") renderComunidadFeed();
}

function renderComunidadFeed() {
  const usuarios = state._comunidad || [];
  el("feed-content").innerHTML = `
    <div class="report-card"><div class="card-title" style="margin-bottom:12px;">👥 Comunidad CampusRadar</div>
    ${usuarios.map((u) => `
      <div class="user-row">
        <div class="avatar" style="width:28px;height:28px;">${esc((u.nombre[0] || "") + (u.apellido[0] || ""))}</div>
        <span class="user-name">${esc(u.nombre)} ${esc(u.apellido)} <span style="color:var(--muted);font-size:11px;">(${esc(u.rol)})</span></span>
        <span class="user-level">${esc(u.nivel)} · REP ${u.reputacion}</span>
      </div>`).join("")}
    </div>`;
}

/* ============================== STATS ================================= */
async function actualizarStats() {
  let s;
  try { s = await api("/api/stats"); } catch { return; }
  el("stat-total").textContent = s.reportes_activos;
  el("stat-verified").textContent = s.verificados;
  el("stat-critical").textContent = s.criticos;
  el("stat-users").textContent = s.usuarios;
}

/* =========================== NOTIFICACIONES =========================== */
async function cargarNotifs() {
  let notifs;
  try { notifs = await api("/api/notificaciones"); } catch { return; }
  state._notifs = notifs;
  const noLeidas = notifs.filter((n) => !n.leido).length;
  el("notif-count").textContent = noLeidas;
  el("notif-count").style.display = noLeidas ? "flex" : "none";

  const panel = el("notif-panel");
  if (!notifs.length) {
    panel.innerHTML = `<div class="empty-state" style="padding:20px;">Sin notificaciones</div>`;
    return;
  }
  panel.innerHTML = notifs.map((n) => `
    <div class="notif-item ${n.leido ? "" : "unread"}" onclick="leerNotif(${n.id})">
      ${esc(n.mensaje)}
      <div style="color:var(--muted);font-size:10px;margin-top:2px;">${hace(n.fecha_creacion)}</div>
    </div>`).join("");
}

function toggleNotifs() {
  const panel = el("notif-panel");
  panel.classList.toggle("hidden");
  if (!panel.classList.contains("hidden")) cargarNotifs();
}

async function leerNotif(id) {
  try { await api(`/api/notificaciones/${id}/leer`, { method: "POST" }); } catch {}
  cargarNotifs();
}

/* ====================== INTERACCIONES SOCIALES ======================== */
async function accionReporte(id, ruta, exito) {
  try {
    await api(`/api/reportes/${id}/${ruta}`, { method: "POST" });
    showToast("Listo", exito);
    await refrescarTrasAccion();
  } catch (e) { showToast("No se pudo", e.message); }
}
function confirmarReporte(id) { accionReporte(id, "confirmar", "Confirmación registrada."); }
function desmentirReporte(id) { accionReporte(id, "desmentir", "Desmentido registrado."); }

async function denunciarReporte(id) {
  const razon = prompt("¿Por qué denuncias este reporte?");
  if (!razon) return;
  try {
    const r = await api(`/api/reportes/${id}/denunciar`, { method: "POST", body: { razon } });
    showToast("Denuncia enviada", r.detail);
  } catch (e) { showToast("No se pudo", e.message); }
}

async function archivarReporte(id) {
  try {
    await api(`/api/reportes/${id}/archivar`, { method: "POST" });
    showToast("Moderación", "Reporte archivado.");
    await refrescarTrasAccion();
  } catch (e) { showToast("No se pudo", e.message); }
}

async function refrescarTrasAccion() {
  // Tras una acción, mi reputación y las métricas pueden haber cambiado.
  try { state.me = await api("/api/auth/me"); pintarPerfil(); } catch {}
  await Promise.all([cargarFeed(), actualizarStats(), cargarComunidad()]);
}

/* ----------------------------- Comentarios ------------------------------ */
async function abrirComentarios(id) {
  comentReporteId = id;
  el("modal-coment").classList.remove("hidden");
  el("coment-input").value = "";
  el("coment-list").innerHTML = `<div class="empty-state" style="padding:20px;">Cargando…</div>`;
  try {
    const cs = await api(`/api/reportes/${id}/comentarios`);
    el("coment-list").innerHTML = cs.length
      ? cs.map((c) => `
          <div style="padding:8px 0;border-bottom:1px solid var(--border);">
            <div style="font-size:13px;">${esc(c.contenido)}</div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">
              ${esc(c.autor.nombre)} ${esc(c.autor.apellido)} · ${hace(c.fecha_creacion)}</div>
          </div>`).join("")
      : `<div class="empty-state" style="padding:20px;">Aún no hay comentarios.</div>`;
  } catch (e) {
    el("coment-list").innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
  }
}
function closeComent() { el("modal-coment").classList.add("hidden"); comentReporteId = null; }

async function submitComent() {
  const contenido = el("coment-input").value.trim();
  if (!contenido) return;
  try {
    await api(`/api/reportes/${comentReporteId}/comentarios`,
      { method: "POST", body: { contenido } });
    await abrirComentarios(comentReporteId); // recarga la lista
    await refrescarTrasAccion();
  } catch (e) { showToast("No se pudo", e.message); }
}

/* ====================== MODAL: NUEVO REPORTE ========================== */
function openModal() {
  el("modal").classList.remove("hidden");
  ["f-titulo", "f-desc", "f-tags"].forEach((i) => (el(i).value = ""));
  setTimeout(initPicker, 60); // el contenedor debe estar visible
}
function closeModal() { el("modal").classList.add("hidden"); }

function initPicker() {
  const edificio = el("f-edificio").value;
  const coords = EDIFICIOS[edificio] || CAMPUS_CENTRO;
  if (!pickerMap) {
    pickerMap = L.map("map-picker").setView(coords, 17);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap", maxZoom: 19,
    }).addTo(pickerMap);
    pickerMarker = L.marker(coords, { draggable: true }).addTo(pickerMap);
  } else {
    pickerMap.setView(coords, 17);
    pickerMarker.setLatLng(coords);
  }
  setTimeout(() => pickerMap.invalidateSize(), 50);
}

function moveMarkerToBuilding() {
  if (!pickerMap) return;
  const coords = EDIFICIOS[el("f-edificio").value] || CAMPUS_CENTRO;
  pickerMap.setView(coords, 17);
  pickerMarker.setLatLng(coords);
}

async function submitReport() {
  const titulo = el("f-titulo").value.trim();
  const descripcion = el("f-desc").value.trim();
  if (!titulo || !descripcion) {
    showToast("Faltan datos", "Título y descripción son obligatorios.");
    return;
  }
  const pos = pickerMarker ? pickerMarker.getLatLng() : { lat: CAMPUS_CENTRO[0], lng: CAMPUS_CENTRO[1] };
  const tags = el("f-tags").value.split(",").map((t) => t.trim()).filter(Boolean);

  const body = {
    titulo, descripcion,
    tipo: el("f-tipo").value,
    ubicacion: {
      edificio: el("f-edificio").value,
      piso: parseInt(el("f-piso").value, 10),
      lat: pos.lat, lon: pos.lng,
    },
    tags,
  };
  try {
    await api("/api/reportes", { method: "POST", body });
    closeModal();
    showToast("Reporte publicado", "Tu reporte ya está en el feed.");
    state.vista = "feed";
    setView("feed");
    await refrescarTrasAccion();
  } catch (e) { showToast("No se pudo publicar", e.message); }
}

/* ============================ MODERACIÓN ============================== */
async function cargarModeracion() {
  const cont = el("moderacion-content");
  cont.innerHTML = `<div class="empty-state" style="padding:20px;">Cargando denuncias…</div>`;
  let denuncias;
  try {
    denuncias = await api("/api/moderacion/denuncias?solo_pendientes=true");
  } catch (e) {
    cont.innerHTML = `<div class="empty-state">${esc(e.message)}</div>`;
    return;
  }
  if (!denuncias.length) {
    cont.innerHTML = `<div class="empty-state"><div class="empty-icon">🛡️</div>No hay denuncias pendientes.</div>`;
    return;
  }
  cont.innerHTML = `<div class="feed-title" style="margin-bottom:14px;">🛡️ Denuncias pendientes</div>` +
    denuncias.map((d) => `
      <div class="report-card">
        <div class="card-header">
          <div><div class="card-type">Reporte #${d.reporte_id}</div>
          <div class="card-title">Razón: ${esc(d.razon)}</div></div>
          <span class="estado-badge estado-Controvertido">${esc(d.estado)}</span>
        </div>
        <div class="card-meta"><span>👤 ${esc(d.denunciante.nombre)} ${esc(d.denunciante.apellido)}</span>
          <span>🕑 ${hace(d.fecha_creacion)}</span></div>
        <div class="card-actions">
          <button class="action-btn desmentir" onclick="resolverDenuncia(${d.id}, 'Aceptada')">✓ Aceptar (archiva reporte)</button>
          <button class="action-btn" onclick="resolverDenuncia(${d.id}, 'Rechazada')">✕ Rechazar denuncia</button>
        </div>
      </div>`).join("");
}

async function resolverDenuncia(id, estado) {
  try {
    await api(`/api/moderacion/denuncias/${id}/resolver`,
      { method: "POST", body: { estado } });
    showToast("Moderación", `Denuncia ${estado.toLowerCase()}.`);
    await cargarModeracion();
    await Promise.all([cargarFeed(), actualizarStats()]);
  } catch (e) { showToast("No se pudo", e.message); }
}

/* ============================== ARRANQUE ============================== */
// Permite enviar formularios de auth con la tecla Enter.
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !el("auth-screen").classList.contains("hidden")) submitAuth();
});
// Cierra el panel de notificaciones al hacer click fuera de él.
document.addEventListener("click", (ev) => {
  const panel = el("notif-panel"), bell = el("notif-bell");
  if (panel && !panel.classList.contains("hidden") &&
      !panel.contains(ev.target) && !bell.contains(ev.target)) {
    panel.classList.add("hidden");
  }
});

// Si hay token guardado, intenta restaurar la sesión automáticamente.
if (state.token) {
  iniciarApp().catch(() => logout());
} else {
  el("auth-screen").classList.remove("hidden");
}
