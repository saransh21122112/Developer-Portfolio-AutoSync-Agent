import fs from 'fs';
import path from 'path';
import { createClient } from '@libsql/client';

const isVercel = !!process.env.VERCEL;
const DB_FILE = isVercel 
  ? path.join('/tmp', 'local_db.json')
  : path.join(process.cwd(), 'local_db.json');

const useTurso = !!(process.env.TURSO_DATABASE_URL && process.env.TURSO_AUTH_TOKEN);

let client = null;
if (useTurso) {
  client = createClient({
    url: process.env.TURSO_DATABASE_URL,
    authToken: process.env.TURSO_AUTH_TOKEN,
  });
}

let initPromise = null;
async function initDb() {
  if (!useTurso) return;
  if (!initPromise) {
    initPromise = (async () => {
      await client.execute(`
        CREATE TABLE IF NOT EXISTS logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp TEXT NOT NULL,
          level TEXT NOT NULL,
          name TEXT NOT NULL,
          message TEXT NOT NULL
        )
      `);
      await client.execute(`
        CREATE TABLE IF NOT EXISTS approvals (
          project TEXT PRIMARY KEY,
          metadata TEXT NOT NULL,
          content TEXT NOT NULL,
          diff TEXT NOT NULL,
          status TEXT NOT NULL,
          timestamp TEXT NOT NULL
        )
      `);
      await client.execute(`
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
      `);
    })();
  }
  return initPromise;
}

// Local File Helper functions
function readLocalDb() {
  if (!fs.existsSync(DB_FILE)) {
    return { logs: [], approvals: {}, sync_pending: false };
  }
  try {
    const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
    if (data.sync_pending === undefined) {
      data.sync_pending = false;
    }
    if (data.approvals === undefined) {
      data.approvals = {};
    }
    if (data.logs === undefined) {
      data.logs = [];
    }
    return data;
  } catch (e) {
    return { logs: [], approvals: {}, sync_pending: false };
  }
}

function writeLocalDb(data) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
  } catch (e) {
    console.error('Failed to write local DB:', e);
  }
}

// Exported structured helpers
export async function getLogs() {
  if (useTurso) {
    await initDb();
    const res = await client.execute("SELECT timestamp, level, name, message FROM logs ORDER BY id DESC LIMIT 300");
    return res.rows.map(row => ({
      timestamp: row.timestamp,
      level: row.level,
      name: row.name,
      message: row.message
    }));
  }
  return readLocalDb().logs;
}

export async function addLog(logEntry) {
  if (useTurso) {
    await initDb();
    await client.execute({
      sql: "INSERT INTO logs (timestamp, level, name, message) VALUES (?, ?, ?, ?)",
      args: [
        logEntry.timestamp || new Date().toISOString(),
        logEntry.level || 'INFO',
        logEntry.name || 'Agent',
        logEntry.message
      ]
    });
    return;
  }
  const db = readLocalDb();
  db.logs.unshift(logEntry);
  db.logs = db.logs.slice(0, 300);
  writeLocalDb(db);
}

export async function getApprovals() {
  if (useTurso) {
    await initDb();
    const res = await client.execute("SELECT project, metadata, content, diff, status, timestamp FROM approvals");
    const approvals = {};
    res.rows.forEach(row => {
      approvals[row.project] = {
        project: row.project,
        metadata: JSON.parse(row.metadata),
        content: row.content,
        diff: row.diff,
        status: row.status,
        timestamp: row.timestamp
      };
    });
    return approvals;
  }
  return readLocalDb().approvals;
}

export async function getApproval(project) {
  if (useTurso) {
    await initDb();
    const res = await client.execute({
      sql: "SELECT project, metadata, content, diff, status, timestamp FROM approvals WHERE project = ?",
      args: [project]
    });
    if (res.rows.length === 0) return null;
    const row = res.rows[0];
    return {
      project: row.project,
      metadata: JSON.parse(row.metadata),
      content: row.content,
      diff: row.diff,
      status: row.status,
      timestamp: row.timestamp
    };
  }
  return readLocalDb().approvals[project] || null;
}

export async function saveApproval(project, pendingItem) {
  if (useTurso) {
    await initDb();
    await client.execute({
      sql: "INSERT OR REPLACE INTO approvals (project, metadata, content, diff, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
      args: [
        project,
        JSON.stringify(pendingItem.metadata || {}),
        pendingItem.content || '',
        pendingItem.diff || '',
        pendingItem.status || 'pending',
        pendingItem.timestamp || new Date().toISOString()
      ]
    });
    return;
  }
  const db = readLocalDb();
  db.approvals[project] = pendingItem;
  writeLocalDb(db);
}

export async function updateApprovalStatus(project, status) {
  if (useTurso) {
    await initDb();
    await client.execute({
      sql: "UPDATE approvals SET status = ? WHERE project = ?",
      args: [status, project]
    });
    return;
  }
  const db = readLocalDb();
  if (db.approvals[project]) {
    db.approvals[project].status = status;
    writeLocalDb(db);
  }
}

export async function getSyncPending() {
  if (useTurso) {
    await initDb();
    const res = await client.execute({
      sql: "SELECT value FROM settings WHERE key = 'sync_pending'",
      args: []
    });
    if (res.rows.length === 0) return false;
    return res.rows[0].value === 'true';
  }
  return readLocalDb().sync_pending || false;
}

export async function setSyncPending(syncPending) {
  if (useTurso) {
    await initDb();
    await client.execute({
      sql: "INSERT OR REPLACE INTO settings (key, value) VALUES ('sync_pending', ?)",
      args: [syncPending ? 'true' : 'false']
    });
    return;
  }
  const db = readLocalDb();
  db.sync_pending = syncPending;
  writeLocalDb(db);
}
