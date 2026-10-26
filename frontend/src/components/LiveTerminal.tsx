import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Terminal, X, Copy, Trash2, CheckCircle, 
  XCircle, AlertCircle, PlayCircle, SkipForward,
  Info
} from 'lucide-react';
import { tokenStore } from '../lib/api';

export interface LiveTerminalProps {
  jobId: string;
  isOpen: boolean;
  onClose: () => void;
}

interface LogEntry {
  id: string;
  type: string;
  timestamp: string;
  message: string;
  level?: string;
  node_id?: string;
  agent_type?: string;
}

export function LiveTerminal({ jobId, isOpen, onClose }: LiveTerminalProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // SSE connection management
  useEffect(() => {
    if (!isOpen || !jobId) return;

    let retryTimeout: ReturnType<typeof setTimeout>;

    const connectSSE = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      setStatus('connecting');
      const token = tokenStore.getAccess();
      const url = `/api/v1/execution-stream/${jobId}?token=${token}`;
      
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setStatus('connected');
      };

      eventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        setStatus('disconnected');
        eventSource.close();
        // Reconnect after 3 seconds
        retryTimeout = setTimeout(connectSSE, 3000);
      };

      const handleEvent = (type: string, data: string) => {
        if (type === 'heartbeat') return; // Heartbeats just keep connection alive

        try {
          const parsed = JSON.parse(data);
          setLogs(prev => [...prev, {
            id: Math.random().toString(36).substring(7),
            type,
            timestamp: parsed.timestamp || new Date().toISOString(),
            message: parsed.message || JSON.stringify(parsed),
            level: parsed.level,
            node_id: parsed.node_id,
            agent_type: parsed.agent_type,
          }]);
        } catch (e) {
          // Fallback if not JSON
          setLogs(prev => [...prev, {
            id: Math.random().toString(36).substring(7),
            type,
            timestamp: new Date().toISOString(),
            message: data,
          }]);
        }
      };

      // Listen to specific custom events
      const eventTypes = [
        'message', 'log', 'task_start', 'task_complete', 
        'task_error', 'task_skipped', 'execution_complete', 
        'execution_paused', 'heartbeat'
      ];

      eventTypes.forEach(eventType => {
        eventSource.addEventListener(eventType, (e: MessageEvent) => {
          handleEvent(eventType === 'message' ? 'log' : eventType, e.data);
        });
      });
    };

    connectSSE();

    return () => {
      clearTimeout(retryTimeout);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [isOpen, jobId]);

  const handleCopyLogs = () => {
    const text = logs.map(l => `[${new Date(l.timestamp).toLocaleTimeString()}] [${l.type}] ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
  };

  const handleClear = () => {
    setLogs([]);
  };

  // UI Helpers
  const getEventIcon = (type: string) => {
    switch(type) {
      case 'task_start': return <PlayCircle size={14} style={{ color: '#58a6ff', marginRight: '6px' }} />;
      case 'task_complete': return <CheckCircle size={14} style={{ color: '#238636', marginRight: '6px' }} />;
      case 'task_error': return <XCircle size={14} style={{ color: '#f85149', marginRight: '6px' }} />;
      case 'task_skipped': return <SkipForward size={14} style={{ color: '#d29922', marginRight: '6px' }} />;
      case 'execution_complete': return <CheckCircle size={14} style={{ color: '#2ea043', marginRight: '6px' }} />;
      case 'execution_paused': return <AlertCircle size={14} style={{ color: '#d29922', marginRight: '6px' }} />;
      case 'log':
      default: return <Info size={14} style={{ color: '#8b949e', marginRight: '6px' }} />;
    }
  };

  const getEventColor = (type: string, level?: string) => {
    if (type === 'task_start') return '#58a6ff';
    if (type === 'task_complete' || type === 'execution_complete') return '#238636';
    if (type === 'task_error' || level === 'error') return '#f85149';
    if (type === 'task_skipped' || type === 'execution_paused' || level === 'warning') return '#d29922';
    return '#8b949e';
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: '400px', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: '#0d1117',
            color: '#c9d1d9',
            fontFamily: '"JetBrains Mono", "Fira Code", "Courier New", Courier, monospace',
            display: 'flex',
            flexDirection: 'column',
            borderTop: '1px solid #30363d',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 16px',
            backgroundColor: '#161b22',
            borderBottom: '1px solid #30363d',
            fontSize: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Terminal size={14} />
                <span style={{ fontWeight: 600 }}>Live Execution Logs</span>
              </div>
              
              {/* Status Indicator */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: status === 'connected' ? '#238636' : status === 'connecting' ? '#d29922' : '#f85149',
                  boxShadow: status === 'connected' ? '0 0 8px #238636' : 'none',
                  animation: status === 'connected' ? 'terminal-pulse 2s infinite' : 'none'
                }} />
                <span style={{ color: '#8b949e' }}>
                  {status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : 'Disconnected'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button 
                onClick={handleCopyLogs} 
                title="Copy Logs" 
                style={{...iconButtonStyle, opacity: logs.length ? 1 : 0.5}}
                disabled={!logs.length}
              >
                <Copy size={14} />
              </button>
              <button 
                onClick={handleClear} 
                title="Clear Logs" 
                style={{...iconButtonStyle, opacity: logs.length ? 1 : 0.5}}
                disabled={!logs.length}
              >
                <Trash2 size={14} />
              </button>
              <div style={{ width: '1px', height: '14px', backgroundColor: '#30363d', margin: '0 4px' }} />
              <button onClick={onClose} title="Close Terminal" style={iconButtonStyle}>
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Logs Area */}
          <div className="terminal-scroll" style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px 16px',
            fontSize: '13px',
            lineHeight: 1.5,
          }}>
            {logs.length === 0 ? (
              <div style={{ color: '#8b949e', fontStyle: 'italic', textAlign: 'center', marginTop: '20px' }}>
                Waiting for logs...
              </div>
            ) : (
              logs.map((log) => {
                const color = getEventColor(log.type, log.level);
                const isBanner = log.type === 'execution_complete' || log.type === 'execution_paused';

                if (isBanner) {
                  return (
                    <div key={log.id} style={{
                      margin: '12px 0',
                      padding: '12px',
                      backgroundColor: log.type === 'execution_complete' ? 'rgba(35, 134, 54, 0.1)' : 'rgba(210, 153, 34, 0.1)',
                      border: `1px solid ${color}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}>
                      {getEventIcon(log.type)}
                      <span style={{ color, fontWeight: 600 }}>{log.message}</span>
                    </div>
                  );
                }

                return (
                  <div key={log.id} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    marginBottom: '6px',
                    wordBreak: 'break-word',
                  }}>
                    <span style={{ color: '#3fb950', marginRight: '12px', flexShrink: 0, opacity: 0.8 }}>
                      [{new Date(log.timestamp).toLocaleTimeString()}]
                    </span>
                    <span style={{ 
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(255,255,255,0.05)',
                      color: color,
                      fontSize: '11px',
                      marginRight: '12px',
                      flexShrink: 0,
                      minWidth: '120px',
                      fontWeight: 500,
                    }}>
                      {getEventIcon(log.type)}
                      {log.type.replace('_', ' ')}
                    </span>
                    <span style={{ color: '#c9d1d9' }}>
                      {log.message}
                      {log.agent_type && (
                        <span style={{ color: '#8b949e', marginLeft: '8px', fontSize: '12px' }}>
                          [{log.agent_type}]
                        </span>
                      )}
                    </span>
                  </div>
                );
              })
            )}
            <div ref={logsEndRef} />
          </div>

          <style>{`
            @keyframes terminal-pulse {
              0% { opacity: 1; transform: scale(1); }
              50% { opacity: 0.5; transform: scale(0.85); }
              100% { opacity: 1; transform: scale(1); }
            }
            
            .terminal-scroll::-webkit-scrollbar {
              width: 10px;
            }
            .terminal-scroll::-webkit-scrollbar-track {
              background: #0d1117;
            }
            .terminal-scroll::-webkit-scrollbar-thumb {
              background: #30363d;
              border-radius: 5px;
            }
            .terminal-scroll::-webkit-scrollbar-thumb:hover {
              background: #484f58;
            }
          `}</style>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const iconButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#8b949e',
  cursor: 'pointer',
  padding: '6px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: '4px',
  transition: 'all 0.2s',
  outline: 'none',
};

export default LiveTerminal;
