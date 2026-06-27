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

export async function POST(request) {
  try {
    const body = await request.json();
    const { project, action } = body; // action is either 'approve' or 'reject'

    if (!project || !['approve', 'reject'].includes(action)) {
      return NextResponse.json({ error: 'Project name and action ("approve"/"reject") are required' }, { status: 400 });
    }

    const targetStatus = action === 'approve' ? 'approved' : 'rejected';
    const logMessage = `User ${action === 'approve' ? 'approved' : 'rejected'} the portfolio update for project '${project}'.`;

    const logEntry = {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      name: 'DashboardUI',
      message: logMessage
    };

    if (isKvConfigured) {
      try {
        let approvals = await kv.get('agent_approvals') || {};
        if (!approvals[project]) {
          return NextResponse.json({ error: `No pending update found for project ${project}` }, { status: 404 });
        }
        
        // Update status
        approvals[project].status = targetStatus;
        await kv.set('agent_approvals', approvals);

        // Add log entry
        let logs = await kv.get('agent_logs') || [];
        logs.unshift(logEntry);
        await kv.set('agent_logs', logs.slice(0, 300));

        return NextResponse.json({ success: true, status: targetStatus });
      } catch (e) {
        console.error('Vercel KV Approvals Action Error:', e);
      }
    }

    const db = readLocalDb();
    if (!db.approvals[project]) {
      return NextResponse.json({ error: `No pending update found for project ${project}` }, { status: 404 });
    }

    db.approvals[project].status = targetStatus;
    db.logs.unshift(logEntry);
    db.logs = db.logs.slice(0, 300);
    writeLocalDb(db);

    return NextResponse.json({ success: true, status: targetStatus });
  } catch (e) {
    console.error('API Approvals Action error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
