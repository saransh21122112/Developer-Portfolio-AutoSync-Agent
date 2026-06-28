'use client';

import React, { useState, useEffect, useMemo } from 'react';

export default function Home() {
  const [logs, setLogs] = useState([]);
  const [approvals, setApprovals] = useState({});
  const [selectedProject, setSelectedProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState('');
  
  // Log filtering states
  const [logFilter, setLogFilter] = useState('ALL');
  const [logSearch, setLogSearch] = useState('');

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

  const handleTriggerSync = async () => {
    setSyncing(true);
    setSyncStatus('Triggering...');
    try {
      const res = await fetch('/api/sync-request', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sync_pending: true }),
      });
      if (res.ok) {
        setSyncStatus('Pending Agent...');
        // Wait a few seconds to let it process
        setTimeout(async () => {
          await fetchData();
          setSyncStatus('');
          setSyncing(false);
        }, 5000);
      } else {
        const data = await res.json();
        alert(`Error triggering sync: ${data.error}`);
        setSyncing(false);
      }
    } catch (e) {
      alert(`Sync trigger failed: ${e.message}`);
      setSyncing(false);
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

  // Filtered logs list memoization
  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const matchesFilter = logFilter === 'ALL' || log.level === logFilter;
      const matchesSearch = log.message.toLowerCase().includes(logSearch.toLowerCase()) ||
                            log.level.toLowerCase().includes(logSearch.toLowerCase());
      return matchesFilter && matchesSearch;
    });
  }, [logs, logFilter, logSearch]);

  return (
    <div style={{ padding: '40px 30px', maxWidth: '1400px', margin: '0 auto', boxSizing: 'border-box' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px', flexWrap: 'wrap', gap: '20px' }}>
        <div>
          <h1 style={{ 
            margin: 0, 
            fontSize: '28px', 
            fontWeight: '900', 
            background: 'linear-gradient(135deg, #22d3ee 0%, #3b82f6 50%, #6366f1 100%)', 
            WebkitBackgroundClip: 'text', 
            WebkitTextFillColor: 'transparent',
            letterSpacing: '-0.02em'
          }}>
            PortfolioSyncAgent Panel
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: '6px', fontWeight: '500' }}>
            Real-time deployment pipelines and validation dashboard
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <button
            disabled={syncing}
            onClick={handleTriggerSync}
            style={{
              padding: '12px 24px',
              borderRadius: '10px',
              border: 'none',
              background: syncing 
                ? 'rgba(255, 255, 255, 0.05)' 
                : 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
              color: syncing ? '#64748b' : 'white',
              fontWeight: '700',
              cursor: syncing ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              boxShadow: syncing ? 'none' : '0 4px 20px rgba(6, 182, 212, 0.25)',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: syncing ? 'none' : 'translateY(0)',
            }}
            onMouseEnter={(e) => {
              if (!syncing) {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 24px rgba(6, 182, 212, 0.35)';
              }
            }}
            onMouseLeave={(e) => {
              if (!syncing) {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 20px rgba(6, 182, 212, 0.25)';
              }
            }}
          >
            {syncing ? (syncStatus || 'Triggering...') : 'Run Sync Now'}
          </button>
          
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '10px', 
            backgroundColor: 'rgba(255,255,255,0.03)', 
            padding: '8px 16px', 
            borderRadius: '20px', 
            border: '1px solid rgba(255,255,255,0.05)'
          }}>
            <span className={activeAgentStatus === 'ACTIVE' ? 'pulse-active' : ''} style={{
              display: 'inline-block',
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: activeAgentStatus === 'ACTIVE' ? '#10b981' : '#64748b',
              boxShadow: activeAgentStatus === 'ACTIVE' ? '0 0 10px #10b981' : 'none',
              transition: 'all 0.3s'
            }} />
            <span style={{ 
              fontSize: '13px', 
              fontWeight: '700', 
              color: activeAgentStatus === 'ACTIVE' ? '#10b981' : '#94a3b8',
              letterSpacing: '0.05em'
            }}>
              {activeAgentStatus}
            </span>
          </div>
        </div>
      </header>

      {/* Stats Grid */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '40px' }}>
        <div className="glass-card" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: '#22d3ee' }} />
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Total Syncs</div>
          <div style={{ fontSize: '36px', fontWeight: '900', marginTop: '12px', color: '#f8fafc', fontFamily: 'monospace' }}>{totalRuns}</div>
        </div>
        <div className="glass-card" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: '#f59e0b' }} />
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Pending Approvals</div>
          <div style={{ fontSize: '36px', fontWeight: '900', marginTop: '12px', color: '#f8fafc', fontFamily: 'monospace' }}>{pendingApprovalsList.length}</div>
        </div>
        <div className="glass-card" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: '#10b981' }} />
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Sync Successes</div>
          <div style={{ fontSize: '36px', fontWeight: '900', marginTop: '12px', color: '#f8fafc', fontFamily: 'monospace' }}>{successCount}</div>
        </div>
        <div className="glass-card" style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: '#ef4444' }} />
          <div style={{ fontSize: '13px', fontWeight: '700', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Logged Errors</div>
          <div style={{ fontSize: '36px', fontWeight: '900', marginTop: '12px', color: '#f8fafc', fontFamily: 'monospace' }}>{errorCount}</div>
        </div>
      </section>

      {/* Main Content Layout */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '120px 0', color: '#94a3b8', flexDirection: 'column', gap: '20px' }}>
          <span className="pulse-active" style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'rgba(99, 102, 241, 0.15)', border: '2px solid #6366f1' }} />
          <span style={{ fontWeight: '500', fontSize: '15px' }}>Loading telemetry stream...</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1.65fr 1fr', gap: '30px', alignItems: 'start' }}>
          {/* Left Side: Pending approvals and details */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
            {/* Approvals List */}
            <div className="glass-card" style={{ padding: '28px', minHeight: '260px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', marginBottom: '22px', color: '#f8fafc', letterSpacing: '-0.01em' }}>
                Pending Review Queue
              </h2>
              {pendingApprovalsList.length === 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '50px 0', color: '#64748b', fontSize: '14px', gap: '12px' }}>
                  <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                  </svg>
                  <span>All portfolios are fully synchronized. No pending approvals.</span>
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
                        padding: '16px 20px', 
                        borderRadius: '10px', 
                        background: selectedProject === app.project ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.01)',
                        border: selectedProject === app.project ? '1px solid rgba(99, 102, 241, 0.3)' : '1px solid rgba(255, 255, 255, 0.03)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease-in-out'
                      }}
                      onMouseEnter={(e) => {
                        if (selectedProject !== app.project) {
                          e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (selectedProject !== app.project) {
                          e.currentTarget.style.background = 'rgba(255,255,255,0.01)';
                          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.03)';
                        }
                      }}
                    >
                      <div>
                        <h4 style={{ margin: 0, fontSize: '15px', color: '#f8fafc', fontWeight: '700' }}>{app.project}</h4>
                        <span style={{ fontSize: '12px', color: '#64748b', marginTop: '4px', display: 'inline-block' }}>
                          Detected: {new Date(app.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <span style={{ 
                        fontSize: '11px', 
                        fontWeight: '700', 
                        backgroundColor: 'rgba(245, 158, 11, 0.1)', 
                        color: '#f59e0b',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        border: '1px solid rgba(245, 158, 11, 0.15)',
                        letterSpacing: '0.02em'
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
              <div className="glass-card" style={{ padding: '28px', borderTop: '2px solid #6366f1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '22px', flexWrap: 'wrap', gap: '15px' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '18px', color: '#f8fafc', fontWeight: '800' }}>
                      Verify Portfolio Changes: {selectedProject}
                    </h3>
                    <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: '#94a3b8' }}>
                      Repository URL: <a href={approvals[selectedProject].metadata?.url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none', fontWeight: '600' }}>{approvals[selectedProject].metadata?.url}</a>
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button 
                      disabled={actioning}
                      onClick={() => handleAction(selectedProject, 'reject')}
                      style={{ 
                        padding: '10px 20px', 
                        borderRadius: '8px', 
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        background: 'rgba(239, 68, 68, 0.08)',
                        color: '#ef4444',
                        fontWeight: '700',
                        cursor: 'pointer',
                        fontSize: '13px',
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.08)' }}
                    >
                      Discard
                    </button>
                    <button 
                      disabled={actioning}
                      onClick={() => handleAction(selectedProject, 'approve')}
                      style={{ 
                        padding: '10px 20px', 
                        borderRadius: '8px', 
                        border: 'none',
                        background: 'linear-gradient(to right, #10b981, #059669)',
                        color: 'white',
                        fontWeight: '700',
                        cursor: 'pointer',
                        fontSize: '13px',
                        boxShadow: '0 4px 14px rgba(16, 185, 129, 0.25)',
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 6px 18px rgba(16, 185, 129, 0.35)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '0 4px 14px rgba(16, 185, 129, 0.25)' }}
                    >
                      {actioning ? 'Pushing...' : 'Approve & Push'}
                    </button>
                  </div>
                </div>

                <div style={{ 
                  backgroundColor: '#020617', 
                  border: '1px solid #1e293b', 
                  borderRadius: '10px', 
                  padding: '24px', 
                  fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace', 
                  fontSize: '13px', 
                  whiteSpace: 'pre-wrap', 
                  color: '#cbd5e1',
                  maxHeight: '450px',
                  overflowY: 'auto',
                  lineHeight: '1.6',
                  boxShadow: 'inset 0 4px 20px rgba(0,0,0,0.5)'
                }}>
                  {approvals[selectedProject].diff.split('\n').map((line, idx) => {
                    let style = { padding: '2px 8px', borderRadius: '2px', margin: '1px 0' };
                    // Polyfill startsWith check safely
                    const isAdd = line.indexOf('+') === 0 && line.indexOf('+++') !== 0;
                    const isDel = line.indexOf('-') === 0 && line.indexOf('---') !== 0;
                    const isMeta = line.indexOf('+++') === 0 || line.indexOf('---') === 0 || line.indexOf('@@') === 0;
                    if (isAdd) {
                      style = { ...style, color: '#4ade80', backgroundColor: 'rgba(74, 222, 128, 0.08)' };
                    } else if (isDel) {
                      style = { ...style, color: '#f87171', backgroundColor: 'rgba(248, 113, 113, 0.08)' };
                    } else if (isMeta) {
                      style = { ...style, color: '#818cf8', backgroundColor: 'rgba(99, 102, 241, 0.05)', fontWeight: 'bold' };
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
          <div className="glass-card" style={{ padding: '28px', display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '22px', flexWrap: 'wrap', gap: '10px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: '800', color: '#f8fafc', letterSpacing: '-0.01em' }}>
                Execution Stream
              </h2>
              {/* Log filter pills */}
              <div style={{ display: 'flex', gap: '5px', backgroundColor: 'rgba(0,0,0,0.2)', padding: '3px', borderRadius: '8px' }}>
                {['ALL', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setLogFilter(lvl)}
                    style={{
                      padding: '4px 10px',
                      fontSize: '11px',
                      fontWeight: '700',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      background: logFilter === lvl ? '#3b82f6' : 'transparent',
                      color: logFilter === lvl ? 'white' : '#64748b',
                      transition: 'all 0.2s'
                    }}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Log Search input */}
            <div style={{ marginBottom: '18px', position: 'relative' }}>
              <input
                type="text"
                placeholder="Search logs..."
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: 'rgba(0, 0, 0, 0.25)',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                  borderRadius: '8px',
                  padding: '10px 14px 10px 34px',
                  color: 'white',
                  fontSize: '13px',
                  outline: 'none',
                  transition: 'border-color 0.2s'
                }}
                onFocus={(e) => e.target.style.borderColor = 'rgba(99, 102, 241, 0.4)'}
                onBlur={(e) => e.target.style.borderColor = 'rgba(255, 255, 255, 0.05)'}
              />
              <svg 
                style={{ position: 'absolute', left: '12px', top: '12px', color: '#475569' }} 
                width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
              </svg>
              {logSearch && (
                <button
                  onClick={() => setLogSearch('')}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '8px',
                    background: 'transparent',
                    border: 'none',
                    color: '#64748b',
                    fontSize: '16px',
                    cursor: 'pointer'
                  }}
                >
                  &times;
                </button>
              )}
            </div>

            {filteredLogs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '50px 0', color: '#64748b', fontSize: '14px' }}>
                {logs.length === 0 ? 'No active execution steps recorded.' : 'No logs match filters.'}
              </div>
            ) : (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '12px', 
                maxHeight: '520px', 
                overflowY: 'auto',
                paddingRight: '5px'
              }}>
                {filteredLogs.map((log, idx) => {
                  let badgeColor = '#94a3b8';
                  let badgeBg = 'rgba(148, 163, 184, 0.08)';
                  
                  if (log.level === 'ERROR') {
                    badgeColor = '#f87171';
                    badgeBg = 'rgba(239, 68, 68, 0.12)';
                  } else if (log.level === 'WARNING') {
                    badgeColor = '#fbbf24';
                    badgeBg = 'rgba(245, 158, 11, 0.12)';
                  } else if (log.level === 'INFO') {
                    badgeColor = '#60a5fa';
                    badgeBg = 'rgba(59, 130, 246, 0.12)';
                  }

                  return (
                    <div 
                      key={idx} 
                      style={{ 
                        padding: '14px', 
                        borderRadius: '8px', 
                        background: 'rgba(255,255,255,0.01)', 
                        border: '1px solid rgba(255,255,255,0.03)',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <span style={{ 
                          fontSize: '10px', 
                          fontWeight: '800', 
                          color: badgeColor,
                          backgroundColor: badgeBg,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          border: `1px solid ${badgeBg}`,
                          letterSpacing: '0.04em'
                        }}>
                          {log.level}
                        </span>
                        <span style={{ fontSize: '11px', color: '#64748b', fontWeight: '500' }}>
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p style={{ 
                        margin: 0, 
                        fontSize: '13px', 
                        color: '#cbd5e1', 
                        lineHeight: '1.5', 
                        fontFamily: '"SFMono-Regular", Consolas, monospace',
                        lineBreak: 'anywhere' 
                      }}>
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
