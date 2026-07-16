# Boucle de création VM Oracle (Always Free ARM)

Protocole pour relancer manuellement la boucle qui tente de créer l'instance
`philum-api` (VM.Standard.A1.Flex, région `eu-paris-1`) jusqu'à ce qu'Oracle
libère de la capacité.

## Ce que fait le script

`~/retry-launch.sh` (dans le home WSL Ubuntu) boucle indéfiniment :

1. Tente **2 OCPU / 12 GB** (le max Always Free)
2. Si échec → pause 90 s → tente **1 OCPU / 6 GB** (fallback)
3. Si échec des deux → nouveau cycle 300 s plus tard
4. **S'arrête tout seul au premier succès** (message `SUCCES` dans le log)

L'erreur normale en attendant : `"message": "Out of host capacity"` — c'est
Oracle qui n'a pas de dispo, pas un bug. L'auth est par clé API
(`~/.oci/oci_api_key.pem`), elle n'expire jamais.

En cas de `TooManyRequests` (429), backoff exponentiel automatique
(60 → 120 → 240 → 300 s max). Le compteur se reset dès qu'une requête passe
sans throttling.

**Alerte au succès** : le script déclenche un bip sonore + une popup Windows
bloquante (« Oracle VM créée : X OCPU / Y GB ») dès qu'une instance est
provisionnée. La popup fonctionne même si Claude/PowerShell est fermé : le
script vit dans WSL, indépendant de tout terminal Windows.

## Lancer la boucle

Dans **PowerShell** (ou n'importe quel terminal Windows) :

```powershell
wsl -e bash -lc "~/retry-launch.sh 2>&1 | tee -a ~/retry-launch.log"
```

Ou directement dans un terminal **Ubuntu/WSL** :

```bash
~/retry-launch.sh 2>&1 | tee -a ~/retry-launch.log
```

## Règles

- **Une seule boucle à la fois** (sinon spam de l'API → `TooManyRequests`).
- La fenêtre du terminal doit **rester ouverte**. `Ctrl+C` pour arrêter.
- La boucle meurt si le PC s'éteint, se met en veille, ou si WSL est arrêté.
  Pour désactiver la veille secteur pendant l'attente :
  ```powershell
  powercfg /change standby-timeout-ac 0
  ```

## Surveiller

Log complet (accessible depuis Windows) : `\\wsl$\Ubuntu\home\mathi\retry-launch.log`

```powershell
# Dernières lignes du log
wsl -e bash -lc "tail -20 ~/retry-launch.log"

# Vérifier si une instance a été créée
wsl -e bash -lc "grep SUCCES ~/retry-launch.log"
```

## Bilan d'activité (occurrences / types d'erreur)

Toutes les commandes ci-dessous se lancent depuis PowerShell.

```powershell
# Total requêtes par code d'erreur (toute l'historique du log)
wsl -e bash -c "grep -oE 'code[^:]*: \"[A-Za-z]+\"' ~/retry-launch.log | sort | uniq -c"
# Exemple : 286 InternalError (Out of host capacity), 4 TooManyRequests

# Total requêtes par status HTTP
wsl -e bash -c "grep -oE 'status[^0-9]*[0-9]+' ~/retry-launch.log | sort | uniq -c"

# Nombre de cycles aujourd'hui (adapte la date)
wsl -e bash -c "grep -c '^\[2026-07-15' ~/retry-launch.log"

# Détail aujourd'hui : première/dernière tentative, nb shape-attempts, nb OoC
wsl -e bash -c "awk '/^\[2026-07-15/,0' ~/retry-launch.log > /tmp/today.log; \
  echo first: ; head -1 /tmp/today.log; \
  echo last:  ; tail -3 /tmp/today.log | head -1; \
  echo shape attempts: ; grep -c 'shape' /tmp/today.log; \
  echo OoC: ; grep -c 'Out of host capacity' /tmp/today.log"

# Vérifier si un succès a eu lieu
wsl -e bash -c "grep SUCCES ~/retry-launch.log"
```

## Changer la cadence du script

Le script est dans WSL à `~/retry-launch.sh`. Trois variables en tête de
fichier contrôlent la cadence :

```bash
SLEEP_SECONDS=240          # pause entre deux cycles complets
SLEEP_BETWEEN_SHAPES=60    # pause entre shape haut (2/12) et shape bas (1/6)
BACKOFF_START=60           # backoff initial sur 429 (double à chaque 429 consécutif)
BACKOFF_MAX=300            # plafond du backoff
```

> **Historique de tuning** : cadence 60/30 testée le 15/07, résultat 36% de
> 429. L'endpoint `launch_instance` a un rate limit spécifique bien plus
> serré que le plafond général (60 req/min). Cadence stable : 240s+60s →
> ~15 req/h, taux 429 attendu <2%.

Édition rapide en une ligne (édition dans WSL avec `nano`) :

```powershell
wsl -e bash -c "nano ~/retry-launch.sh"
```

Ou depuis Windows (le home WSL est monté à `\\wsl$\Ubuntu\home\mathi\`).

**Après modification, il faut relancer la boucle** (le script en cours garde
les anciennes valeurs en mémoire) :

```powershell
# 1. Tuer la boucle en cours
wsl -e bash -c "pkill -f retry-launch.sh"
# 2. Vérifier
wsl -e bash -c "pgrep -af retry-launch.sh || echo 'aucune boucle'"
# 3. Relancer
wsl -e bash -lc "~/retry-launch.sh 2>&1 | tee -a ~/retry-launch.log"
```

Rate limit OCI sur `launch_instance` : ~60 req/min. À 60 s + 30 s, on est
à ~40 req/heure, soit ~0,7 req/min — 90× sous le plafond. Marge pour
descendre encore si utile.

## En cas de succès

1. Console Oracle → Compute → Instances → noter l'**IP publique**.
2. Connexion : `ssh -i C:\Users\mathi\.ssh\oracle_philum opc@<IP>`
3. La clé SSH est déjà injectée à la création (`oracle_philum.pub`).
