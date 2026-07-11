#!/usr/bin/env bash
# Retente la création de l'instance ARM Always Free jusqu'à succès
# (contourne "Out of host capacity" en insistant automatiquement).
#
# Prérequis : OCI CLI configuré (`oci setup config`) + un VCN avec un
# sous-réseau PUBLIC déjà créé (console : Networking → Virtual cloud
# networks → "Start VCN Wizard" → "Create VCN with Internet Connectivity").
#
# Remplir les variables ci-dessous puis : ./retry-launch.sh
# Laisser tourner (une nuit s'il le faut). Arrêt automatique au succès.
set -u

# ── À REMPLIR ────────────────────────────────────────────────────────
TENANCY_OCID="ocid1.tenancy.oc1..xxxx"          # Profil (en haut à droite) → Tenancy → OCID
AD_NAME="XXXX:EU-PARIS-1-AD-1"                  # oci iam availability-domain list --query 'data[].name'
SUBNET_OCID="ocid1.subnet.oc1..xxxx"            # VCN → Subnets → subnet public → OCID
IMAGE_OCID="ocid1.image.oc1..xxxx"              # voir commande ci-dessous
SSH_PUB_FILE="$HOME/.ssh/oracle_philum.pub"
OCPUS=1                                          # 1/6 passe plus souvent ; max Always Free : 2/12
MEMORY_GB=6
DISPLAY_NAME="philum-api"
SLEEP_SECONDS=300
# ─────────────────────────────────────────────────────────────────────
# Trouver l'IMAGE_OCID Ubuntu 24.04 aarch64 de TA région :
#   oci compute image list --compartment-id "$TENANCY_OCID" \
#     --operating-system "Canonical Ubuntu" --operating-system-version "24.04 Minimal aarch64" \
#     --sort-by TIMECREATED --query 'data[0].{id:id,name:"display-name"}'
# ─────────────────────────────────────────────────────────────────────

# tr -d '\r\n' : une clé générée côté Windows contient des CRLF qui
# rendent le JSON --metadata invalide.
SSH_KEY=$(tr -d '\r\n' < "$SSH_PUB_FILE")
METADATA=$(printf '{"ssh_authorized_keys": "%s"}' "$SSH_KEY")

attempt=0
while true; do
  attempt=$((attempt + 1))
  echo "[$(date '+%F %T')] Tentative #$attempt..."
  if oci compute instance launch \
    --compartment-id "$TENANCY_OCID" \
    --availability-domain "$AD_NAME" \
    --shape "VM.Standard.A1.Flex" \
    --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
    --image-id "$IMAGE_OCID" \
    --subnet-id "$SUBNET_OCID" \
    --assign-public-ip true \
    --display-name "$DISPLAY_NAME" \
    --metadata "$METADATA"; then
    echo "✅ SUCCÈS — instance créée. Voir la console : Compute → Instances."
    exit 0
  fi
  echo "   Échec (capacité ?). Nouvelle tentative dans ${SLEEP_SECONDS}s. Ctrl+C pour arrêter."
  sleep "$SLEEP_SECONDS"
done
