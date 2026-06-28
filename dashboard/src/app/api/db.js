import fs from 'fs';
import path from 'path';

// On Vercel, the filesystem is read-only except for /tmp.
// We check process.env.VERCEL to detect the serverless runtime.
const isVercel = !!process.env.VERCEL;
const DB_FILE = isVercel 
  ? path.join('/tmp', 'local_db.json')
  : path.join(process.cwd(), 'local_db.json');

export const isKvConfigured = !!(process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN);

export function readLocalDb() {
  if (!fs.existsSync(DB_FILE)) {
    return { logs: [], approvals: {}, sync_pending: false };
  }
  try {
    const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
    if (data.sync_pending === undefined) {
      data.sync_pending = false;
    }
    return data;
  } catch (e) {
    return { logs: [], approvals: {}, sync_pending: false };
  }
}

export function writeLocalDb(data) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
  } catch (e) {
    console.error('Failed to write local DB:', e);
  }
}
