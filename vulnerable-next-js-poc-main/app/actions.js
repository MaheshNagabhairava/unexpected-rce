'use server'

const VALID_USERS = {
  'admin': 'password',
  'user': 'secret'
}

export async function login(formData) {
  const username = formData.get('username')
  const password = formData.get('password')

  if (VALID_USERS[username] && VALID_USERS[username] === password) {
    // Return a session object that the client must store and send back
    // This object is the vector for the RCE vulnerability when sent back to refreshLogs
    return {
      success: true,
      session: {
        user: username,
        role: username === 'admin' ? 'admin' : 'viewer',
        token: Buffer.from(`${username}:${Date.now()}`).toString('base64')
      }
    }
  }

  return { success: false, error: 'Invalid credentials' }
}

export async function refreshLogs(sessionObject) {
  // VULNERABLE: The 'sessionObject' is deserialized by Next.js before this function runs.
  // This allows the prototype pollution RCE attack vector (CVE-2025-55182).

  if (!sessionObject || !sessionObject.user) {
    return { error: 'Unauthorized' }
  }

  try {
    // Generate noise/dummy traffic so logs look realistic
    await Promise.all([
      fetch('http://localhost:5000/system.info', { cache: 'no-store' }).catch(() => { }),
      fetch('http://localhost:5000/metrics', { cache: 'no-store' }).catch(() => { }),
      fetch('http://localhost:5000/config.json', { cache: 'no-store' }).catch(() => { }),
      fetch('http://localhost:5000/users.db', { cache: 'no-store' }).catch(() => { }),
      fetch('http://localhost:5000/dashboard.xml', { cache: 'no-store' }).catch(() => { }),
      fetch('http://localhost:5000/auth.key', { cache: 'no-store' }).catch(() => { })
    ])

    // Fetch the access.log file that log_server.py writes to
    const res = await fetch('http://localhost:5000/access.log', { cache: 'no-store' })
    const text = await res.text()
    // Split text into lines for the viewer
    const logs = text.split('\n').filter(line => line.trim() !== '')
    return { logs }
  } catch (error) {
    return { logs: [`ERROR: Could not fetch from port 5000 - ${error.message}`] }
  }
}
