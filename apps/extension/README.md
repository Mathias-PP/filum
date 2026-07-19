# Extension navigateur Philum (MV3)

Ajoute la page courante comme source d'une de vos fiches Philum, en un clic.

## Installation (mode développeur, non publiée sur le Chrome Web Store)

1. Ouvrir `chrome://extensions` (ou `edge://extensions`)
2. Activer le **mode développeur** (coin haut droit)
3. **Charger l'extension non empaquetée** → sélectionner ce dossier `apps/extension/`

## Utilisation

1. Se connecter à Philum dans un onglet (la session est un cookie httpOnly,
   l'extension le réutilise via `credentials: "include"` — elle ne voit jamais
   le token).
2. Sur n'importe quelle page, cliquer l'icône Philum.
3. Le popup pré-remplit titre / auteurs / catégorie (heuristique locale, puis
   enrichissement via l'endpoint public `/sources/extract`).
4. Choisir la fiche cible et cliquer **Ajouter la source**.

## Réglages

Clic droit sur l'icône → Options : URLs de l'API et du site (utile pour pointer
sur `http://localhost:8000` en dev). Note : en dev local, le cookie de session
est `SameSite=Lax` non-Secure et est bien envoyé par le fetch de l'extension
grâce à `host_permissions`.

## Sécurité

- Aucune permission large : `activeTab` (URL/titre de l'onglet actif au clic
  uniquement) + `storage` + `host_permissions` limitées à l'API Philum.
- Aucun script de contenu injecté dans les pages.
- Aucun secret stocké : l'authentification repose sur le cookie de session
  httpOnly existant du navigateur.
