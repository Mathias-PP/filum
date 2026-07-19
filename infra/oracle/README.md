# Déploiement backend sur Oracle Cloud Always Free

Guide complet : VM gratuite **à vie** (pas un trial), Docker Compose (FastAPI + Caddy TLS), domaine gratuit DuckDNS. Le frontend reste sur Vercel ; grâce au proxy SvelteKit (ADR-025), **la config Google OAuth ne change pas** — seul `BACKEND_URL` sur Vercel change.

Deux variantes selon la VM obtenue :

| | **E2.1.Micro** (x86, 1 GB) — `docker-compose.micro.yml` | **A1.Flex** (ARM, 2 OCPU/12 GB) — `docker-compose.yml` |
|---|---|---|
| Disponibilité | **Immédiate** (2 instances gratuites) | « Out of host capacity » chronique (cf. `../oracle-vm-retry.md`) |
| Postgres | **Externe (Supabase free tier)** | Conteneur local + backups |
| Étapes spécifiques | 2-micro, 4b (swap), 6 (Supabase) | 2, 6 |

**Stratégie recommandée** : démarrer sur E2.1.Micro aujourd'hui, laisser la boucle
de retry A1 tourner ; au succès, redéployer sur l'ARM en ~30 min (la VM est
stateless : la base est chez Supabase, il suffit de rejouer les étapes 4→6 sur la
nouvelle machine et de re-pointer le DNS DuckDNS). Les deux quotas sont cumulables.

Durée estimée : 1h à 1h30.

---

## Étape 0 — Prérequis

- Une carte bancaire (vérification d'identité Oracle uniquement — **jamais débitée** tant qu'on reste sur les ressources « Always Free », étiquetées comme telles dans la console).
- Une clé SSH. Si tu n'en as pas (PowerShell) :
  ```powershell
  ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\oracle_philum
  ```
  La clé **publique** est dans `oracle_philum.pub`.

## Étape 1 — Créer le compte Oracle Cloud

1. https://www.oracle.com/cloud/free/ → **Start for free**.
2. ⚠️ **Le choix de la « Home Region » est définitif.** Prendre **France Central (Paris)** ou **Germany Central (Frankfurt)**. Frankfurt a généralement plus de capacité ARM disponible.
3. Vérification email + CB (empreinte ~1 €, remboursée). Choisir le compte **Free Tier** ; à la fin du trial de 30 jours, le compte bascule automatiquement en « Always Free » — les ressources Always Free continuent de tourner, rien à faire.

## Étape 2-micro — Créer la VM E2.1.Micro (dispo immédiate)

Console Oracle → menu ☰ → **Compute** → **Instances** → **Create instance**.

