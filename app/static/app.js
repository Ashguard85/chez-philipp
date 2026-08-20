'use strict';

const CFG = window.APP_CONFIG || { deployment: 'pages', appName: 'Chez Philipp', version: '4.0.0', defaultApiBase: '', dockerFallbackUrl: '' };
const APP_VERSION = CFG.version || '4.0.0';
const MODE_KEY = 'chez-philipp-mode';
const VIEW_KEY = 'chez-philipp-view';
const DB_NAME = 'chez-philipp-pwa';
const DB_VERSION = 3;
const WEEKDAYS = ['Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag','Sonntag'];
const MONTHS = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'];

const DEFAULT_SERVICES = [
  {id:'hands',name:'Signature Manicure',short_description:'Präzise Hand- und Nagelpflege',description:'Form, Pflege und ein makelloses Finish – ruhig, sorgfältig und auf deine Wünsche abgestimmt.',price_label:'1 Küsschen',duration_min:45,icon:'H',color_enabled:1,active:1,sort_order:10},
  {id:'feet',name:'Signature Pedicure',short_description:'Entspannende Pflege für deine Füsse',description:'Ein gepflegtes, entspanntes Finish mit Zeit für Details und einer angenehm ruhigen Behandlung.',price_label:'1 Küsschen',duration_min:45,icon:'F',color_enabled:1,active:1,sort_order:20},
  {id:'hands-foot-massage',name:'Manicure & Foot Ritual',short_description:'Handpflege mit Fussmassage',description:'Signature Manicure kombiniert mit einer wohltuenden Fussmassage – für ein besonders entspanntes Erlebnis.',price_label:'1 Küsschen',duration_min:75,icon:'HF',color_enabled:1,active:1,sort_order:30},
  {id:'hands-feet',name:'Full Care Ritual',short_description:'Komplettpflege für Hände und Füsse',description:'Das vollständige Pflegeprogramm mit ausreichend Zeit für Hände, Füsse und ein hochwertiges Finish.',price_label:'1 Küsschen',duration_min:90,icon:'FC',color_enabled:1,active:1,sort_order:40},
  {id:'foot-massage',name:'Foot Massage',short_description:'Entspannung für müde Füsse',description:'Eine fokussierte, wohltuende Massage für eine bewusste Pause und spürbare Entspannung.',price_label:'1 Küsschen',duration_min:30,icon:'FM',color_enabled:0,active:1,sort_order:50},
  {id:'philipp-exclusive',name:"Philipp's Private Ritual",short_description:'Die persönliche Signature-Behandlung',description:'Die exklusive Behandlung mit Philipp – individuell, persönlich und mit besonderer Aufmerksamkeit.',price_label:'1 Küsschen',duration_min:60,icon:'P',color_enabled:0,active:1,sort_order:60}
];

const DEFAULT_NAIL_COLORS = [
  {id:'nude',name:'Nude',hex_color:'#D8B7A6',active:1,sort_order:10},
  {id:'blush',name:'Blush',hex_color:'#E6B8B4',active:1,sort_order:20},
  {id:'rose',name:'Rosé',hex_color:'#C88F95',active:1,sort_order:30},
  {id:'red',name:'Classic Red',hex_color:'#A8323D',active:1,sort_order:40},
  {id:'bordeaux',name:'Bordeaux',hex_color:'#6D2431',active:1,sort_order:50},
  {id:'taupe',name:'Taupe',hex_color:'#8C786D',active:1,sort_order:60},
  {id:'milky-white',name:'Milky White',hex_color:'#F2EEE6',active:1,sort_order:70},
  {id:'black',name:'Black',hex_color:'#292524',active:1,sort_order:80},
  {id:'french',name:'French',hex_color:'#E8D7CB',active:1,sort_order:90},
  {id:'decide-later',name:'Vor Ort entscheiden',hex_color:'#B9B2AA',active:1,sort_order:100}
];
const DEFAULT_HOURS = [
  {weekday:0,enabled:1,start_time:'09:00',end_time:'18:00',slot_interval_min:30},
  {weekday:1,enabled:1,start_time:'09:00',end_time:'18:00',slot_interval_min:30},
  {weekday:2,enabled:1,start_time:'09:00',end_time:'18:00',slot_interval_min:30},
  {weekday:3,enabled:1,start_time:'09:00',end_time:'18:00',slot_interval_min:30},
  {weekday:4,enabled:1,start_time:'09:00',end_time:'18:00',slot_interval_min:30},
  {weekday:5,enabled:0,start_time:'09:00',end_time:'16:00',slot_interval_min:30},
  {weekday:6,enabled:0,start_time:'09:00',end_time:'16:00',slot_interval_min:30}
];

const state = {
  mode: null,
  provider: null,
  services: [],
  colors: [],
  selectedService: null,
  selectedColor: null,
  bookingIntent: null,
  selectedDate: null,
  selectedTime: null,
  availabilityDays: {},
  latestBooking: null,
  serverConfig: null,
  adminState: null,
  pendingImport: null,
  updateRegistration: null,
  updateWaiting: null,
  dirty: false
};

