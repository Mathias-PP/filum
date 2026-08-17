# `infra/` — Infrastructure de déploiement

Docker Compose et configurations pour héberger le backend Philum. Le frontend est sur Vercel (aucune config `infra/` requise pour lui).

## Ce qui vit ici

| Sous-dossier | Rôle |
|---|---|
| `oracle/` | Stack Docker Compose backend agnostique du cloud. Historiquement écrite pour Oracle Cloud Always Free, tourne aujourd'hui sur GCP e2-micro (cf. ADR-028 et l'entête de `oracle/README.md`). Contient `docker-compose.micro.yml` (variante Supabase Postgres) et `docker-compose.yml` (variante Postgres local + backups). Caddy pour le TLS DuckDNS. |
| `postgres/` | Config Postgres local (utilisée par la variante non-Supabase et par le dev). |
| `litellm/` | Config du proxy LiteLLM (voir `.docs/17-llm-strategy.md`). |
| `oracle-vm-retry.md` | Journal des tentatives d'obtention d'une VM Oracle A1.Flex. |

## Prod actuelle

VM GCP e2-micro (us-central1, Ubuntu 24.04, swap 2 GB), Postgres via Supabase, TLS via Caddy + DuckDNS, redéploiement Docker à chaque `git pull` sur la VM. Nom d'hôte : `philum-api.duckdns.org`.

Pour redéployer :

```bash
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  'sudo -n -u mathias_pinault git -C /home/mathias_pinault/filum pull -q && \
   sudo -n docker compose -f /home/mathias_pinault/filum/infra/oracle/docker-compose.micro.yml up -d --build backend'
```

(Le repo est cloné sous `/home/mathias_pinault/`, l'agent SSH via `mathias.pinault` peut passer par `sudo -n -u mathias_pinault` sans mot de passe. Cf. mémoire projet locale `reference_vm_deploy.md`.)

## Références

- ADR-028 (Postgres Supabase + GCP e2-micro) : `DECISIONS.md`
- Historique du choix Oracle → GCP : `oracle-vm-retry.md`
- Stratégie LLM : `.docs/17-llm-strategy.md`
