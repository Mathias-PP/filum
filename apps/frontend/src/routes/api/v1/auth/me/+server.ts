import type { RequestHandler } from '@sveltejs/kit'

export const GET: RequestHandler = async ({ fetch }) => {
  try {
    const response = await fetch('/api/v1/auth/me', {
      credentials: 'include'
    })
    
    if (response.ok) {
      const user = await response.json()
      return new Response(JSON.stringify(user), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    }
    
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    })
  } catch {
    return new Response(JSON.stringify({ error: 'Server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
}
