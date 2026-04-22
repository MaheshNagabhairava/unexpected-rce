'use client'

import { useState, useEffect } from 'react'
import { refreshLogs } from '../actions'

export default function LogViewer({ session }) {
    const [logs, setLogs] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        // Initial load
        fetchLogs()

        // Poll every 3 seconds
        const interval = setInterval(fetchLogs, 3000)
        return () => clearInterval(interval)
    }, [session])

    async function fetchLogs() {
        try {
            // VULNERABLE: We send the 'session' object back to the server action.
            // This serialization/deserialization path is what 'exploit.py' will target.
            const res = await refreshLogs(session)
            if (res.logs) {
                setLogs(res.logs)
            }
        } catch (err) {
            console.error('Failed to fetch logs:', err)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{ maxWidth: '800px', margin: '2rem auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2>Server Logs (Port 5000)</h2>
                <span style={{ fontSize: '0.9rem', color: '#666' }}>
                    Logged in as: <strong>{session.user}</strong>
                </span>
            </div>

            <div style={{
                background: '#1e1e1e',
                color: '#00ff00',
                padding: '1rem',
                borderRadius: '8px',
                fontFamily: 'monospace',
                height: '400px',
                overflowY: 'auto'
            }}>
                {loading && logs.length === 0 ? (
                    <p>Connecting to log server...</p>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} style={{ marginBottom: '0.5rem', borderBottom: '1px solid #333' }}>
                            {log}
                        </div>
                    ))
                )}
            </div>
            <p style={{ textAlign: 'center', color: '#666', marginTop: '1rem' }}>
                Logs auto-refresh every 3s
            </p>
        </div>
    )
}
