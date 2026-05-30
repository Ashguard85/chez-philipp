const http     = require('http');
const fs       = require('fs');
const path     = require('path');
const Database = require('better-sqlite3');

const PORT      = process.env.PORT      || 3201;
const ADMIN_PIN = process.env.ADMIN_PIN || '1234';
const DATA_DIR  = process.env.DATA_DIR  || '/data';

fs.mkdirSync(DATA_DIR, { recursive: true });

const db = new Database(path.join(DATA_DIR, 'bookings.db'));
db.exec(`
  CREATE TABLE IF NOT EXISTS bookings (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    service TEXT NOT NULL,
    date    TEXT NOT NULL,
    time    TEXT NOT NULL,
    notes   TEXT DEFAULT '',
    price   TEXT DEFAULT '',
    created TEXT DEFAULT (datetime('now','localtime'))
  )
`);

const SCHEDULE_FILE = path.join(DATA_DIR, 'schedule.json');
const SERVICES_FILE = path.join(DATA_DIR, 'services.json');

const DEFAULT_SCHEDULE = {
  0: { open: false, slots: [] },
  1: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  2: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  3: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  4: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  5: { open: true, slots: ['09:00','10:00','11:00','13:00','14:00','15:00','16:00','17:00'] },
  6: { open: false, slots: [] }
};

const DEFAULT_SERVICES = [
  { id:1, icon:'🤲', name:'Nur Hände',              desc:'Pflege & Behandlung beider Hände',          details:'Wir kümmern uns liebevoll um deine Hände: feilen, pflegen, lackieren.',                        price:'1 Küsschen', duration:'45 Min.' },
  { id:2, icon:'🦶', name:'Nur Füsse',               desc:'Pflege & Behandlung beider Füsse',          details:'Entspannung pur für deine Füsse: einweichen, feilen, pflegen, lackieren.',                    price:'1 Küsschen', duration:'45 Min.' },
  { id:3, icon:'🤲', name:'Hände mit Fussmassage',   desc:'Handpflege plus entspannende Fussmassage',  details:'Das Beste aus beiden Welten: gepflegte Hände und eine wohltuende Fussmassage.',               price:'1 Küsschen', duration:'75 Min.' },
  { id:4, icon:'✨', name:'Hände und Füsse',         desc:'Das volle Programm',                        details:'Komplettpaket für Hände und Füsse – du lehnst dich zurück, wir machen den Rest.',             price:'1 Küsschen', duration:'90 Min.' },
  { id:5, icon:'💆', name:'Nur Fussmassage',         desc:'Tiefenentspannung für müde Füsse',          details:'Eine verwöhnende Massage die deine Füsse nach einem langen Tag wieder zum Leben erweckt.',     price:'1 Küsschen', duration:'30 Min.' },
  { id:6, icon:'😍', name:'Ich massiere deine Füsse',desc:'Philipp himself – persönlich & mit Liebe',  details:'Philipp himself nimmt sich Zeit nur für dich. Die exklusivste Behandlung im ganzen Angebot.', price:'1 Küsschen', duration:'60 Min.' }
];

function readJSON(f, def) { try { return JSON.parse(fs.readFileSync(f,'utf8')); } catch { return def; } }
function writeJSON(f, d)  { fs.writeFileSync(f, JSON.stringify(d,null,2), 'utf8'); }
function getBody(req)     { return new Promise((ok,err) => { let d=''; req.on('data',c=>d+=c); req.on('end',()=>{ try{ok(JSON.parse(d))}catch(e){err(e)} }); }); }

function reply(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Admin-Pin',
  });
  res.end(body);
}

function isAdmin(req, res) {
  if (req.headers['x-admin-pin'] !== ADMIN_PIN) { reply(res, 401, {error:'Falscher PIN'}); return false; }
  return true;
}

http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x');
  const p = u.pathname;

  if (req.method === 'OPTIONS') { reply(res, 204, {}); return; }

  // Health check
  if (p === '/health') { reply(res, 200, {ok:true}); return; }

  // Services
  if (p === '/services' && req.method === 'GET') { reply(res, 200, readJSON(SERVICES_FILE, DEFAULT_SERVICES)); return; }
  if (p === '/services' && req.method === 'PUT') {
    if (!isAdmin(req,res)) return;
    writeJSON(SERVICES_FILE, await getBody(req));
    reply(res, 200, {ok:true}); return;
  }

  // Schedule
  if (p === '/schedule' && req.method === 'GET') { reply(res, 200, readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE)); return; }
  if (p === '/schedule' && req.method === 'PUT') {
    if (!isAdmin(req,res)) return;
    writeJSON(SCHEDULE_FILE, await getBody(req));
    reply(res, 200, {ok:true}); return;
  }

  // Slots (free slots for date)
  if (p === '/slots' && req.method === 'GET') {
    const date = u.searchParams.get('date');
    if (!date) { reply(res, 400, {error:'date required'}); return; }
    const sched = readJSON(SCHEDULE_FILE, DEFAULT_SCHEDULE);
    const dow   = new Date(date).getDay();
    const day   = sched[dow] || {open:false, slots:[]};
    if (!day.open) { reply(res, 200, {open:false, slots:[]}); return; }
    const booked = db.prepare('SELECT time FROM bookings WHERE date=?').all(date).map(r=>r.time);
    reply(res, 200, {open:true, slots: day.slots.filter(t=>!booked.includes(t))}); return;
  }

  // Bookings - create
  if (p === '/bookings' && req.method === 'POST') {
    const b = await getBody(req);
    if (!b.name||!b.service||!b.date||!b.time) { reply(res,400,{error:'Missing fields'}); return; }
    const r = db.prepare('INSERT INTO bookings (name,service,date,time,notes,price) VALUES (?,?,?,?,?,?)').run(b.name,b.service,b.date,b.time,b.notes||'',b.price||'');
    reply(res, 201, {ok:true, id:r.lastInsertRowid}); return;
  }

  // Bookings - list (admin)
  if (p === '/bookings' && req.method === 'GET') {
    if (!isAdmin(req,res)) return;
    reply(res, 200, db.prepare('SELECT * FROM bookings ORDER BY date DESC,time DESC').all()); return;
  }

  // Bookings - delete (admin)
  if (p.startsWith('/bookings/') && req.method === 'DELETE') {
    if (!isAdmin(req,res)) return;
    db.prepare('DELETE FROM bookings WHERE id=?').run(parseInt(p.split('/')[2]));
    reply(res, 200, {ok:true}); return;
  }

  // My bookings by name
  if (p === '/mybookings' && req.method === 'GET') {
    const name = u.searchParams.get('name');
    if (!name) { reply(res,400,{error:'name required'}); return; }
    reply(res, 200, db.prepare('SELECT * FROM bookings WHERE LOWER(name)=LOWER(?) ORDER BY date DESC').all(name)); return;
  }

  reply(res, 404, {error:'Not found'});

}).listen(PORT, '0.0.0.0', () => console.log(`✅ Chez Philipp API running on port ${PORT}`));