const $ = (id) => document.getElementById(id);
const qsa = (selector, root=document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const uid = () => crypto.randomUUID ? crypto.randomUUID() : `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const nowIso = () => new Date().toISOString();
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
function colorSwatchData(value) {
  const hex = /^#[0-9a-f]{6}$/i.test(String(value || '')) ? String(value).toUpperCase() : '#B9B2AA';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><rect width="40" height="40" rx="20" fill="${hex}"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function showToast(message, type='ok') {
  const toast = $('toast');
  toast.textContent = message;
  toast.classList.toggle('error', type === 'error');
  toast.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove('show'), 2800);
}

function setConnectivity(message='') {
  const el = $('connectivity-banner');
  if (!message) {
    el.classList.add('hidden');
    el.textContent = '';
    return;
  }
  el.textContent = message;
  el.classList.remove('hidden');
}

function normalizeUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '');
}

function validateExternalHttps(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('device')) db.createObjectStore('device', { keyPath: 'key' });
      if (!db.objectStoreNames.contains('services')) db.createObjectStore('services', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('colors')) db.createObjectStore('colors', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('hours')) db.createObjectStore('hours', { keyPath: 'weekday' });
      if (!db.objectStoreNames.contains('overrides')) db.createObjectStore('overrides', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('bookings')) {
        const store = db.createObjectStore('bookings', { keyPath: 'id' });
        store.createIndex('public_code', 'public_code', { unique: true });
        store.createIndex('date', 'date', { unique: false });
      }
      if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(storeName, key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

async function idbGetAll(storeName) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
    tx.oncomplete = () => db.close();
  });
}

async function idbPut(storeName, value) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).put(value);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function idbDelete(storeName, key) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).delete(key);
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function idbReplaceStore(storeName, records) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    store.clear();
    records.forEach(record => store.put(record));
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function idbBulkPut(storeName, records) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    records.forEach(record => store.put(record));
    tx.oncomplete = () => { db.close(); resolve(); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

async function getDeviceSetting(key, fallback=null) {
  const row = await idbGet('device', key);
  return row ? row.value : fallback;
}

async function setDeviceSetting(key, value) {
  await idbPut('device', { key, value });
}

async function ensureLocalSeed() {
  const marker = await idbGet('meta', 'seeded');
  const versionRow = await idbGet('meta', 'schema_version');
  const stamp = nowIso();
  if (!marker) {
    await idbBulkPut('services', DEFAULT_SERVICES.map(x => ({...x, created_at: stamp, updated_at: stamp})));
    await idbBulkPut('colors', DEFAULT_NAIL_COLORS.map(x => ({...x, created_at: stamp, updated_at: stamp})));
    await idbBulkPut('hours', DEFAULT_HOURS);
    await idbPut('meta', {key:'seeded', value:true});
    await idbPut('meta', {key:'schema_version', value:3});
    return;
  }
  if (Number(versionRow?.value || 1) < 2) {
    const services = await idbGetAll('services');
    await idbBulkPut('services', services.map(item => ({
      ...item,
      color_enabled: item.color_enabled === undefined ? (['hands','feet','hands-foot-massage','hands-feet'].includes(item.id) ? 1 : 0) : Number(item.color_enabled),
      updated_at: item.updated_at || stamp
    })));
    if (!(await idbGetAll('colors')).length) {
      await idbBulkPut('colors', DEFAULT_NAIL_COLORS.map(x => ({...x, created_at: stamp, updated_at: stamp})));
    }
    await idbPut('meta', {key:'schema_version', value:2});
  }
  if (Number((await idbGet('meta', 'schema_version'))?.value || 1) < 3) {
    await idbPut('meta', {key:'schema_version', value:3});
  }
}

function minutes(value) {
  const [h,m] = String(value).split(':').map(Number);
  return h * 60 + m;
}
function timeFromMinutes(value) {
  return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
}
function localDateString(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}
function parseLocalDate(value) {
  const [y,m,d] = value.split('-').map(Number);
  return new Date(y, m-1, d, 12, 0, 0);
}
function weekdayMondayZero(value) {
  const native = parseLocalDate(value).getDay();
  return (native + 6) % 7;
}
function endTime(start, duration) { return timeFromMinutes(minutes(start) + Number(duration)); }

class LocalProvider {
  constructor() { this.kind = 'local'; }
  async init() { await ensureLocalSeed(); }
  async getConfig() { return {title:CFG.appName || 'Chez Philipp',version:APP_VERSION,auth_enabled:false,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,booking_notification_enabled:false}; }
  async getServices() {
    return (await idbGetAll('services')).filter(x => Number(x.active) === 1).sort((a,b) => Number(a.sort_order)-Number(b.sort_order) || a.name.localeCompare(b.name));
  }
  async getColors() {
    return (await idbGetAll('colors')).filter(x => Number(x.active) === 1).sort((a,b) => Number(a.sort_order)-Number(b.sort_order) || a.name.localeCompare(b.name));
  }
  async getAvailability(date, serviceId) {
    const service = await idbGet('services', serviceId);
    if (!service || !Number(service.active)) return [];
    const day = parseLocalDate(date);
    const today = new Date();
    if (day < new Date(today.getFullYear(), today.getMonth(), today.getDate())) return [];
    const hours = await idbGet('hours', weekdayMondayZero(date));
    const overrides = (await idbGetAll('overrides')).filter(x => x.date === date);
    let windows = [];
    let step = Number(hours?.slot_interval_min || 30);
    if (overrides.length) {
      if (overrides.some(x => x.kind === 'closed')) return [];
      windows = overrides.filter(x => x.kind === 'available').map(x => [minutes(x.start_time), minutes(x.end_time)]);
    } else if (hours && Number(hours.enabled)) {
      windows = [[minutes(hours.start_time), minutes(hours.end_time)]];
    } else {
      return [];
    }
    const bookings = (await idbGetAll('bookings')).filter(b => b.date === date && b.status === 'confirmed');
    const busy = bookings.map(b => [minutes(b.start_time), minutes(b.end_time)]);
    const result = [];
    const duration = Number(service.duration_min);
    for (const [open, close] of windows) {
      let cursor = open;
      while (cursor + duration <= close) {
        const finish = cursor + duration;
        const overlap = busy.some(([s,e]) => cursor < e && finish > s);
        const pastToday = date === localDateString(today) && cursor <= today.getHours()*60 + today.getMinutes();
        if (!overlap && !pastToday) result.push(timeFromMinutes(cursor));
        cursor += Math.max(5, step);
      }
    }
    return [...new Set(result)].sort();
  }
  async getAvailabilityDays(serviceId, days=28) {
    const result=[];
    const today=new Date();
    for (let i=0;i<days;i++) {
      const d=new Date(today.getFullYear(),today.getMonth(),today.getDate()+i,12);
      const value=localDateString(d);
      const slots=await this.getAvailability(value,serviceId);
      result.push({date:value,count:slots.length});
    }
    return result;
  }
  async createBooking(data) {
    const service = await idbGet('services', data.service_id);
    if (!service) throw new Error('Leistung nicht gefunden');
    let color = null;
    if (Number(service.color_enabled)) {
      if (!data.nail_color_id) throw new Error('Bitte eine Farbe auswählen.');
      color = await idbGet('colors', data.nail_color_id);
      if (!color || !Number(color.active)) throw new Error('Farbe nicht gefunden.');
    }
    const mode = data.booking_mode === 'requested' ? 'requested' : 'confirmed';
    const start = minutes(data.start_time);
    const end = start + Number(service.duration_min);
    const today = new Date();
    const selectedDay = parseLocalDate(data.date);
    if (selectedDay < new Date(today.getFullYear(), today.getMonth(), today.getDate()) || (data.date === localDateString(today) && start <= today.getHours()*60 + today.getMinutes())) throw new Error('Der gewünschte Termin liegt in der Vergangenheit.');
    const confirmed = (await idbGetAll('bookings')).filter(b => b.date === data.date && b.status === 'confirmed');
    if (confirmed.some(b => start < minutes(b.end_time) && end > minutes(b.start_time))) throw new Error('Zu dieser Zeit besteht bereits ein bestätigter Termin.');
    if (mode === 'confirmed') {
      const free = await this.getAvailability(data.date, data.service_id);
      if (!free.includes(data.start_time)) throw new Error('Dieser Termin ist nicht mehr verfügbar.');
    }
    const code = `CP-${Math.random().toString(36).slice(2,10).toUpperCase().replace(/[IO01]/g,'X').padEnd(8,'7').slice(0,8)}`;
    const stamp = nowIso();
    const row = {
      id: uid(), public_code: code, customer_name: 'Meine Frau', customer_email: '', customer_phone: '',
      service_id: service.id, service_name: service.name, price_label: service.price_label || '',
      nail_color_id: color?.id || '', nail_color_name: color?.name || '', nail_color_hex: color?.hex_color || '',
      date: data.date, start_time: data.start_time, end_time: endTime(data.start_time, service.duration_min), notes: data.notes || '',
      status:mode, created_at:stamp, updated_at:stamp
    };
    await idbPut('bookings', row);
    return row;
  }
  async getBookingByCode(code) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('bookings','readonly');
      const req = tx.objectStore('bookings').index('public_code').get(String(code).trim().toUpperCase());
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error);
      tx.oncomplete = () => db.close();
    });
  }
  async getMyBookings() { return (await idbGetAll('bookings')).sort((a,b) => `${b.date}${b.start_time}`.localeCompare(`${a.date}${a.start_time}`)); }
  async getAdminState() {
    return {
      services:(await idbGetAll('services')).sort((a,b)=>Number(a.sort_order)-Number(b.sort_order)),
      nail_colors:(await idbGetAll('colors')).sort((a,b)=>Number(a.sort_order)-Number(b.sort_order)),
      opening_hours:(await idbGetAll('hours')).sort((a,b)=>a.weekday-b.weekday),
      availability_overrides:(await idbGetAll('overrides')).sort((a,b)=>`${a.date}${a.start_time}`.localeCompare(`${b.date}${b.start_time}`)),
      bookings:await this.getMyBookings(), notification_enabled:false
    };
  }
  async saveServices(items) {
    const stamp = nowIso();
    await idbBulkPut('services', items.map((item,index) => ({...item,id:item.id || uid(),duration_min:Number(item.duration_min)||30,color_enabled:item.color_enabled?1:0,active:item.active?1:0,sort_order:Number(item.sort_order ?? index*10),created_at:item.created_at || stamp,updated_at:stamp})));
  }
  async saveNailColors(items) {
    const stamp = nowIso();
    await idbBulkPut('colors', items.map((item,index) => ({...item,id:item.id || uid(),hex_color:item.hex_color || '#B9B2AA',active:item.active?1:0,sort_order:Number(item.sort_order ?? index*10),created_at:item.created_at || stamp,updated_at:stamp})));
  }
  async saveOpeningHours(items) { await idbReplaceStore('hours', items.map(x => ({...x,enabled:x.enabled?1:0,slot_interval_min:Number(x.slot_interval_min)||30}))); }
  async saveAvailabilityOverrides(items) { const stamp=nowIso(); await idbReplaceStore('overrides', items.map(x=>({...x,id:x.id||uid(),created_at:x.created_at||stamp,updated_at:stamp}))); }
  async confirmBooking(id) { const row=await idbGet('bookings',id); if(!row||row.status!=='requested') throw new Error('Terminanfrage nicht gefunden.'); const busy=(await idbGetAll('bookings')).filter(b=>b.id!==id&&b.date===row.date&&b.status==='confirmed'); if(busy.some(b=>minutes(row.start_time)<minutes(b.end_time)&&minutes(row.end_time)>minutes(b.start_time))) throw new Error('Der Zeitraum ist inzwischen belegt.'); await idbPut('bookings',{...row,status:'confirmed',updated_at:nowIso()}); }
  async rejectBooking(id) { const row=await idbGet('bookings',id); if(row&&row.status==='requested') await idbPut('bookings',{...row,status:'rejected',updated_at:nowIso()}); }
  async cancelBooking(id) {
    const row = await idbGet('bookings', id);
    if (!row) return;
    await idbPut('bookings', {...row,status:'cancelled',updated_at:nowIso()});
  }
  async exportBackup() {
    return {format:'chez-philipp-backup',version:3,exported_at:nowIso(),data:{services:await idbGetAll('services'),nail_colors:await idbGetAll('colors'),opening_hours:await idbGetAll('hours'),availability_overrides:await idbGetAll('overrides'),bookings:await idbGetAll('bookings'),meta:{}}};
  }
  async previewBackup(payload) { return validateBackupClient(payload); }
  async applyBackup(payload, strategy='replace') {
    const counts = validateBackupClient(payload);
    const safety = await this.exportBackup();
    await downloadJson(safety, `chez-philipp-local-before-restore-${localDateString(new Date())}.json`, false);
    const normalizedServices = (payload.data.services || []).map(item => ({...item,color_enabled:item.color_enabled === undefined ? (['hands','feet','hands-foot-massage','hands-feet'].includes(item.id) ? 1 : 0) : Number(item.color_enabled)}));
    if (strategy === 'replace') {
      await idbReplaceStore('bookings', payload.data.bookings || []);
      await idbReplaceStore('hours', payload.data.opening_hours || []);
      await idbReplaceStore('overrides', Number(payload.version)>=3 ? (payload.data.availability_overrides || []) : []);
      await idbReplaceStore('services', normalizedServices);
      if (Number(payload.version) >= 2) await idbReplaceStore('colors', payload.data.nail_colors || []);
    } else {
      await idbBulkPut('services', normalizedServices);
      if (Number(payload.version) >= 2) await idbBulkPut('colors', payload.data.nail_colors || []);
      await idbBulkPut('hours', payload.data.opening_hours || []);
      if (Number(payload.version)>=3) await idbBulkPut('overrides', payload.data.availability_overrides || []);
      await idbBulkPut('bookings', payload.data.bookings || []);
    }
    return counts;
  }
}

class ServerProvider {
  constructor(serverConfig) { this.kind = 'server'; this.serverConfig = serverConfig || {}; this.serverMeta = null; }
  apiUrl(path) {
    const base = CFG.deployment === 'docker' ? '' : normalizeUrl(this.serverConfig.backendUrl || CFG.defaultApiBase || '');
    return `${base}/api${path}`;
  }
  headers(admin=false) {
    const headers = {'Content-Type':'application/json'};
    if (this.serverConfig.cfClientId) headers['CF-Access-Client-Id'] = this.serverConfig.cfClientId;
    if (this.serverConfig.cfClientSecret) headers['CF-Access-Client-Secret'] = this.serverConfig.cfClientSecret;
    if (admin) {
      const pin = sessionStorage.getItem('chez-philipp-admin-pin');
      if (pin) headers['X-Admin-Pin'] = pin;
    }
    return headers;
  }
  async request(path, options={}) {
    const admin = Boolean(options.admin);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), options.timeout || 9000);
    try {
      const response = await fetch(this.apiUrl(path), {
        method: options.method || 'GET',
        headers: this.headers(admin),
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
        cache: 'no-store',
        credentials: 'omit'
      });
      if (!response.ok) {
        let detail = '';
        try { detail = (await response.json()).error || ''; } catch { detail = await response.text(); }
        const error = new Error(detail || `HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      if (response.status === 204) return null;
      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) throw new Error('Unerwartete Serverantwort. Cloudflare Access, Backend-URL und API-Freigabe prüfen.');
      return response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Timeout beim Serverzugriff');
      if (error instanceof TypeError && /fetch/i.test(error.message)) throw new Error('Server nicht erreichbar oder Anfrage durch Netzwerk/CORS blockiert');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async init() { this.serverMeta = await this.getConfig(); }
  async getConfig() { return this.request('/config'); }
  async getServices() { return this.request('/services'); }
  async getColors() { return this.request('/nail-colors'); }
  async getAvailability(date, serviceId) { return (await this.request(`/availability?date=${encodeURIComponent(date)}&service_id=${encodeURIComponent(serviceId)}`)).slots || []; }
  async getAvailabilityDays(serviceId,days=28) { return (await this.request(`/availability-days?service_id=${encodeURIComponent(serviceId)}&days=${Number(days)||28}`)).days || []; }
  async createBooking(data) {
    const row = await this.request('/bookings',{method:'POST',body:data});
    const codes = await getDeviceSetting('bookingCodes', []);
    if (!codes.includes(row.public_code)) await setDeviceSetting('bookingCodes', [row.public_code, ...codes].slice(0,100));
    return row;
  }
  async getBookingByCode(code) { try { return await this.request(`/bookings/by-code/${encodeURIComponent(String(code).trim().toUpperCase())}`); } catch (e) { if (e.status===404) return null; throw e; } }
  async getMyBookings() {
    const codes = await getDeviceSetting('bookingCodes', []);
    const results = [];
    for (const code of codes.slice(0,40)) {
      try { const row = await this.getBookingByCode(code); if (row) results.push(row); } catch (e) { if (!results.length) throw e; }
    }
    return results.sort((a,b) => `${b.date}${b.start_time}`.localeCompare(`${a.date}${a.start_time}`));
  }
  async getAdminState() { return this.request('/admin/state',{admin:true}); }
  async saveServices(items) { return this.request('/admin/services',{method:'PUT',body:items,admin:true}); }
  async saveNailColors(items) { return this.request('/admin/nail-colors',{method:'PUT',body:items,admin:true}); }
  async saveOpeningHours(items) { return this.request('/admin/opening-hours',{method:'PUT',body:items,admin:true}); }
  async saveAvailabilityOverrides(items) { return this.request('/admin/availability-overrides',{method:'PUT',body:items,admin:true}); }
  async confirmBooking(id) { return this.request(`/admin/bookings/${encodeURIComponent(id)}/confirm`,{method:'POST',admin:true}); }
  async rejectBooking(id) { return this.request(`/admin/bookings/${encodeURIComponent(id)}/reject`,{method:'POST',admin:true}); }
  async cancelBooking(id) { return this.request(`/admin/bookings/${encodeURIComponent(id)}`,{method:'DELETE',admin:true}); }
  async exportBackup() { return this.request('/admin/export',{admin:true}); }
  async previewBackup(payload) { return this.request('/admin/import/preview',{method:'POST',body:payload,admin:true}); }
  async applyBackup(payload,strategy='replace') { return this.request(`/admin/import/apply?strategy=${encodeURIComponent(strategy)}`,{method:'POST',body:payload,admin:true,timeout:20000}); }
  async createServerBackup() { return this.request('/admin/backup',{admin:true}); }
  async retryNotification(id) { return this.request(`/admin/notifications/${encodeURIComponent(id)}/retry`,{method:'POST',admin:true,timeout:20000}); }
}

