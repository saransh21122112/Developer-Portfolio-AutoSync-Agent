import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';
import fs from 'fs';
import path from 'path';

const DB_FILE = path.join(process.cwd(), 'local_db.json');
const isKvConfigured = !!(process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN);

function readLocalDb() {
  if (!fs.existsSync(DB_FILE)) {
    return { logs: [], approvals: {} };
  }
  try {
    return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
  } catch (e) {
    return { logs: [], approvals: {} };
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
      const approvals = await kv.get('agent_approvals') || {};
      return NextResponse.json(approvals);
    } catch (e) {
      console.error('Vercel KV GET Approvals Error:', e);
    }
  }

  const db = readLocalDb();
  return NextResponse.json(db.approvals);
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { project, metadata, content, diff } = body;

    if (!project) {
      return NextResponse.json({ error: 'Project name is required' }, { status: 400 });
    }

    const pendingItem = {
      project,
      metadata: metadata || {},
      content: content || '',
      diff: diff || '',
      status: 'pending',
      timestamp: new Date().toISOString()
    };

    if (isKvConfigured) {
      try {
        let approvals = await kv.get('agent_approvals') || {};
        approvals[project] = pendingItem;
        await kv.set('agent_approvals', approvals);
        return NextResponse.json({ success: true, item: pendingItem });
      } catch (e) {
        console.error('Vercel KV POST Approvals Error:', e);
      }
    }

    const db = readLocalDb();
    db.approvals[project] = pendingItem;
    writeLocalDb(db);

    return NextResponse.json({ success: true, item: pendingItem });
  } catch (e) {
    console.error('API Approvals POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
