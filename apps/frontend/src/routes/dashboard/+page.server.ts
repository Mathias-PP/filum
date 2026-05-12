import type { PageServerLoad } from './$types'

export const load: PageServerLoad = async ({ fetch, parent }) => {
  const { user } = await parent()
  
  if (!user) {
    return { redirect: '/api/v1/auth/login' }
  }
  
  return { user }
}
