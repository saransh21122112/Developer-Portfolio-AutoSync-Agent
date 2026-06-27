'use client';

import React, { useState, useEffect } from 'react';

export default function Home() {
  const [logs, setLogs] = useState([]);
  const [approvals, setApprovals] = useState({});
  const [selectedProject, setSelectedProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState(false);

  // Poll data from local APIs
  const fetchData = async () => {
    try {
      // Fetch Logs
      const logsRes = await fetch('/api/logs');
      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setLogs(logsData);
      }

      // Fetch Approvals
      const approvalsRes = await fetch('/api/approvals');
      if (approvalsRes.ok) {
        const approvalsData = await approvalsRes.json();
        setApprovals(approvalsData);
      }
    } catch (e) {
      console.error('Failed to poll dashboard data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (project, action) => {
    setActioning(true);
    try {
      const res = await fetch('/api/approvals/action', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ project, action }),
      });
      if (res.ok) {
        await fetchData();
        if (selectedProject === project) {
          setSelectedProject(null);
        }
      } else {
        const data = await res.json();
        alert(`Error executing action: ${data.error}`);
      }
    } catch (e) {
      alert(`Action failed: ${e.message}`);
    } finally {
      setActioning(false);
    }
  };

  // Calculations for stats
  const pendingApprovalsList = Object.values(approvals).filter(
    (app) => app.status === 'pending'
  );
  
  const totalRuns = logs.filter(
    (log) => log.message.includes('Executing one-off poll') || log.message.includes('Orchestrating flow')
  ).length || Object.keys(approvals).length;

  const errorCount = logs.filter((log) => log.level === 'ERROR').length;
  const successCount = logs.filter(
    (log) => log.message.includes('successfully') || log.message.includes('succeeded')
  ).length;

  const activeAgentStatus = logs.length > 0 && 
    (new Date() - new Date(logs[0].timestamp)) < 15000 && 
    !logs[0].message.includes('completed') ? 'ACTIVE' : 'IDLE';

  return (
    <div style={{ padding: '30px', maxWidth: '1400px', margin: '0 auto', boxSizing: 'border-box' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '35px' }}>
        <div>
          <h1 style={{ 
            margin: 0, 
            fontSize: '26px', 
            fontWeight: '800', 
            background: 'linear-gradient(to right, #22d3ee, #6366f1)', 
            WebkitBackgroundClip: 'text', 
            WebkitTextFillColor: 'transparent' 
          }}>
            PortfolioSyncAgent Panel
          </h1>
          <p style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
            Real-time deployment pipelines and validation dashboard
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            display: 'inline-block',
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: activeAgentStatus === 'ACTIVE' ? '#10b981' : '#6366f1',
            boxShadow: activeAgentStatus === 'ACTIVE' ? '0 0 10px #10b981' : '0 0 10px #6366f1'
          }} />
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: activeAgentStatus === 'ACTIVE' ? '#10b981' : '#818cf8' }}>
            {activeAgentStatus}
          </span>
        </div>
      </header>

      {/* Stats Grid */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '35px' }}>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Syncs</div>
          <div style={{ fontSize: '32px', fontWeight: '800', marginTop: '10px', color: '#22d3ee' }}>{totalRuns}</div>
        </div>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pending Approvals</div>
          <div style={{ fontSize: '32px', fontWeight: '800', marginTop: '10px', color: '#f59e0b' }}>{pendingApprovalsList.length}</div>
        </div>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sync Successes</div>
          <div style={{ fontSize: '32px', fontWeight: '800', marginTop: '10px', color: '#10b981' }}>{successCount}</div>
        </div>
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Logged Errors</div>
          <div style={{ fontSize: '32px', fontWeight: '800', marginTop: '10px', color: '#ef4444' }}>{errorCount}</div>
        </div>
      </section>

      {/* Main Content Layout */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '100px 0', color: '#64748b' }}>Loading dashboard telemetry...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '30px' }}>
          {/* Left Side: Pending approvals and details */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
            {/* Approvals List */}
            <div className="glass-card" style={{ padding: '25px', minHeight: '300px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '20px', color: '#f8fafc' }}>
                Pending Review Queue
              </h2>
              {pendingApprovalsList.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '50px 0', color: '#64748b', fontSize: '14px' }}>
                  No updates require approval. All portfolios are synchronized.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {pendingApprovalsList.map((app) => (
                    <div 
                      key={app.project} 
                      onClick={() => setSelectedProject(app.project)}
                      style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center', 
                        padding: '16px', 
                        borderRadius: '8px', 
                        background: selectedProject === app.project ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                        border: selectedProject === app.project ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(255, 255, 255, 0.05)',
                        cursor: 'pointer',
                        transition: 'background 0.2s'
                      }}
                    >
                      <div>
                        <h4 style={{ margin: 0, fontSize: '15px', color: '#f8fafc' }}>{app.project}</h4>
                        <span style={{ fontSize: '12px', color: '#64748b' }}>
                          Detected: {new Date(app.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <span style={{ 
                        fontSize: '11px', 
                        fontWeight: 'bold', 
                        backgroundColor: 'rgba(245, 158, 11, 0.15)', 
                        color: '#f59e0b',
                        padding: '4px 8px',
                        borderRadius: '4px'
                      }}>
                        Awaiting Verification
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Approval Details (Diff Viewer) */}
            {selectedProject && approvals[selectedProject] && (
              <div className="glass-card" style={{ padding: '25px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '18px', color: '#f8fafc' }}>
                      Verify Portfolio Changes: {selectedProject}
                    </h3>
                    <p style={{ margin: '5px 0 0 0', fontSize: '13px', color: '#64748b' }}>
                      URL: <a href={approvals[selectedProject].metadata?.url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8' }}>{approvals[selectedProject].metadata?.url}</a>
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button 
                      disabled={actioning}
                      onClick={() => handleAction(selectedProject, 'reject')}
                      style={{ 
                        padding: '8px 16px', 
                        borderRadius: '6px', 
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        background: 'rgba(239, 68, 68, 0.1)',
                        color: '#ef4444',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        fontSize: '13px'
                      }}
                    >
                      Discard
                    </button>
                    <button 
                      disabled={actioning}
                      onClick={() => handleAction(selectedProject, 'approve')}
                      style={{ 
                        padding: '8px 16px', 
                        borderRadius: '6px', 
                        border: 'none',
                        background: 'linear-gradient(to right, #10b981, #059669)',
                        color: 'white',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        fontSize: '13px'
                      }}
                    >
                      {actioning ? 'Pushing...' : 'Approve & Push'}
                    </button>
                  </div>
                </div>

                <div style={{ 
                  backgroundColor: '#020617', 
                  border: '1px solid #1e293b', 
                  borderRadius: '8px', 
                  padding: '20px', 
                  fontFamily: 'monospace', 
                  fontSize: '13px', 
                  whiteSpace: 'pre-wrap', 
                  color: '#cbd5e1',
                  maxHeight: '400px',
                  overflowY: 'auto'
                }}>
                  {approvals[selectedProject].diff.split('\n').map((line, idx) => {
                    let style = {};
                    if (line.startsWith('+') && !line.startsWith('+++')) {
                      style = { color: '#4ade80', backgroundColor: 'rgba(74, 222, 128, 0.05)' };
                    } else if (line.startsWith('-') && !line.startsWith('---')) {
                      style = { color: '#f87171', backgroundColor: 'rgba(248, 113, 113, 0.05)' };
                    }
                    return (
                      <div key={idx} style={style}>
                        {line}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right Side: Live Logs */}
          <div className="glass-card" style={{ padding: '25px', display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '700', marginBottom: '20px', color: '#f8fafc' }}>
              Execution Stream
            </h2>
            {logs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '50px 0', color: '#64748b', fontSize: '14px' }}>
                No active execution steps recorded yet.
              </div>
            ) : (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '12px', 
                maxHeight: '600px', 
                overflowY: 'auto',
                paddingRight: '5px'
              }}>
                {logs.map((log, idx) => {
                  let badgeColor = '#64748b';
                  let badgeBg = 'rgba(100, 116, 139, 0.1)';
                  
                  if (log.level === 'ERROR') {
                    badgeColor = '#ef4444';
                    badgeBg = 'rgba(239, 68, 68, 0.15)';
                  } else if (log.level === 'WARNING') {
                    badgeColor = '#f59e0b';
                    badgeBg = 'rgba(245, 158, 11, 0.15)';
                  } else if (log.level === 'INFO') {
                    badgeColor = '#3b82f6';
                    badgeBg = 'rgba(59, 130, 246, 0.15)';
                  }

                  return (
                    <div 
                      key={idx} 
                      style={{ 
                        padding: '12px', 
                        borderRadius: '6px', 
                        background: 'rgba(255,255,255,0.01)', 
                        border: '1px solid rgba(255,255,255,0.03)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ 
                          fontSize: '10px', 
                          fontWeight: 'bold', 
                          color: badgeColor,
                          backgroundColor: badgeBg,
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}>
                          {log.level}
                        </span>
                        <span style={{ fontSize: '11px', color: '#64748b' }}>
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: '13px', color: '#e2e8f0', lineBreak: 'anywhere' }}>
                        {log.message}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