1. **Name** : `philum-api`.
2. **Image and shape** → **Edit** :
   - **Shape** : catégorie **Specialty and previous generation** → `VM.Standard.E2.1.Micro` (étiqueté « Always Free-eligible »). 1 GB RAM, 1/8 de cœur AMD burstable à 100 %.
   - **Image** : **Canonical Ubuntu 24.04** (x86_64 — l'architecture suit le shape automatiquement).
3. **Primary VNIC** : VCN par défaut, sous-réseau public, **Assign a public IPv4 address = Yes**.
4. **Add SSH keys** : coller le contenu de `oracle_philum.pub`.
5. **Boot volume** : 50 GB. → **Create**. L'instance passe **Running** en ~1 min (pas de pénurie sur ce shape).

Puis suivre **2b** (IP réservée), **3** (ports), **4** (Docker) **+ 4b (swap, obligatoire sur 1 GB)**, **5** (DuckDNS), **6** en variante Supabase.

## Étape 2 — Créer la VM ARM A1.Flex (si capacité disponible)

Console Oracle → menu ☰ → **Compute** → **Instances** → **Create instance**.

1. **Name** : `philum-api`.
2. **Placement** : laisser l'AD par défaut.
3. **Image and shape** → **Edit** :
   - **Image** : *Ubuntu* → **Canonical Ubuntu 24.04** en build **aarch64** (si seule la variante « Minimal aarch64 » est proposée avec le shape Ampere, elle convient — voir la note post-installation à l'étape 4).
   - **Shape** : **Ampere** → `VM.Standard.A1.Flex` → **2 OCPU / 12 GB RAM = le maximum Always Free**. ⚠️ Depuis le 15 juin 2026, le quota gratuit est de 1 500 OCPU-heures + 9 000 GB-heures/mois, soit exactement 2 OCPU / 12 GB en continu (c'était 4/24 avant — beaucoup de tutoriels sont périmés). Allouer plus consommerait le quota mensuel avant la fin du mois et l'instance serait stoppée. Source : [doc Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).
4. **Primary VNIC** : laisser le VCN par défaut (« Create new virtual cloud network »), sous-réseau public, **Assign a public IPv4 address = Yes**.
5. **Add SSH keys** : **Paste public keys** → coller le contenu de `oracle_philum.pub`.
6. **Boot volume** : 50 GB par défaut (Always Free couvre jusqu'à 200 GB au total).
7. **Create**.

> 💥 **Erreur « Out of host capacity »** : classique sur les shapes ARM gratuits. Solutions : réessayer (parfois plusieurs fois par jour), changer d'Availability Domain à l'étape Placement, ou réduire à 1 OCPU / 6 GB (suffisant pour Philum ; redimensionnable plus tard via stop → Edit shape, sous réserve de capacité). La capacité se libère souvent tôt le matin. C'est le seul vrai obstacle du process — persévérer.

Quand l'instance est **Running**, noter son **Public IP**.

### 2b — Réserver l'IP publique (sinon elle change au stop/start)

1. Instance → **Attached VNICs** → cliquer la VNIC → **IPv4 Addresses**.
2. Sur l'IP → ⋮ → **Edit** → **No public IP** → Update (détache l'éphémère).
3. Puis ⋮ → **Edit** → **Reserved public IP** → **Create new reserved IP** → Update.

L'IP réservée attachée à une instance est gratuite.

## Étape 3 — Ouvrir les ports 80 et 443

Deux pare-feu à ouvrir (les deux sont nécessaires) :

### 3a — Security List Oracle (réseau)

Menu ☰ → **Networking** → **Virtual cloud networks** → ton VCN → **Security Lists** → *Default Security List* → **Add Ingress Rules** :

| Source CIDR | Protocol | Destination Port |
| ----------- | -------- | ---------------- |
| 0.0.0.0/0   | TCP      | 80               |
| 0.0.0.0/0   | TCP      | 443              |

(Le port 22 est déjà ouvert par défaut.)

### 3b — iptables de la VM (⚠️ piège connu des images Ubuntu Oracle)

Les images Ubuntu d'Oracle embarquent des règles iptables restrictives **indépendantes** de la Security List. Après connexion SSH (étape 4) :

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## Étape 4 — Installer Docker sur la VM

```powershell
ssh -i $env:USERPROFILE\.ssh\oracle_philum ubuntu@<PUBLIC_IP>
```

Puis sur la VM :

```bash
sudo apt-get update && sudo apt-get upgrade -y
# Les paquets suivants manquent sur l'image "Minimal" (no-op sur l'image complète) :
sudo apt-get install -y curl git iptables-persistent
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit   # se reconnecter pour que le groupe docker prenne effet
```

### 4b — Swap (obligatoire sur E2.1.Micro / 1 GB)

Sans swap, le build Docker et les pics mémoire tuent des process (OOM). 2 GB de swap :

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo sysctl vm.swappiness=10 && echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.d/99-swap.conf
free -h   # vérifier : ligne Swap = 2.0Gi
```

## Étape 5 — Domaine gratuit DuckDNS

1. https://www.duckdns.org → login (GitHub/Google).
2. Créer un sous-domaine, ex. `philum-api` → donne `philum-api.duckdns.org`.
3. Dans le champ **current ip**, mettre la **Public IP réservée** de la VM → **update ip**.

(L'IP étant réservée/fixe, pas besoin du cron de mise à jour DuckDNS.)

## Étape 6 — Déployer l'application

### 6a (variante micro uniquement) — Créer la base Supabase

1. https://supabase.com → New project → région **eu-west-3 (Paris)** (ou la plus proche), free tier.
2. Noter le mot de passe base. Dashboard → **Connect** → onglet **Session pooler** (port 5432, ⚠️ pas le Transaction pooler 6543 : incompatible asyncpg) → copier la connection string → ce sera `database_url` dans `.env`.
3. Les migrations Alembic et le seed tournent automatiquement au premier boot du conteneur.

### 6b — Lancer

Sur la VM :

```bash
git clone https://github.com/Mathias-PP/filum.git
cd filum/infra/oracle
cp .env.example .env
nano .env
```

Remplir `.env` :

- `API_DOMAIN` : ton domaine DuckDNS.
- `POSTGRES_PASSWORD`, `session_secret` : générer avec `openssl rand -hex 32`.
- `master_encryption_key` : ⚠️ **reprendre la valeur Railway si tu l'as encore** (elle chiffre les clés privées Ed25519 des utilisateurs — une nouvelle clé rend les anciennes signatures impossibles à re-signer). Si la base repart de zéro de toute façon, en générer une nouvelle.
- `google_client_id` / `google_client_secret` : reprendre ceux du projet Google Cloud existant (inchangés).

Puis :

```bash
chmod +x deploy.sh

# Variante ARM (Postgres local) :
docker compose up -d --build
# Variante E2.1.Micro (base Supabase, `database_url` rempli dans .env) :
docker compose -f docker-compose.micro.yml up -d --build   # build ~5-10 min sur 1/8 cœur

docker logs -f philum-backend    # attendre "Application startup complete"
```

Le conteneur backend applique les migrations Alembic et seed la fiche démo au boot (cf. `apps/backend/Dockerfile`).

Vérifications :

```bash
curl -s http://localhost:80/health          # via Caddy en HTTP local
curl -s https://philum-api.duckdns.org/health   # TLS public (Caddy obtient le certificat au premier hit, ~10 s)
```

## Étape 7 — Rebrancher Vercel

1. https://vercel.com → projet **filum** → **Settings** → **Environment Variables**.
2. `BACKEND_URL` = `https://philum-api.duckdns.org` (environnement **Production**).
3. **Deployments** → ⋮ sur le dernier déploiement → **Redeploy** (les env vars serverless ne sont prises qu'au déploiement).

Vérifier ensuite :

- https://filum-eight.vercel.app/@example/memoire-et-cerveau → la fiche démo s'affiche.
- « Continuer avec Google » → le flow OAuth aboutit (rien à changer côté Google Cloud Console : le `redirect_uri` reste construit sur l'origin Vercel via `X-Filum-Public-Origin`, cf. ADR-025).

## Étape 8 — Récupérer les données Railway (si encore accessibles)

Si le Postgres Railway répond encore malgré la fin du trial :

```bash
# Depuis n'importe quelle machine avec pg_dump :
pg_dump "<DATABASE_URL_RAILWAY_format_postgresql://...>" > railway_dump.sql
scp -i ~/.ssh/oracle_philum railway_dump.sql ubuntu@<PUBLIC_IP>:~
# Sur la VM (base vierge AVANT le premier docker compose up, sinon drop/recréer) :
docker exec -i philum-postgres psql -U philum -d philum < ~/railway_dump.sql
```

Variante micro (Supabase) : restaurer directement dans Supabase depuis n'importe quelle machine — `psql "<database_url_supabase>" < railway_dump.sql` (avant le premier boot du backend).

Sinon : la base repart de zéro, le seed recrée la fiche démo `/@example/memoire-et-cerveau` automatiquement.

## Maintenance courante

```bash
# Mettre à jour l'app après un merge sur main :
cd ~/filum/infra/oracle && ./deploy.sh

# Logs :
docker logs -f philum-backend

# Backups (dump quotidien automatique, rotation 14 jours) :
ls ~/filum/infra/oracle/backups/

# Restaurer un backup :
gunzip -c backups/philum_XXXX.sql.gz | docker exec -i philum-postgres psql -U philum -d philum
```

**Sécurité VM** : les mises à jour de sécurité Ubuntu sont automatiques (`unattended-upgrades` actif par défaut). Prévoir un `sudo reboot` occasionnel (kernel) — `restart: always` relance tout au boot.

## Checklist finale

- [ ] VM Running avec IP publique **réservée**
- [ ] Ports 80/443 ouverts (Security List **ET** iptables)
- [ ] `https://<API_DOMAIN>/health` → 200
- [ ] `BACKEND_URL` mis à jour + redeploy Vercel
- [ ] Fiche démo OK, login Google OK
- [ ] `STATE.md` mis à jour (URL backend + section env vars)
- [ ] Supprimer le service Railway pour éviter toute confusion
