#!/usr/bin/env bash
# Crée le réseau complet pour la VM Philum (VCN + internet gateway +
# route + subnet public) via OCI CLI, de façon idempotente.
# Usage : bash create-network.sh
set -euo pipefail

TEN=$(grep '^tenancy' ~/.oci/config | cut -d= -f2 | tr -d ' ')
[ -n "$TEN" ] || { echo "ERREUR: tenancy introuvable dans ~/.oci/config"; exit 1; }
echo "Tenancy : $TEN"

VCN=$(oci network vcn list --compartment-id "$TEN" \
  --query "data[?\"display-name\"=='vcn-philum'] | [0].id" --raw-output 2>/dev/null || true)
if [ -z "$VCN" ] || [ "$VCN" = "null" ]; then
  echo "Création du VCN..."
  VCN=$(oci network vcn create --compartment-id "$TEN" \
    --cidr-blocks '["10.0.0.0/16"]' --display-name vcn-philum \
    --wait-for-state AVAILABLE --query data.id --raw-output)
fi
echo "VCN     : $VCN"

IGW=$(oci network internet-gateway list --compartment-id "$TEN" --vcn-id "$VCN" \
  --query 'data[0].id' --raw-output 2>/dev/null || true)
if [ -z "$IGW" ] || [ "$IGW" = "null" ]; then
  echo "Création de l'internet gateway..."
  IGW=$(oci network internet-gateway create --compartment-id "$TEN" --vcn-id "$VCN" \
    --is-enabled true --display-name igw-philum \
    --wait-for-state AVAILABLE --query data.id --raw-output)
fi
echo "IGW     : $IGW"

RT=$(oci network vcn get --vcn-id "$VCN" --query 'data."default-route-table-id"' --raw-output)
echo "Route 0.0.0.0/0 -> IGW..."
oci network route-table update --rt-id "$RT" \
  --route-rules "[{\"destination\":\"0.0.0.0/0\",\"networkEntityId\":\"$IGW\"}]" \
  --force --query 'data."lifecycle-state"' --raw-output

SUBNET=$(oci network subnet list --compartment-id "$TEN" --vcn-id "$VCN" \
  --query "data[?\"display-name\"=='subnet-public'] | [0].id" --raw-output 2>/dev/null || true)
if [ -z "$SUBNET" ] || [ "$SUBNET" = "null" ]; then
  echo "Création du subnet public..."
  SUBNET=$(oci network subnet create --compartment-id "$TEN" --vcn-id "$VCN" \
    --cidr-block 10.0.0.0/24 --display-name subnet-public \
    --wait-for-state AVAILABLE --query data.id --raw-output)
fi

echo ""
echo "======================================================"
echo "  SUBNET_OCID=$SUBNET"
echo "  (valeur à mettre dans retry-launch.sh)"
echo "======================================================"
