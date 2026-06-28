import { NextResponse } from 'next/server';
import { getApprovals, saveApproval } from '../db';

export async function GET() {
  try {
    const approvals = await getApprovals();
    return NextResponse.json(approvals);
  } catch (e) {
    console.error('API Approvals GET error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
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

    await saveApproval(project, pendingItem);
    return NextResponse.json({ success: true, item: pendingItem });
  } catch (e) {
    console.error('API Approvals POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
