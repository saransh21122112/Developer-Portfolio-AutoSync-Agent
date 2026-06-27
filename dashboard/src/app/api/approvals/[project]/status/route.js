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

// GET status of a project
export async function GET(request, { params }) {
  const { project } = await params;
  
  if (isKvConfigured) {
    try {
      const approvals = await kv.get('agent_approvals') || {};
      const item = approvals[project];
      if (!item) {
        return NextResponse.json({ project, status: 'none' });
      }
      return NextResponse.json({ project, status: item.status, item });
    } catch (e) {
      console.error('Vercel KV Status GET Error:', e);
    }
  }

  const db = readLocalDb();
  const item = db.approvals[project];
  if (!item) {
    return NextResponse.json({ project, status: 'none' });
  }
  return NextResponse.json({ project, status: item.status, item });
}

// POST to update status (e.g. from 'approved' to 'completed' / 'failed')
export async function POST(request, { params }) {
  const { project } = await params;
  
  try {
    const body = await request.json();
    const { status } = body;

    if (!status) {
      return NextResponse.json({ error: 'Status is required' }, { status: 400 });
    }

    if (isKvConfigured) {
      try {
        let approvals = await kv.get('agent_approvals') || {};
        if (!approvals[project]) {
          return NextResponse.json({ error: 'Project not found' }, { status: 404 });
        }
        approvals[project].status = status;
        await kv.set('agent_approvals', approvals);
        return NextResponse.json({ success: true, status });
      } catch (e) {
        console.error('Vercel KV Status POST Error:', e);
      }
    }

    const db = readLocalDb();
    if (!db.approvals[project]) {
      return NextResponse.json({ error: 'Project not found' }, { status: 404 });
    }
    db.approvals[project].status = status;
    writeLocalDb(db);

    return NextResponse.json({ success: true, status });
  } catch (e) {
    console.error('API Status POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