function validateBackupClient(payload) {
  if (!payload || payload.format !== 'chez-philipp-backup') throw new Error('Unbekanntes Backup-Format');
  if (![1,2,3].includes(Number(payload.version))) throw new Error('Nicht unterstützte Backup-Version');
  if (!payload.data || !Array.isArray(payload.data.services) || !Array.isArray(payload.data.opening_hours) || !Array.isArray(payload.data.bookings)) throw new Error('Backup-Daten sind unvollständig');
  if (Number(payload.version) >= 2 && !Array.isArray(payload.data.nail_colors)) throw new Error('Backup enthält keine gültige Farbliste');
  if (Number(payload.version) >= 3 && !Array.isArray(payload.data.availability_overrides)) throw new Error('Backup enthält keine gültigen Verfügbarkeitsausnahmen');
  return {version:Number(payload.version),services:payload.data.services.length,nail_colors:(payload.data.nail_colors || []).length,opening_hours:payload.data.opening_hours.length,availability_overrides:(payload.data.availability_overrides || []).length,bookings:payload.data.bookings.length};
}

async function configureProvider() {
  if (CFG.deployment === 'docker') {
    state.mode = 'server';
    localStorage.setItem(MODE_KEY,'server');
    state.serverConfig = {backendUrl:'',cfClientId:'',cfClientSecret:'',dockerFallbackUrl:''};
    state.provider = new ServerProvider(state.serverConfig);
    try { await state.provider.init(); setConnectivity(''); } catch (e) { setConnectivity(`Server nicht erreichbar: ${e.message}`); }
    return;
  }
  state.mode = localStorage.getItem(MODE_KEY);
  state.serverConfig = await getDeviceSetting('serverConfig', null);
  if (!['local','server'].includes(state.mode)) return;
  if (state.mode === 'local') {
    state.provider = new LocalProvider();
    await state.provider.init();
  } else {
    state.provider = new ServerProvider(state.serverConfig || {});
    try { await state.provider.init(); setConnectivity(''); } catch (e) { setConnectivity(`Server nicht erreichbar. Die lokal gecachte App-Oberfläche läuft weiter. ${e.message}`); }
  }
}

function refreshModeUi() {
  const local = state.mode === 'local';
  $('mode-pill').textContent = local ? 'Lokal' : 'Server';
  $('settings-mode-title').textContent = local ? 'Lokal' : 'Server';
  $('settings-mode-description').textContent = local
    ? 'Alle fachlichen Daten liegen ausschließlich in IndexedDB auf diesem Gerät. Es gibt keine automatische Synchronisation und lokale Buchungen können keine E-Mail-Benachrichtigung an Philipp auslösen.'
    : 'Die fachlichen Daten liegen auf dem Docker-Backend. Diese PWA ist nur der Client; lokale und Serverdaten werden nicht automatisch vermischt.';
  $('local-data-warning').classList.toggle('hidden', !local);
  $('server-settings-card').classList.toggle('hidden', CFG.deployment === 'docker');
  $('change-mode').classList.toggle('hidden', CFG.deployment === 'docker');
  $('version-chip').textContent = `v${APP_VERSION}`;
  const fallback = state.serverConfig?.dockerFallbackUrl || CFG.dockerFallbackUrl || '';
  $('docker-fallback-card').classList.toggle('hidden', !fallback || CFG.deployment === 'docker');
  renderServerSummary();
}

function renderServerSummary() {
  const cfg = state.serverConfig || {};
  const configured = CFG.deployment === 'docker' || Boolean(cfg.backendUrl);
  $('server-summary').textContent = CFG.deployment === 'docker'
    ? 'Docker-Frontend nutzt das Backend derselben Origin.'
    : configured
      ? `${cfg.backendUrl} · Cloudflare Service Auth ${cfg.cfClientId && cfg.cfClientSecret ? 'konfiguriert' : 'nicht gesetzt'}. Das Secret wird hier absichtlich nicht angezeigt.`
      : 'Noch nicht konfiguriert.';
  $('server-status-dot').classList.toggle('ok', configured && state.mode === 'server');
}

function goView(name) {
  if (!['book','appointments','more','admin'].includes(name)) name = 'book';
  qsa('.view').forEach(el => el.classList.toggle('active', el.dataset.view === name));
  qsa('.nav-button').forEach(el => el.classList.toggle('active', el.dataset.nav === name));
  if (name !== 'admin') localStorage.setItem(VIEW_KEY, name);
  if (name === 'appointments') loadAppointments();
  if (name === 'more') refreshModeUi();
  window.scrollTo({top:0,behavior:'instant'});
}

function renderServices() {
  const grid = $('service-grid');
  if (!state.services.length) {
    grid.innerHTML = '<p class="empty-state">Keine Leistungen verfügbar.</p>';
    return;
  }
  grid.innerHTML = state.services.map(service => `
    <button class="service-card ${state.selectedService?.id===service.id?'selected':''}" type="button" data-service-id="${esc(service.id)}">
      <span class="service-icon">${esc(service.icon || 'CP')}</span>
      <span class="service-main"><strong>${esc(service.name)}</strong><span>${esc(service.short_description || '')}</span></span>
      <span class="service-meta"><strong>${esc(service.price_label || '')}</strong><span>${Number(service.duration_min)} Min.</span></span>
    </button>`).join('');
  qsa('[data-service-id]', grid).forEach(button => button.addEventListener('click', () => selectService(button.dataset.serviceId)));
}

