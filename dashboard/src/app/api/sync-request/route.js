import { NextResponse } from 'next/server';
import { getSyncPending, setSyncPending } from '../db';

export async function GET() {
  try {
    const syncPending = await getSyncPending();
    return NextResponse.json({ sync_pending: syncPending });
  } catch (e) {
    console.error('API sync-request GET error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const { sync_pending } = body;

    if (sync_pending === undefined) {
      return NextResponse.json({ error: 'sync_pending boolean is required' }, { status: 400 });
    }

    await setSyncPending(sync_pending);
    return NextResponse.json({ success: true, sync_pending });
  } catch (e) {
    console.error('API sync-request POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
