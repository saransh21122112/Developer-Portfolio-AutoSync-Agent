import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';
import fs from 'fs';
import path from 'path';

const DB_FILE = path.join(process.cwd(), 'local_db.json');
const isKvConfigured = !!(process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN);

function readLocalDb() {
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

function writeLocalDb(data) {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
  } catch (e) {
    console.error('Failed to write local DB:', e);
  }
}

export async function GET() {
  if (isKvConfigured) {
    try {
      const syncPending = await kv.get('sync_pending') || false;
      return NextResponse.json({ sync_pending: syncPending });
    } catch (e) {
      console.error('Vercel KV GET sync_pending error:', e);
    }
  }

  const db = readLocalDb();
  return NextResponse.json({ sync_pending: db.sync_pending || false });
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { sync_pending } = body;

    if (sync_pending === undefined) {
      return NextResponse.json({ error: 'sync_pending boolean is required' }, { status: 400 });
    }

    if (isKvConfigured) {
      try {
        await kv.set('sync_pending', sync_pending);
        return NextResponse.json({ success: true, sync_pending });
      } catch (e) {
        console.error('Vercel KV POST sync_pending error:', e);
      }
    }

    const db = readLocalDb();
    db.sync_pending = sync_pending;
    writeLocalDb(db);

    return NextResponse.json({ success: true, sync_pending });
  } catch (e) {
    console.error('API sync-request POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
