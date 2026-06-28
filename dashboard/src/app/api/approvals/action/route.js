import { NextResponse } from 'next/server';
import { getApproval, updateApprovalStatus, addLog } from '../../db';

export async function POST(request) {
  try {
    const body = await request.json();
    const { project, action } = body; // action is either 'approve' or 'reject'

    if (!project || !['approve', 'reject'].includes(action)) {
      return NextResponse.json({ error: 'Project name and action ("approve"/"reject") are required' }, { status: 400 });
    }

    const targetStatus = action === 'approve' ? 'approved' : 'rejected';
    
    // Check if project exists
    const approvalItem = await getApproval(project);
    if (!approvalItem) {
      return NextResponse.json({ error: `No pending update found for project ${project}` }, { status: 404 });
    }

    // Update status
    await updateApprovalStatus(project, targetStatus);

    // Add log entry
    const logMessage = `User ${action === 'approve' ? 'approved' : 'rejected'} the portfolio update for project '${project}'.`;
    const logEntry = {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      name: 'DashboardUI',
      message: logMessage
    };
    await addLog(logEntry);

    return NextResponse.json({ success: true, status: targetStatus });
  } catch (e) {
    console.error('API Approvals Action error:', e);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