async function loadServices() {
  if (!state.provider) return;
  try {
    [state.services, state.colors] = await Promise.all([state.provider.getServices(), state.provider.getColors()]);
    renderServices();
    if (state.selectedService) renderColorSelection();
    if (state.mode === 'server') setConnectivity('');
  } catch (e) {
    $('service-grid').innerHTML = `<p class="empty-state">Server nicht erreichbar. Buchungen können gerade nicht geladen oder gespeichert werden.<br>${esc(e.message)}</p>`;
    if (state.mode === 'server') setConnectivity('Docker-Backend momentan nicht erreichbar. Es werden keine Änderungen vorgetäuscht oder lokal zwischengespeichert.');
  }
}

function selectService(id) {
  state.selectedService = state.services.find(x => x.id === id) || null;
  state.selectedColor = null;
  state.bookingIntent = null;
  state.selectedDate = null;
  state.selectedTime = null;
  state.availabilityDays = {};
  renderServices();
  renderSelectedService();
  renderBookingIntent();
  renderColorSelection();
  updateStepLabels();
  renderDates();
  renderSlots();
  updateBookingSummary();
  $('booking-stage').classList.toggle('hidden', !state.selectedService);
  if (state.selectedService) setTimeout(() => $('booking-stage').scrollIntoView({behavior:'smooth',block:'start'}), 40);
}

function renderSelectedService() {
  const s = state.selectedService;
  if (!s) return;
  $('selected-service').innerHTML = `
    <div class="selected-service-top"><div><strong>${esc(s.name)}</strong><p>${esc(s.short_description || '')} · ${Number(s.duration_min)} Minuten</p></div><span class="selected-price">${esc(s.price_label || '')}</span></div>
    <p class="selected-description">${esc(s.description || '')}</p>`;
}

function renderBookingIntent() {
  const direct = $('choose-book-slot');
  const request = $('choose-request-slot');
  direct.classList.toggle('selected', state.bookingIntent === 'book');
  request.classList.toggle('selected', state.bookingIntent === 'request');
  $('book-flow').classList.toggle('hidden', state.bookingIntent !== 'book');
  $('request-flow').classList.toggle('hidden', state.bookingIntent !== 'request');
  $('booking-form').classList.toggle('hidden', !state.bookingIntent);
  if (!state.bookingIntent) {
    state.selectedDate = null;
    state.selectedTime = null;
  }
  renderColorSelection();
  updateStepLabels();
  updateBookingSummary();
}

function chooseBookingIntent(intent) {
  state.bookingIntent = intent;
  state.selectedDate = null;
  state.selectedTime = null;
  if (intent === 'request') {
    const today = new Date();
    const dateInput = $('request-date');
    dateInput.min = localDateString(today);
    dateInput.value = '';
    $('request-time').value = '';
  }
  renderBookingIntent();
  if (intent === 'book') renderDates();
}

function updateStepLabels() {
  const hasColor = Boolean(state.selectedService && Number(state.selectedService.color_enabled));
  const offset = hasColor ? 1 : 0;
  if ($('date-step-label')) $('date-step-label').textContent = `${3 + offset} · Datum`;
  if ($('time-step-label')) $('time-step-label').textContent = `${4 + offset} · Uhrzeit`;
  if ($('request-step-label')) $('request-step-label').textContent = `${3 + offset} · Wunschzeit`;
  if ($('confirm-step-label')) $('confirm-step-label').textContent = `${state.bookingIntent === 'book' ? 5 + offset : 4 + offset} · Bestätigen`;
}

function renderColorSelection() {
  const section = $('color-section');
  const grid = $('color-grid');
  const enabled = Boolean(state.bookingIntent && state.selectedService && Number(state.selectedService.color_enabled));
  section.classList.toggle('hidden', !enabled);
  if (!enabled) {
    if (state.selectedService && !Number(state.selectedService.color_enabled)) state.selectedColor = null;
    if (!state.bookingIntent) grid.innerHTML = '';
    return;
  }
  if (!state.colors.length) {
    grid.innerHTML = '<p class="empty-state">Aktuell sind keine Farben verfügbar.</p>';
    return;
  }
  grid.innerHTML = state.colors.map(color => `
    <button class="color-choice ${state.selectedColor?.id===color.id?'selected':''}" type="button" data-color-id="${esc(color.id)}">
      <img class="color-swatch" src="${colorSwatchData(color.hex_color)}" alt="">
      <span>${esc(color.name)}</span>
      <strong>${state.selectedColor?.id===color.id?'✓':''}</strong>
    </button>`).join('');
  qsa('[data-color-id]', grid).forEach(button => button.addEventListener('click', () => {
    state.selectedColor = state.colors.find(x => x.id === button.dataset.colorId) || null;
    renderColorSelection();
    updateBookingSummary();
  }));
}

async function renderDates() {
  const strip = $('date-strip');
  strip.innerHTML = '';
  const today = new Date();
  const dates = [];
  for (let i=0;i<28;i++) {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate()+i, 12);
    const value = localDateString(date);
    dates.push({date,value});
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `date-button ${state.selectedDate===value?'selected':''}`;
    button.dataset.date = value;
    button.innerHTML = `<small>${['So','Mo','Di','Mi','Do','Fr','Sa'][date.getDay()]}</small><strong>${date.getDate()}</strong><small>${MONTHS[date.getMonth()]}</small>`;
    button.disabled = true;
    button.addEventListener('click', async () => {
      state.selectedDate = value;
      state.selectedTime = null;
      await renderDates();
      await renderSlots();
      updateBookingSummary();
    });
    strip.appendChild(button);
  }
  if (state.bookingIntent !== 'book' || !state.selectedService) return;
  try {
    const availabilityDays = await state.provider.getAvailabilityDays(state.selectedService.id, 28);
    state.availabilityDays = Object.fromEntries(availabilityDays.map(x => [x.date, Number(x.count)||0]));
    qsa('[data-date]',strip).forEach(button => {
      const count = state.availabilityDays[button.dataset.date] || 0;
      button.disabled = count === 0;
      button.classList.toggle('unavailable', count === 0);
      button.title = count ? `${count} freie Startzeit${count===1?'':'en'}` : 'Keine freie Zeit';
    });
  } catch (e) {
    qsa('[data-date]',strip).forEach(button => { button.disabled=false; button.classList.remove('unavailable'); });
  }
}

async function renderSlots() {
  const grid = $('slot-grid');
  if (state.bookingIntent !== 'book' || !state.selectedService || !state.selectedDate) {
    grid.innerHTML = '<p class="empty-state">Bitte zuerst ein Datum wählen.</p>';
    return;
  }
  grid.innerHTML = '<p class="empty-state">Freie Zeiten werden geladen …</p>';
  try {
    const slots = await state.provider.getAvailability(state.selectedDate, state.selectedService.id);
    if (!slots.length) {
      grid.innerHTML = '<p class="empty-state">An diesem Tag ist aktuell kein passender Termin freigegeben. Du kannst stattdessen einen freien Termin anfragen.</p>';
      return;
    }
    grid.innerHTML = slots.map(slot => `<button class="slot-button ${state.selectedTime===slot?'selected':''}" type="button" data-slot="${esc(slot)}">${esc(slot)}</button>`).join('');
    qsa('[data-slot]',grid).forEach(button => button.addEventListener('click', () => {
      state.selectedTime = button.dataset.slot;
      qsa('[data-slot]',grid).forEach(x => x.classList.toggle('selected', x.dataset.slot === state.selectedTime));
      updateBookingSummary();
    }));
  } catch (e) {
    grid.innerHTML = `<p class="empty-state">Zeiten konnten nicht geladen werden: ${esc(e.message)}</p>`;
  }
}

function formatDate(value, withWeekday=true) {
  const d = parseLocalDate(value);
  return new Intl.DateTimeFormat('de-CH',{weekday:withWeekday?'long':undefined,day:'2-digit',month:'long',year:'numeric'}).format(d);
}

function syncRequestInputs() {
  if (state.bookingIntent !== 'request') return;
  state.selectedDate = $('request-date').value || null;
  state.selectedTime = $('request-time').value || null;
  state.dirty = Boolean(state.selectedDate || state.selectedTime);
  updateBookingSummary();
}

