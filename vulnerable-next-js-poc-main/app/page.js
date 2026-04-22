'use client'

import { useState } from 'react'
import LoginForm from './components/LoginForm'
import LogViewer from './components/LogViewer'

export default function Home() {
  const [session, setSession] = useState(null)

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui' }}>
      <header style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h1>Secure Log Dashboard</h1>
        <p>Enterprise Log Monitoring System V1.0</p>
      </header>

      {!session ? (
        <LoginForm onLoginSuccess={setSession} />
      ) : (
        <LogViewer session={session} />
      )}
    </main>
  )
}
