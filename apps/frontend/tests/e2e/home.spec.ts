import { test, expect } from '@playwright/test'

test.describe('Home page', () => {
  test('displays hero section', async ({ page }) => {
    await page.goto('/')
    
    await expect(page.getByRole('heading', { name: /rendez visible/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /créer ma première fiche/i })).toBeVisible()
  })
  
  test('navigation links work', async ({ page }) => {
    await page.goto('/')
    
    await expect(page.getByRole('link', { name: 'Accueil' })).toBeVisible()
    await expect(page.getByRole('link', { name: /tableau de bord/i })).toBeVisible()
  })
})