function updateBookingSummary() {
  const needsColor = Boolean(state.selectedService && Number(state.selectedService.color_enabled));
  const ready = Boolean(state.bookingIntent && state.selectedService && state.selectedDate && state.selectedTime && (!needsColor || state.selectedColor));
  $('confirm-booking').disabled = !ready;
  if (!state.bookingIntent) return;
  const isRequest = state.bookingIntent === 'request';
  $('confirm-booking').textContent = isRequest ? 'Terminanfrage senden' : 'Termin verbindlich reservieren';
  $('booking-hint').textContent = isRequest
    ? 'Die Wunschzeit ist zunächst nur eine Anfrage und blockiert noch keinen Termin.'
    : 'Dieser Termin wird sofort verbindlich reserviert.';
  if (!ready) {
    const missing = needsColor && !state.selectedColor ? 'Bitte Farbe, Datum und Uhrzeit wählen' : 'Bitte Datum und Uhrzeit wählen';
    $('booking-summary').innerHTML = `<div class="summary-line"><span>${isRequest?'Anfrage':'Termin'}</span><strong>${missing}</strong></div>`;
    return;
  }
  $('booking-summary').innerHTML = `
    <div class="summary-line"><span>Art</span><strong>${isRequest?'Freie Terminanfrage':'Verbindliche Buchung'}</strong></div>
    <div class="summary-line"><span>Behandlung</span><strong>${esc(state.selectedService.name)}</strong></div>
    ${needsColor ? `<div class="summary-line"><span>Farbe</span><strong><img class="inline-swatch" src="${colorSwatchData(state.selectedColor.hex_color)}" alt="">${esc(state.selectedColor.name)}</strong></div>` : ''}
    <div class="summary-line"><span>${isRequest?'Wunschzeit':'Termin'}</span><strong>${esc(formatDate(state.selectedDate))} · ${esc(state.selectedTime)} Uhr</strong></div>
    <div class="summary-line"><span>Dauer / Preis</span><strong>${Number(state.selectedService.duration_min)} Min. · ${esc(state.selectedService.price_label || '')}</strong></div>`;
}

async function submitBooking(event) {
  event.preventDefault();
  if (!state.bookingIntent || !state.selectedService || !state.selectedDate || !state.selectedTime) return;
  if (Number(state.selectedService.color_enabled) && !state.selectedColor) { showToast('Bitte eine Farbe auswählen.','error'); return; }
  const isRequest = state.bookingIntent === 'request';
  const button = $('confirm-booking');
  button.disabled = true;
  button.textContent = isRequest ? 'Anfrage wird gesendet …' : 'Termin wird reserviert …';
  try {
    const booking = await state.provider.createBooking({
      service_id:state.selectedService.id,
      nail_color_id:state.selectedColor?.id || '',
      date:state.selectedDate,
      start_time:state.selectedTime,
      booking_mode:isRequest ? 'requested' : 'confirmed'
    });
    state.latestBooking = booking;
    state.dirty = false;
    renderSuccess(booking);
    $('success-dialog').showModal();
    if (state.mode === 'server') setConnectivity('');
  } catch (e) {
    showToast(e.message || (isRequest ? 'Anfrage fehlgeschlagen' : 'Buchung fehlgeschlagen'),'error');
    if (state.mode === 'server') setConnectivity('Server nicht erreichbar oder Termin konnte nicht gespeichert werden. Es wird nichts lokal vorgetäuscht.');
    if (!isRequest) await renderSlots();
  } finally {
    updateBookingSummary();
  }
}

function renderSuccess(booking) {
  const requested = booking.status === 'requested';
  $('success-eyebrow').textContent = requested ? 'Terminanfrage gesendet' : 'Reservierung bestätigt';
  $('success-title').textContent = requested ? 'Philipp prüft deinen Wunsch.' : 'Dein Termin steht.';
  $('success-details').innerHTML = `
    <div class="success-row"><span>Status</span><strong>${requested?'Noch nicht bestätigt':'Verbindlich gebucht'}</strong></div>
    <div class="success-row"><span>Behandlung</span><strong>${esc(booking.service_name)}</strong></div>
    ${booking.nail_color_name ? `<div class="success-row"><span>Farbe</span><strong><img class="inline-swatch" src="${colorSwatchData(booking.nail_color_hex)}" alt="">${esc(booking.nail_color_name)}</strong></div>` : ''}
    <div class="success-row"><span>Datum</span><strong>${esc(formatDate(booking.date))}</strong></div>
    <div class="success-row"><span>Uhrzeit</span><strong>${esc(booking.start_time)} Uhr</strong></div>
    <div class="success-row"><span>Buchungscode</span><strong>${esc(booking.public_code)}</strong></div>`;
}

function resetBookingFlow() {
  state.selectedService = null;
  state.selectedColor = null;
  state.bookingIntent = null;
  state.selectedDate = null;
  state.selectedTime = null;
  state.availabilityDays = {};
  $('booking-form').reset();
  $('booking-stage').classList.add('hidden');
  $('booking-form').classList.add('hidden');
  $('book-flow').classList.add('hidden');
  $('request-flow').classList.add('hidden');
  $('color-section').classList.add('hidden');
  renderServices();
  state.dirty = false;
}

async function loadAppointments(extraCode='') {
  if (!state.provider) return;
  const list = $('appointment-list');
  list.innerHTML = '<p class="empty-state">Termine werden geladen …</p>';
  try {
    let rows = await state.provider.getMyBookings();
    if (extraCode) {
      const found = await state.provider.getBookingByCode(extraCode);
      if (found && !rows.some(x => x.id === found.id)) rows.unshift(found);
      if (!found) showToast('Kein Termin zu diesem Buchungscode gefunden.','error');
    }
    if (!rows.length) { list.innerHTML = '<p class="empty-state">Auf diesem Gerät sind noch keine Termine hinterlegt.</p>'; return; }
    list.innerHTML = rows.map(row => appointmentCard(row)).join('');
  } catch (e) {
    list.innerHTML = `<p class="empty-state">Termine konnten nicht geladen werden: ${esc(e.message)}</p>`;
  }
}

function appointmentCard(row) {
  const d = parseLocalDate(row.date);
  const statusLabel = row.status === 'requested' ? 'Anfrage offen' : row.status === 'rejected' ? 'abgelehnt' : row.status === 'cancelled' ? 'storniert' : 'bestätigt';
  return `<article class="appointment-card ${['cancelled','rejected'].includes(row.status)?'cancelled':''}">
    <div class="appointment-date"><small>${MONTHS[d.getMonth()]}</small><strong>${d.getDate()}</strong></div>
    <div class="appointment-main"><strong>${esc(row.service_name)}</strong><span>${esc(formatDate(row.date,false))} · ${esc(row.start_time)}–${esc(row.end_time)} Uhr${row.nail_color_name?` · ${esc(row.nail_color_name)}`:''} · ${esc(statusLabel)}</span></div>
    <div class="appointment-code">${esc(row.public_code)}</div>
  </article>`;
}

async function saveServerSetup() {
  const backendUrl = normalizeUrl($('backend-url').value);
  if (CFG.deployment !== 'docker' && !validateExternalHttps(backendUrl)) {
    showToast('Für das Pages-Frontend ist eine öffentliche HTTPS-Backend-URL erforderlich.','error'); return;
  }
  const old = state.serverConfig || {};
  const next = {
    backendUrl,
    cfClientId:$('cf-client-id').value.trim() || old.cfClientId || '',
    cfClientSecret:$('cf-client-secret').value || old.cfClientSecret || '',
    dockerFallbackUrl:normalizeUrl($('docker-fallback-url').value) || old.dockerFallbackUrl || ''
  };
  const probe = new ServerProvider(next);
  const button = $('save-server-setup');
  button.disabled = true; button.textContent = 'Verbindung wird geprüft …';
  try {
    await probe.init();
    await setDeviceSetting('serverConfig', next);
    state.serverConfig = next;
    state.mode = 'server';
    localStorage.setItem(MODE_KEY,'server');
    state.provider = probe;
    $('cf-client-secret').value = '';
    $('setup-dialog').close();
    refreshModeUi();
    await loadServices();
    showToast('Server-Verbindung gespeichert.');
  } catch (e) {
    showToast(`Verbindung fehlgeschlagen: ${e.message}`,'error');
  } finally { button.disabled=false; button.textContent='Server prüfen & speichern'; }
}

async function chooseMode(mode) {
  qsa('[data-mode-choice]').forEach(x => x.classList.toggle('selected', x.dataset.modeChoice === mode));
  if (mode === 'local') {
    localStorage.setItem(MODE_KEY,'local');
    state.mode = 'local';
    state.provider = new LocalProvider();
    await state.provider.init();
    $('server-setup-fields').classList.add('hidden');
    $('setup-dialog').close();
    refreshModeUi();
    resetBookingFlow();
    await loadServices();
    showToast('Lokaler Modus aktiviert.');
    return;
  }
  $('server-setup-fields').classList.remove('hidden');
  const cfg = state.serverConfig || {};
  $('backend-url').value = cfg.backendUrl || CFG.defaultApiBase || '';
  $('cf-client-id').value = cfg.cfClientId || '';
  $('cf-client-secret').value = '';
  $('docker-fallback-url').value = cfg.dockerFallbackUrl || CFG.dockerFallbackUrl || '';
}

function openSetup(editing=true) {
  $('setup-close').classList.toggle('hidden', !editing && !state.mode);
  $('server-setup-fields').classList.add('hidden');
  qsa('[data-mode-choice]').forEach(x => x.classList.toggle('selected', x.dataset.modeChoice === state.mode));
  if (state.mode === 'server' && editing) {
    $('server-setup-fields').classList.remove('hidden');
    const cfg = state.serverConfig || {};
    $('backend-url').value = cfg.backendUrl || CFG.defaultApiBase || '';
    $('cf-client-id').value = cfg.cfClientId || '';
    $('cf-client-secret').value = '';
    $('docker-fallback-url').value = cfg.dockerFallbackUrl || CFG.dockerFallbackUrl || '';
  }
  $('setup-dialog').showModal();
}

async function clearServerCredentials() {
  if (!confirm('Cloudflare-Zugangsdaten und Backend-Konfiguration auf diesem Gerät vollständig löschen?')) return;
  await idbDelete('device','serverConfig');
  state.serverConfig = null;
  if (state.mode === 'server' && CFG.deployment === 'pages') {
    localStorage.removeItem(MODE_KEY);
    state.mode = null;
    state.provider = null;
  }
  refreshModeUi();
  openSetup(false);
}

