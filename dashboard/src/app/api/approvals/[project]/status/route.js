import { NextResponse } from 'next/server';
import { getApproval, updateApprovalStatus } from '../../../db';

// GET status of a project
export async function GET(request, { params }) {
  const { project } = await params;
  
  try {
    const item = await getApproval(project);
    if (!item) {
      return NextResponse.json({ project, status: 'none' });
    }
    return NextResponse.json({ project, status: item.status, item });
  } catch (e) {
    console.error('API Status GET error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
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

    // Check if project exists
    const item = await getApproval(project);
    if (!item) {
      return NextResponse.json({ error: 'Project not found' }, { status: 404 });
    }

    await updateApprovalStatus(project, status);
    return NextResponse.json({ success: true, status });
  } catch (e) {
    console.error('API Status POST error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
