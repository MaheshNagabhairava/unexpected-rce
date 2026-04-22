'use client'

import { useState } from 'react'
import { login } from '../actions'

export default function LoginForm({ onLoginSuccess }) {
    const [error, setError] = useState('')

    async function handleSubmit(formData) {
        const res = await login(formData)

        if (res.success) {
            onLoginSuccess(res.session)
        } else {
            setError(res.error)
        }
    }

    return (
        <div style={{ maxWidth: '300px', margin: '2rem auto', padding: '1rem', border: '1px solid #ccc', borderRadius: '8px' }}>
            <h2 style={{ textAlign: 'center' }}>Login</h2>
            <form action={handleSubmit}>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem' }}>Username:</label>
                    <input type="text" name="username" style={{ width: '100%', padding: '0.5rem' }} />
                </div>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem' }}>Password:</label>
                    <input type="password" name="password" style={{ width: '100%', padding: '0.5rem' }} />
                </div>
                <button type="submit" style={{ width: '100%', padding: '0.5rem', background: '#0070f3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                    Login
                </button>
                {error && <p style={{ color: 'red', marginTop: '1rem', textAlign: 'center' }}>{error}</p>}
            </form>
            <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#666' }}>
                <p>Demo Credentials:</p>
                <ul>
                    <li>admin : password</li>
                    <li>user : secret</li>
                </ul>
            </div>
        </div>
    )
}