async function downloadJson(payload, filename, preferShare=true) {
  const text = JSON.stringify(payload,null,2);
  const file = new File([text], filename, {type:'application/json'});
  if (preferShare && navigator.share && navigator.canShare && navigator.canShare({files:[file]})) {
    try { await navigator.share({files:[file],title:'Chez Philipp Backup'}); return; } catch (e) { if (e.name === 'AbortError') return; }
  }
  const url = URL.createObjectURL(file);
  const a = document.createElement('a');
  a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}

async function exportBackup() {
  try {
    const payload = await state.provider.exportBackup();
    await downloadJson(payload,`chez-philipp-${state.mode}-backup-${localDateString(new Date())}.json`);
    showToast('Backup erstellt.');
  } catch (e) {
    if (e.status === 401) { showToast('Für Server-Backups zuerst im Admin-Bereich anmelden.','error'); goView('admin'); return; }
    showToast(e.message,'error');
  }
}

async function handleImportFile(file) {
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const preview = await state.provider.previewBackup(payload);
    const counts = preview.counts || preview;
    state.pendingImport = payload;
    $('import-preview').innerHTML = `
      <strong>Backup geprüft</strong><p>${Number(counts.services)} Leistungen · ${Number(counts.nail_colors || 0)} Farben · ${Number(counts.opening_hours)} Wochenregeln · ${Number(counts.availability_overrides || 0)} Tagesausnahmen · ${Number(counts.bookings)} Termine/Anfragen.</p>
      <div class="button-row"><button class="secondary-button" id="import-merge" type="button">Zusammenführen</button><button class="ghost-button danger-text" id="import-replace" type="button">Ersetzen</button></div>`;
    $('import-preview').classList.remove('hidden');
    $('import-merge').addEventListener('click', () => applyImport('merge'));
    $('import-replace').addEventListener('click', () => applyImport('replace'));
  } catch (e) { state.pendingImport=null; $('import-preview').classList.add('hidden'); showToast(`Backup ungültig: ${e.message}`,'error'); }
  finally { $('import-backup').value=''; }
}

async function applyImport(strategy) {
  if (!state.pendingImport) return;
  const message = strategy === 'replace'
    ? 'Aktuellen Datenbestand ersetzen? Vorher wird ein Sicherheitsbackup erstellt bzw. angeboten.'
    : 'Backup mit dem aktuellen Datenbestand zusammenführen? Bei gleichen IDs gewinnt der Importstand.';
  if (!confirm(message)) return;
  try {
    await state.provider.applyBackup(state.pendingImport,strategy);
    state.pendingImport=null;
    $('import-preview').classList.add('hidden');
    resetBookingFlow();
    await loadServices();
    showToast('Import erfolgreich abgeschlossen.');
  } catch (e) { showToast(e.message,'error'); }
}

async function openAdmin() {
  goView('admin');
  state.adminState = null;
  $('admin-panel').classList.add('hidden');
  const local = state.mode === 'local';
  if (local) {
    $('admin-login').classList.add('hidden');
    await loadAdminState();
    return;
  }
  $('admin-login').classList.remove('hidden');
  if (sessionStorage.getItem('chez-philipp-admin-pin')) {
    try { await loadAdminState(); return; } catch (e) { if (e.status===401) sessionStorage.removeItem('chez-philipp-admin-pin'); }
  }
}

async function adminLogin() {
  const pin = $('admin-pin').value.trim();
  sessionStorage.setItem('chez-philipp-admin-pin', pin);
  try { await loadAdminState(); $('admin-pin').value=''; }
  catch (e) { sessionStorage.removeItem('chez-philipp-admin-pin'); showToast(e.status===401?'Falscher Admin-PIN.':e.message,'error'); }
}

async function loadAdminState() {
  state.adminState = await state.provider.getAdminState();
  $('admin-login').classList.add('hidden');
  $('admin-panel').classList.remove('hidden');
  renderAdminHours();
  renderAdminServices();
  renderAdminColors();
  renderAdminBookings();
  renderAdminBackup();
}

function renderAdminHours() {
  const root = $('admin-tab-hours');
  const hours = state.adminState?.opening_hours || [];
  const overrides = state.adminState?.availability_overrides || [];
  root.innerHTML = `
    <div class="settings-card availability-intro">
      <div class="settings-card-head"><div><small>Grundregel</small><h3>Regelmässige Freizeit</h3></div></div>
      <p>Diese Zeiten bilden deine normale Woche. Tagesausnahmen darunter ersetzen die Wochenregel für das jeweilige Datum vollständig.</p>
    </div>
    <div class="admin-list">${hours.map(item => `
      <div class="admin-card" data-hour-day="${item.weekday}">
        <div class="admin-card-head"><h3>${WEEKDAYS[item.weekday]}</h3><label class="toggle-row"><input type="checkbox" data-hour-field="enabled" ${Number(item.enabled)?'checked':''}> Verfügbar</label></div>
        <div class="field-grid">
          <label class="field"><span>Von</span><span class="ios-input-shell"><input type="time" data-hour-field="start_time" value="${esc(item.start_time)}"></span></label>
          <label class="field"><span>Bis</span><span class="ios-input-shell"><input type="time" data-hour-field="end_time" value="${esc(item.end_time)}"></span></label>
          <label class="field field-full"><span>Startzeit-Raster</span><select data-hour-field="slot_interval_min"><option value="15" ${Number(item.slot_interval_min)===15?'selected':''}>15 Minuten</option><option value="30" ${Number(item.slot_interval_min)===30?'selected':''}>30 Minuten</option><option value="60" ${Number(item.slot_interval_min)===60?'selected':''}>60 Minuten</option></select></label>
        </div>
      </div>`).join('')}</div>
    <div class="admin-actions"><button class="primary-button" id="save-hours" type="button">Wochenplan speichern</button></div>

    <div class="settings-card availability-intro">
      <div class="settings-card-head"><div><small>Ausnahmen</small><h3>Einzelne Tage</h3></div></div>
      <p>Ideal für spontane Freizeit, Ferien oder einen Tag, an dem du bewusst keine Termine möchtest.</p>
      <div class="button-row wrap-row"><button class="secondary-button" id="add-available-override" type="button">Freie Zeit hinzufügen</button><button class="ghost-button" id="add-closed-override" type="button">Tag sperren</button></div>
    </div>
    <div class="admin-list" id="availability-override-list">${overrides.length ? overrides.map((item,index) => availabilityOverrideCard(item,index)).join('') : '<p class="empty-state">Noch keine Tagesausnahmen. Es gilt der Wochenplan.</p>'}</div>
    <div class="admin-actions"><button class="primary-button" id="save-overrides" type="button">Tagesausnahmen speichern</button></div>`;
  $('save-hours').addEventListener('click', saveAdminHours);
  $('add-available-override').addEventListener('click', () => {
    state.adminState.availability_overrides.push({id:uid(),date:localDateString(new Date()),kind:'available',start_time:'18:00',end_time:'21:00'});
    renderAdminHours();
  });
  $('add-closed-override').addEventListener('click', () => {
    state.adminState.availability_overrides.push({id:uid(),date:localDateString(new Date()),kind:'closed',start_time:'',end_time:''});
    renderAdminHours();
  });
  qsa('[data-remove-override]',root).forEach(button => button.addEventListener('click', () => {
    state.adminState.availability_overrides.splice(Number(button.dataset.removeOverride),1);
    renderAdminHours();
  }));
  $('save-overrides').addEventListener('click', saveAvailabilityOverrides);
}

function availabilityOverrideCard(item,index) {
  const closed = item.kind === 'closed';
  return `<div class="admin-card" data-override-index="${index}">
    <div class="admin-card-head"><h3>${closed?'Tag gesperrt':'Zusätzliche Freizeit'}</h3><button class="text-button danger-text" data-remove-override="${index}" type="button">Entfernen</button></div>
    <div class="field-grid">
      <label class="field field-full"><span>Datum</span><span class="ios-input-shell"><input type="date" data-override-field="date" value="${esc(item.date || '')}"></span></label>
      <label class="field field-full"><span>Regel</span><select data-override-field="kind"><option value="available" ${!closed?'selected':''}>An diesem Tag verfügbar</option><option value="closed" ${closed?'selected':''}>An diesem Tag nicht verfügbar</option></select></label>
      <label class="field override-time ${closed?'hidden':''}"><span>Von</span><span class="ios-input-shell"><input type="time" data-override-field="start_time" value="${esc(item.start_time || '18:00')}"></span></label>
      <label class="field override-time ${closed?'hidden':''}"><span>Bis</span><span class="ios-input-shell"><input type="time" data-override-field="end_time" value="${esc(item.end_time || '21:00')}"></span></label>
    </div>
  </div>`;
}

async function saveAdminHours() {
  const items = qsa('[data-hour-day]').map(card => ({
    weekday:Number(card.dataset.hourDay),
    enabled:card.querySelector('[data-hour-field="enabled"]').checked?1:0,
    start_time:card.querySelector('[data-hour-field="start_time"]').value,
    end_time:card.querySelector('[data-hour-field="end_time"]').value,
    slot_interval_min:Number(card.querySelector('[data-hour-field="slot_interval_min"]').value)
  }));
  try { await state.provider.saveOpeningHours(items); state.adminState.opening_hours=items; showToast('Wochenplan gespeichert.'); }
  catch (e) { showToast(e.message,'error'); }
}

