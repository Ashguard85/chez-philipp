const http = require('http');
const fs   = require('fs');
const path = require('path');

const PORT      = process.env.PORT || 3201;
const ADMIN_PIN = process.env.ADMIN_PIN || '1234';
const DATA_DIR  = process.env.DATA_DIR || '/data';

const SCHEDULE_FILE = path.join(DATA_DIR, 'schedule.json');
const SERVICES_FILE = path.join(DATA_DIR, 'services.json');

// ── DEFAULTS ──
const DEFAULT_SCHEDULE = {
  0: { open: false, slots: [] },
  1: { open: true,  slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  2: { open: true,  slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  3: { open: true,  slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  4: { open: true,  slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  5: { open: true,  slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  6: { open: false, slots: [] },
};

const DEFAULT_SERVICES = [
  { id: 1, icon: '🤲', name: 'Nur Hände',             desc: 'Pflege & Behandlung beider Hände',          price: '1 Küsschen', duration: '45 Min.' },
  { id: 2, icon: '🦶', name: 'Nur Füsse',              desc: 'Pflege & Behandlung beider Füsse',          price: '1 Küsschen', duration: '45 Min.' },
  { id: 3, icon: '🤲', name: 'Hände mit Fussmassage',  desc: 'Handpflege plus entspannende Fussmassage',  price: '1 Küsschen', duration: '75 Min.' },
  { id: 4, icon: '✨', name: 'Hände und Füsse',        desc: 'Das volle Programm für Hände & Füsse',      price: '1 Küsschen', duration: '90 Min.' },
  { id: 5, icon: '💆', name: 'Nur Fussmassage',        desc: 'Tiefenentspannung pur für müde Füsse',      price: '1 Küsschen', duration: '30 Min.' },
  { id: 6, icon: '😍', name: 'Ich massiere deine Füsse', desc: 'Philipp himself – persönlich & mit Liebe', price: '1 Küsschen', duration: '60 Min.' },
];

// ── HELPERS ──
function readJSON(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return fallback; }
}

function writeJSON(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf8');
}

function body(req) {
  return new Promise((res, rej) => {
    let d = '';
    req.on('data', c => d += c);
    req.on('end', () => { try { res(JSON.parse(d)); } catch { rej(new Error('Invalid JSON')); } });
  });
}

function send(res, status, data) {
  const json = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, PUT, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Pin',
  });
  res.end(json);
}

function authAdmin(req, res) {
  const pin = req.headers['x-admin-pin'];
  if (pin !== ADMIN_PIN) { send(res, 401, { error: 'Falscher PIN' }); return false; }
  return true;
}

// ── ROUTER ──
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost`);

  // CORS preflight
  if (req.method === 'OPTIONS') { send(res, 204, {}); return; }

  // GET /api/services
  if (req.method === 'GET' && url.pathname === '/services') {
    send(res, 200, readJSON(SERVICES_FILE, DEFAULT_SERVICES));
    return;
  }

  // PUT /api/services  (admin)
  if (req.method === 'PUT' && url.pathname === '/services') {
    if (!authAdmin(req, res)) return;
    try {
      const data = await body(req);
      writeJSON(SERVICES_FILE, data);
      send(res, 200, { ok: true });
    } catch (e) { send(res, 400, { error: e.message }); }
    return;
  }

  // GET /api/schedule
  if (req.method === 'GET' && url.pathname === '/schedule') {
    send(res, 200, readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE));
    return;
  }

  // PUT /api/schedule  (admin)
  if (req.method === 'PUT' && url.pathname === '/schedule') {
    if (!authAdmin(req, res)) return;
    try {
      const data = await body(req);
      writeJSON(SCHEDULE_FILE, data);
      send(res, 200, { ok: true });
    } catch (e) { send(res, 400, { error: e.message }); }
    return;
  }

  // GET /api/slots?date=YYYY-MM-DD
  if (req.method === 'GET' && url.pathname === '/slots') {
    const dateStr = url.searchParams.get('date');
    if (!dateStr) { send(res, 400, { error: 'date param required' }); return; }
    const schedule = readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE);
    const dow = new Date(dateStr).getDay();
    const day = schedule[dow] || { open: false, slots: [] };
    send(res, 200, { open: day.open, slots: day.open ? day.slots : [] });
    return;
  }

  send(res, 404, { error: 'Not found' });
});

server.listen(PORT, () => console.log(`Chez Philipp API running on :${PORT}`));
