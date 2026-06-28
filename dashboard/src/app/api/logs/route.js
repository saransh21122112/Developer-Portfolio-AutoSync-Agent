import { NextResponse } from 'next/server';
import { getLogs, addLog } from '../db';

export async function GET() {
  try {
    const logs = await getLogs();
    return NextResponse.json(logs);
  } catch (e) {
    console.error('API Logs GET error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
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

    await addLog(logEntry);
    return NextResponse.json({ success: true, entry: logEntry });
  } catch (e) {
    console.error('API Log POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
