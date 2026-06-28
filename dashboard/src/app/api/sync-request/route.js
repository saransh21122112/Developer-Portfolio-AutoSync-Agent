import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';
import { isKvConfigured, readLocalDb, writeLocalDb } from '../db';

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
