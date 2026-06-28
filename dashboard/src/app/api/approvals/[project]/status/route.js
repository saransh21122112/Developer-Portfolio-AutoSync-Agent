import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';
import { isKvConfigured, readLocalDb, writeLocalDb } from '../../../../db';

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
