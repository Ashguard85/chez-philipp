const http     = require('http');
const fs       = require('fs');
const path     = require('path');
const Database = require('better-sqlite3');

const PORT      = process.env.PORT      || 3201;
const ADMIN_PIN = process.env.ADMIN_PIN || '1234';
const DATA_DIR  = process.env.DATA_DIR  || '/data';

const SCHEDULE_FILE = path.join(DATA_DIR, 'schedule.json');
const SERVICES_FILE = path.join(DATA_DIR, 'services.json');
const DB_FILE       = path.join(DATA_DIR, 'bookings.db');

// ── SQLITE ──
fs.mkdirSync(DATA_DIR, { recursive: true });
const db = new Database(DB_FILE);
db.exec(`
  CREATE TABLE IF NOT EXISTS bookings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    service   TEXT NOT NULL,
    date      TEXT NOT NULL,
    time      TEXT NOT NULL,
    notes     TEXT,
    price     TEXT,
    created   TEXT DEFAULT (datetime('now'))
  )
`);

// ── DEFAULTS ──
const DEFAULT_SCHEDULE = {
  0: { open: false, slots: [] },
  1: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  2: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  3: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  4: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  5: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  6: { open: false, slots: [] },
};

const DEFAULT_SERVICES = [
  { id: 1, icon: '🤲', name: 'Nur Hände',              desc: 'Pflege & Behandlung beider Hände',         details: 'Wir kümmern uns liebevoll um deine Hände: feilen, pflegen, lackieren.',                        price: '1 Küsschen', duration: '45 Min.' },
  { id: 2, icon: '🦶', name: 'Nur Füsse',               desc: 'Pflege & Behandlung beider Füsse',         details: 'Entspannung pur für deine Füsse: einweichen, feilen, pflegen, lackieren.',                    price: '1 Küsschen', duration: '45 Min.' },
  { id: 3, icon: '🤲', name: 'Hände mit Fussmassage',   desc: 'Handpflege plus entspannende Fussmassage', details: 'Das Beste aus beiden Welten: gepflegte Hände und eine wohltuende Fussmassage.',               price: '1 Küsschen', duration: '75 Min.' },
  { id: 4, icon: '✨', name: 'Hände und Füsse',         desc: 'Das volle Programm',                       details: 'Komplettpaket für Hände und Füsse — du lehnst dich zurück, wir machen den Rest.',             price: '1 Küsschen', duration: '90 Min.' },
  { id: 5, icon: '💆', name: 'Nur Fussmassage',         desc: 'Tiefenentspannung für müde Füsse',         details: 'Eine verwöhnende Massage die deine Füsse nach einem langen Tag wieder zum Leben erweckt.',     price: '1 Küsschen', duration: '30 Min.' },
  { id: 6, icon: '😍', name: 'Ich massiere deine Füsse', desc: 'Philipp himself – persönlich & mit Liebe', details: 'Philipp himself nimmt sich Zeit nur für dich. Die exklusivste Behandlung im ganzen Angebot.', price: '1 Küsschen', duration: '60 Min.' },
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
function bodyJSON(req) {
  return new Promise((res, rej) => {
    let d = '';
    req.on('data', c => d += c);
    req.on('end', () => { try { res(JSON.parse(d)); } catch { rej(new Error('Invalid JSON')); } });
  });
}
function send(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, PUT, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Pin',
  });
  res.end(JSON.stringify(data));
}
function authAdmin(req, res) {
  if (req.headers['x-admin-pin'] !== ADMIN_PIN) {
    send(res, 401, { error: 'Falscher PIN' }); return false;
  }
  return true;
}

// ── ROUTER ──
http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const p   = url.pathname;

  if (req.method === 'OPTIONS') { send(res, 204, {}); return; }

  // ── SERVICES ──
  if (req.method === 'GET'  && p === '/services') { send(res, 200, readJSON(SERVICES_FILE, DEFAULT_SERVICES)); return; }
  if (req.method === 'PUT'  && p === '/services') {
    if (!authAdmin(req, res)) return;
    writeJSON(SERVICES_FILE, await bodyJSON(req));
    send(res, 200, { ok: true }); return;
  }

  // ── SCHEDULE ──
  if (req.method === 'GET'  && p === '/schedule') { send(res, 200, readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE)); return; }
  if (req.method === 'PUT'  && p === '/schedule') {
    if (!authAdmin(req, res)) return;
    writeJSON(SCHEDULE_FILE, await bodyJSON(req));
    send(res, 200, { ok: true }); return;
  }

  // ── SLOTS (free slots for a date, minus already booked) ──
  if (req.method === 'GET' && p === '/slots') {
    const dateStr = url.searchParams.get('date');
    if (!dateStr) { send(res, 400, { error: 'date required' }); return; }
    const schedule = readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE);
    const dow = new Date(dateStr).getDay();
    const day = schedule[dow] || { open: false, slots: [] };
    if (!day.open) { send(res, 200, { open: false, slots: [] }); return; }
    const booked = db.prepare('SELECT time FROM bookings WHERE date = ?').all(dateStr).map(r => r.time);
    const free   = day.slots.filter(t => !booked.includes(t));
    send(res, 200, { open: true, slots: free, booked }); return;
  }

  // ── BOOKINGS: create ──
  if (req.method === 'POST' && p === '/bookings') {
    try {
      const b = await bodyJSON(req);
      if (!b.name || !b.service || !b.date || !b.time) { send(res, 400, { error: 'Missing fields' }); return; }
      const result = db.prepare(
        'INSERT INTO bookings (name, service, date, time, notes, price) VALUES (?,?,?,?,?,?)'
      ).run(b.name, b.service, b.date, b.time, b.notes || '', b.price || '');
      send(res, 201, { ok: true, id: result.lastInsertRowid }); return;
    } catch (e) { send(res, 400, { error: e.message }); return; }
  }

  // ── BOOKINGS: list all (admin) ──
  if (req.method === 'GET' && p === '/bookings') {
    if (!authAdmin(req, res)) return;
    const rows = db.prepare('SELECT * FROM bookings ORDER BY date DESC, time DESC').all();
    send(res, 200, rows); return;
  }

  // ── BOOKINGS: delete (admin) ──
  if (req.method === 'DELETE' && p.startsWith('/bookings/')) {
    if (!authAdmin(req, res)) return;
    const id = parseInt(p.split('/')[2]);
    db.prepare('DELETE FROM bookings WHERE id = ?').run(id);
    send(res, 200, { ok: true }); return;
  }

  // ── BOOKINGS: by name (for customer view) ──
  if (req.method === 'GET' && p === '/mybookings') {
    const name = url.searchParams.get('name');
    if (!name) { send(res, 400, { error: 'name required' }); return; }
    const rows = db.prepare('SELECT * FROM bookings WHERE LOWER(name) = LOWER(?) ORDER BY date DESC').all(name);
    send(res, 200, rows); return;
  }

  send(res, 404, { error: 'Not found' });

}).listen(PORT, () => console.log(`Chez Philipp API :${PORT}`));
