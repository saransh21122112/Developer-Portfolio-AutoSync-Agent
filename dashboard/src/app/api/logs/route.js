import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';
import { isKvConfigured, readLocalDb, writeLocalDb } from '../db';

export async function GET() {
  if (isKvConfigured) {
    try {
      const logs = await kv.get('agent_logs') || [];
      return NextResponse.json(logs);
    } catch (e) {
      console.error('Vercel KV Error:', e);
    }
  }

  // Fallback to local DB
  const db = readLocalDb();
  return NextResponse.json(db.logs);
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { timestamp, level, name, message } = body;
    
    if (!message) {
      return NextResponse.json({ error: 'Message is required' }, { status: 400 });
    }

    const logEntry = {
      timestamp: timestamp || new Date().toISOString(),
      level: level || 'INFO',
      name: name || 'Agent',
      message
    };

    if (isKvConfigured) {
      try {
        let logs = await kv.get('agent_logs') || [];
        logs.unshift(logEntry); // Add to beginning
        logs = logs.slice(0, 300); // Cap at 300 entries
        await kv.set('agent_logs', logs);
        return NextResponse.json({ success: true, entry: logEntry });
      } catch (e) {
        console.error('Vercel KV Write Error:', e);
      }
    }

    // Fallback write to local DB
    const db = readLocalDb();
    db.logs.unshift(logEntry);
    db.logs = db.logs.slice(0, 300);
    writeLocalDb(db);

    return NextResponse.json({ success: true, entry: logEntry });
  } catch (e) {
    console.error('API Log POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