async function saveAvailabilityOverrides() {
  const items = qsa('[data-override-index]').map(card => {
    const index=Number(card.dataset.overrideIndex);
    const old=state.adminState.availability_overrides[index] || {};
    const kind=card.querySelector('[data-override-field="kind"]').value;
    return {
      id:old.id || uid(), date:card.querySelector('[data-override-field="date"]').value, kind,
      start_time:kind==='available'?card.querySelector('[data-override-field="start_time"]').value:'',
      end_time:kind==='available'?card.querySelector('[data-override-field="end_time"]').value:'',
      created_at:old.created_at || nowIso(), updated_at:nowIso()
    };
  });
  try {
    await state.provider.saveAvailabilityOverrides(items);
    state.adminState.availability_overrides=items.sort((a,b)=>`${a.date}${a.start_time}`.localeCompare(`${b.date}${b.start_time}`));
    renderAdminHours();
    showToast('Tagesausnahmen gespeichert.');
  } catch (e) { showToast(e.message,'error'); }
}

function renderAdminServices() {
  const root = $('admin-tab-services');
  const services = state.adminState?.services || [];
  root.innerHTML = `<div class="admin-list" id="admin-service-list">${services.map((item,index) => serviceAdminCard(item,index)).join('')}</div>
    <div class="admin-actions"><button class="secondary-button" id="add-service" type="button">Leistung hinzufügen</button><button class="primary-button" id="save-services" type="button">Leistungen speichern</button></div>`;
  $('add-service').addEventListener('click', () => {
    state.adminState.services.push({id:uid(),name:'Neue Leistung',short_description:'',description:'',price_label:'',duration_min:30,icon:'CP',color_enabled:0,active:1,sort_order:state.adminState.services.length*10+10,created_at:nowIso(),updated_at:nowIso()});
    renderAdminServices();
  });
  $('save-services').addEventListener('click', saveAdminServices);
}

function serviceAdminCard(item,index) {
  return `<div class="admin-card" data-service-admin="${index}">
    <div class="admin-card-head"><h3>${esc(item.name || 'Leistung')}</h3><label class="toggle-row"><input type="checkbox" data-svc-field="active" ${Number(item.active)?'checked':''}> Aktiv</label></div>
    <div class="field-grid">
      <label class="field"><span>Kürzel</span><input data-svc-field="icon" maxlength="12" value="${esc(item.icon||'')}"></label>
      <label class="field"><span>Name</span><input data-svc-field="name" maxlength="120" value="${esc(item.name||'')}"></label>
      <label class="field field-full"><span>Kurzbeschreibung</span><input data-svc-field="short_description" maxlength="220" value="${esc(item.short_description||'')}"></label>
      <label class="field field-full"><span>Beschreibung</span><textarea data-svc-field="description" maxlength="2000" rows="3">${esc(item.description||'')}</textarea></label>
      <label class="field"><span>Preistext</span><input data-svc-field="price_label" maxlength="80" value="${esc(item.price_label||'')}"></label>
      <label class="field"><span>Dauer (Min.)</span><input data-svc-field="duration_min" type="number" min="5" max="480" step="5" value="${Number(item.duration_min)||30}"></label>
      <label class="toggle-row field-full"><input type="checkbox" data-svc-field="color_enabled" ${Number(item.color_enabled)?'checked':''}> Farbauswahl bei dieser Leistung anzeigen</label>
    </div>
  </div>`;
}

async function saveAdminServices() {
  const items = qsa('[data-service-admin]').map(card => {
    const index = Number(card.dataset.serviceAdmin);
    const old = state.adminState.services[index];
    return {...old,
      active:card.querySelector('[data-svc-field="active"]').checked?1:0,
      icon:card.querySelector('[data-svc-field="icon"]').value.trim(),
      name:card.querySelector('[data-svc-field="name"]').value.trim(),
      short_description:card.querySelector('[data-svc-field="short_description"]').value.trim(),
      description:card.querySelector('[data-svc-field="description"]').value.trim(),
      price_label:card.querySelector('[data-svc-field="price_label"]').value.trim(),
      duration_min:Number(card.querySelector('[data-svc-field="duration_min"]').value),
      color_enabled:card.querySelector('[data-svc-field="color_enabled"]').checked?1:0,
      sort_order:index*10+10
    };
  });
  try {
    await state.provider.saveServices(items);
    state.adminState.services=items;
    state.services = await state.provider.getServices();
    renderServices(); renderAdminServices(); showToast('Leistungen gespeichert.');
  } catch (e) { showToast(e.message,'error'); }
}

function renderAdminColors() {
  const root = $('admin-tab-colors');
  const colors = state.adminState?.nail_colors || [];
  root.innerHTML = `<div class="admin-list" id="admin-color-list">${colors.map((item,index) => `
    <div class="admin-card color-admin-card" data-color-admin="${index}">
      <div class="admin-card-head"><h3><img class="admin-color-swatch" src="${colorSwatchData(item.hex_color)}" alt="">${esc(item.name || 'Farbe')}</h3><label class="toggle-row"><input type="checkbox" data-color-field="active" ${Number(item.active)?'checked':''}> Aktiv</label></div>
      <div class="field-grid">
        <label class="field"><span>Name</span><input data-color-field="name" maxlength="100" value="${esc(item.name || '')}"></label>
        <label class="field color-picker-field"><span>Farbton</span><input data-color-field="hex_color" type="color" value="${esc(item.hex_color || '#B9B2AA')}"></label>
      </div>
    </div>`).join('')}</div>
    <div class="admin-actions"><button class="secondary-button" id="add-color" type="button">Farbe hinzufügen</button><button class="primary-button" id="save-colors" type="button">Farben speichern</button></div>`;
  $('add-color').addEventListener('click', () => {
    state.adminState.nail_colors.push({id:uid(),name:'Neue Farbe',hex_color:'#C7B2A6',active:1,sort_order:state.adminState.nail_colors.length*10+10,created_at:nowIso(),updated_at:nowIso()});
    renderAdminColors();
  });
  $('save-colors').addEventListener('click', saveAdminColors);
}

async function saveAdminColors() {
  const items = qsa('[data-color-admin]').map(card => {
    const index = Number(card.dataset.colorAdmin);
    const old = state.adminState.nail_colors[index];
    return {...old,
      active:card.querySelector('[data-color-field="active"]').checked?1:0,
      name:card.querySelector('[data-color-field="name"]').value.trim(),
      hex_color:card.querySelector('[data-color-field="hex_color"]').value,
      sort_order:index*10+10
    };
  });
  try {
    await state.provider.saveNailColors(items);
    state.adminState.nail_colors=items;
    state.colors = await state.provider.getColors();
    renderAdminColors();
    if (state.selectedService) renderColorSelection();
    showToast('Farben gespeichert.');
  } catch (e) { showToast(e.message,'error'); }
}

function renderAdminBookings() {
  const root = $('admin-tab-bookings');
  const rows = state.adminState?.bookings || [];
  const mailInfo = state.mode === 'server'
    ? `<div class="settings-card notification-card"><div class="settings-card-head"><div><small>Benachrichtigung</small><h3>E-Mail bei Buchung & Anfrage</h3></div><span class="status-dot ${state.adminState?.notification_enabled?'ok':'bad'}"></span></div><p>${state.adminState?.notification_enabled?'Aktiv. Verbindliche Buchungen und freie Terminanfragen werden persistent in der Outbox erfasst. Buchungen enthalten den ICS-Anhang; Anfragen bewusst noch nicht.':'Nicht vollständig konfiguriert oder deaktiviert. Prüfe die SMTP-/NOTIFY-Environment-Variablen.'}</p></div>`
    : `<div class="security-note"><strong>Lokaler Modus:</strong> Lokale Buchungen und Anfragen bleiben auf diesem Gerät und lösen keine E-Mail an Philipp aus.</div>`;
  root.innerHTML = `${mailInfo}<div class="admin-list admin-booking-list">${rows.length ? rows.map(row => {
    const mailStatus = row.notification_status === 'sent' ? 'Mail gesendet' : row.notification_status === 'failed' ? 'Mail-Zustellung fehlgeschlagen' : row.notification_status === 'pending' ? 'Mail ausstehend' : 'Keine Mail eingeplant';
    const retry = state.mode === 'server' && state.adminState?.notification_enabled && row.notification_status && row.notification_status !== 'sent'
      ? `<button class="ghost-button" data-retry-notification="${esc(row.id)}" type="button">Mail erneut versuchen</button>` : '';
    const statusLabel = row.status === 'requested' ? 'Anfrage offen' : row.status === 'rejected' ? 'Abgelehnt' : row.status === 'cancelled' ? 'Storniert' : 'Bestätigt';
    const requestActions = row.status === 'requested'
      ? `<button class="primary-button compact-action" data-confirm-request="${esc(row.id)}" type="button">Bestätigen</button><button class="ghost-button danger-text" data-reject-request="${esc(row.id)}" type="button">Ablehnen</button>` : '';
    const cancelAction = row.status === 'confirmed' ? `<button class="ghost-button danger-text" data-cancel-booking="${esc(row.id)}" type="button">Termin stornieren</button>` : '';
    return `<div class="admin-card ${['cancelled','rejected'].includes(row.status)?'cancelled':''} ${row.status==='requested'?'request-card':''}">
      <div class="admin-card-head"><h3>${esc(row.service_name)}</h3><span class="version-chip">${esc(row.public_code)}</span></div>
      <div class="booking-admin-meta"><span>${esc(formatDate(row.date))} · ${esc(row.start_time)}–${esc(row.end_time)} Uhr · ${esc(row.price_label||'')}</span>${row.nail_color_name?`<span>Farbe: ${esc(row.nail_color_name)}</span>`:''}${row.notes?`<span>Notiz: ${esc(row.notes)}</span>`:''}<span><strong>Status: ${esc(statusLabel)}</strong></span>${state.mode==='server'?`<span>Benachrichtigung: ${esc(mailStatus)}${Number(row.notification_attempts)>0?` · ${Number(row.notification_attempts)} Versuch${Number(row.notification_attempts)===1?'':'e'}`:''}</span>`:''}</div>
      ${(requestActions||cancelAction||retry)?`<div class="admin-actions">${requestActions}${cancelAction}${retry}</div>`:''}
    </div>`;
  }).join('') : '<p class="empty-state">Keine Termine oder Anfragen vorhanden.</p>'}</div>`;
  qsa('[data-confirm-request]',root).forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Diese Wunschzeit verbindlich bestätigen?')) return;
    try { await state.provider.confirmBooking(button.dataset.confirmRequest); await loadAdminState(); showToast('Terminanfrage bestätigt.'); }
    catch (e) { showToast(e.message,'error'); }
  }));
  qsa('[data-reject-request]',root).forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Diese Terminanfrage ablehnen?')) return;
    try { await state.provider.rejectBooking(button.dataset.rejectRequest); await loadAdminState(); showToast('Terminanfrage abgelehnt.'); }
    catch (e) { showToast(e.message,'error'); }
  }));
  qsa('[data-cancel-booking]',root).forEach(button => button.addEventListener('click', async () => {
    if (!confirm('Diesen Termin wirklich stornieren?')) return;
    try { await state.provider.cancelBooking(button.dataset.cancelBooking); await loadAdminState(); showToast('Termin storniert.'); }
    catch (e) { showToast(e.message,'error'); }
  }));
  qsa('[data-retry-notification]',root).forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { const result = await state.provider.retryNotification(button.dataset.retryNotification); await loadAdminState(); showToast(result.status === 'sent' ? 'E-Mail wurde gesendet.' : 'E-Mail bleibt für einen erneuten Versuch vorgemerkt.'); }
    catch (e) { showToast(e.message,'error'); }
    finally { button.disabled = false; }
  }));
}

