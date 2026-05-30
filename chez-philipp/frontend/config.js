// Runtime config - overwritten by docker entrypoint at container start
const API           = window.location.protocol + '//' + window.location.hostname + ':3200/api';
const CALDAV_URL    = window.location.protocol + '//' + window.location.hostname + ':3200/caldav/philipp/calendar/';
const CALDAV_USER   = 'philipp';
const CALDAV_PASS   = 'geheim123';
const ADMIN_PIN_ENV = '1234';