function renderAdminBackup() {
  const root = $('admin-tab-backup');
  root.innerHTML = `<div class="settings-card">
    <div class="settings-card-head"><div><small>Sicherungsstrategie</small><h3>${state.mode==='local'?'Lokales JSON-Backup':'Server-Backup'}</h3></div></div>
    <p>${state.mode==='local'?'Exportiert den vollständigen lokalen Datenbestand. Geräte-Secrets sind ausgeschlossen.':'Der Server kann ein SQLite-Sicherheitsbackup unter /app/data/backups anlegen. Zusätzlich steht der JSON-Export unter „Mehr“ zur Verfügung.'}</p>
    <div class="button-row"><button class="secondary-button" id="admin-json-export" type="button">JSON exportieren</button>${state.mode==='server'?'<button class="ghost-button" id="server-snapshot" type="button">SQLite-Snapshot</button>':''}</div>
  </div>`;
  $('admin-json-export').addEventListener('click', exportBackup);
  if ($('server-snapshot')) $('server-snapshot').addEventListener('click', async () => {
    try { const result=await state.provider.createServerBackup(); showToast(`Server-Backup erstellt: ${result.file}`); } catch (e) { showToast(e.message,'error'); }
  });
}

function switchAdminTab(name) {
  qsa('[data-admin-tab]').forEach(x => x.classList.toggle('active',x.dataset.adminTab===name));
  qsa('.admin-tab-panel').forEach(x => x.classList.toggle('active',x.id===`admin-tab-${name}`));
}

async function checkForUpdate() {
  if (!('serviceWorker' in navigator)) { $('update-status').textContent='Service Worker wird von diesem Browser nicht unterstützt.'; return; }
  const reg = state.updateRegistration || await navigator.serviceWorker.getRegistration();
  if (!reg) { $('update-status').textContent='Service Worker ist noch nicht registriert.'; return; }
  $('update-status').textContent='Update-Prüfung läuft …';
  try {
    await reg.update();
    await sleep(700);
    if (reg.waiting || state.updateWaiting) {
      showUpdateReady(reg.waiting || state.updateWaiting);
    } else {
      $('update-status').textContent=`v${APP_VERSION} ist aktuell. Falls gerade ein Release veröffentlicht wurde, kann die Erkennung browserbedingt etwas verzögert sein.`;
    }
  } catch (e) { $('update-status').textContent=`Update-Prüfung nicht möglich: ${e.message}`; }
}

function showUpdateReady(worker) {
  state.updateWaiting = worker;
  $('update-banner').classList.remove('hidden');
  $('manual-update').classList.remove('hidden');
  $('update-status').textContent='Eine neue Version wurde heruntergeladen und wartet auf einen sicheren Wechsel.';
}

async function applyPreparedUpdate() {
  const reg = state.updateRegistration || await navigator.serviceWorker.getRegistration();
  const worker = reg?.waiting || state.updateWaiting;
  if (!worker) { await checkForUpdate(); return; }
  if (state.dirty && !confirm('Es gibt noch Eingaben im Buchungsformular. Trotzdem jetzt aktualisieren?')) return;
  sessionStorage.setItem('chez-philipp-update-reload-once','1');
  worker.postMessage({type:'SKIP_WAITING'});
}

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.register('./service-worker.js',{scope:'./'});
    state.updateRegistration = reg;
    if (reg.waiting) showUpdateReady(reg.waiting);
    reg.addEventListener('updatefound', () => {
      const worker = reg.installing;
      if (!worker) return;
      worker.addEventListener('statechange', () => {
        if (worker.state === 'installed' && navigator.serviceWorker.controller) showUpdateReady(worker);
      });
    });
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (sessionStorage.getItem('chez-philipp-update-reload-once') === '1') {
        sessionStorage.removeItem('chez-philipp-update-reload-once');
        location.reload();
      }
    });
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') reg.update().catch(()=>{}); });
  } catch (e) { console.warn('Service worker registration failed',e); }
}

function bindEvents() {
  qsa('[data-nav]').forEach(button => button.addEventListener('click', () => goView(button.dataset.nav)));
  $('brand-home').addEventListener('click', () => goView('book'));
  $('open-more').addEventListener('click', () => goView('more'));
  $('choose-book-slot').addEventListener('click', () => chooseBookingIntent('book'));
  $('choose-request-slot').addEventListener('click', () => chooseBookingIntent('request'));
  $('request-date').addEventListener('input', syncRequestInputs);
  $('request-time').addEventListener('input', syncRequestInputs);
  $('booking-form').addEventListener('submit', submitBooking);
  qsa('#booking-form input, #booking-form textarea').forEach(el => el.addEventListener('input', () => { state.dirty = true; }));
  $('success-close').addEventListener('click', () => { $('success-dialog').close(); resetBookingFlow(); goView('book'); });
  $('success-appointments').addEventListener('click', () => { $('success-dialog').close(); resetBookingFlow(); goView('appointments'); });
  $('lookup-booking').addEventListener('click', () => loadAppointments($('booking-code-input').value.trim()));
  $('booking-code-input').addEventListener('keydown', e => { if (e.key==='Enter') loadAppointments(e.target.value.trim()); });
  $('change-mode').addEventListener('click', () => openSetup(true));
  $('edit-server').addEventListener('click', () => openSetup(true));
  $('clear-server').addEventListener('click', clearServerCredentials);
  qsa('[data-mode-choice]').forEach(button => button.addEventListener('click', () => chooseMode(button.dataset.modeChoice)));
  $('save-server-setup').addEventListener('click', saveServerSetup);
  $('export-backup').addEventListener('click', exportBackup);
  $('import-backup').addEventListener('change', e => handleImportFile(e.target.files?.[0]));
  $('open-admin').addEventListener('click', openAdmin);
  $('admin-back').addEventListener('click', () => goView('more'));
  $('admin-login-button').addEventListener('click', adminLogin);
  $('admin-pin').addEventListener('keydown', e => { if (e.key==='Enter') adminLogin(); });
  qsa('[data-admin-tab]').forEach(button => button.addEventListener('click', () => switchAdminTab(button.dataset.adminTab)));
  $('check-update').addEventListener('click', checkForUpdate);
  $('manual-update').addEventListener('click', applyPreparedUpdate);
  $('apply-update').addEventListener('click', applyPreparedUpdate);
  $('open-docker-fallback').addEventListener('click', () => {
    const url = state.serverConfig?.dockerFallbackUrl || CFG.dockerFallbackUrl;
    if (url) window.open(url,'_blank','noopener,noreferrer');
  });
  window.addEventListener('online', () => { if (state.mode==='server') { setConnectivity(''); loadServices(); } });
  window.addEventListener('offline', () => {
    if (state.mode==='local') setConnectivity('Offline · Lokaler Modus bleibt mit App-Shell und IndexedDB nutzbar.');
    else setConnectivity('Offline · App-Shell läuft lokal weiter. Schreibaktionen zum Server sind aktuell nicht möglich.');
  });
}

async function boot() {
  bindEvents();
  await registerServiceWorker();
  await configureProvider();
  refreshModeUi();
  if (!state.mode && CFG.deployment === 'pages') {
    openSetup(false);
    $('service-grid').innerHTML = '<p class="empty-state">Wähle zuerst den Betriebsmodus.</p>';
  } else {
    await loadServices();
  }
  const lastView = localStorage.getItem(VIEW_KEY);
  goView(['book','appointments','more'].includes(lastView) ? lastView : 'book');
  if (!navigator.onLine) {
    setConnectivity(state.mode==='local' ? 'Offline · Lokaler Modus bleibt vollständig auf diesem Gerät nutzbar.' : 'Offline · Lokal gecachte App-Oberfläche wird verwendet.');
  }
}

document.addEventListener('DOMContentLoaded', boot);
