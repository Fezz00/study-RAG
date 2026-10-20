#!/usr/bin/env bash
# Create (or restart) the local Kubernetes cluster for this project.
#
# Usage:  ./scripts/cluster-up.sh
#
# - uses its own minikube profile, so other minikube clusters are not touched
# - enables the ingress addon (one URL for the whole app, phase 4)
# - creates the namespace and the secret that lets the cluster pull the private images from ghcr.io
#
# Safe to run again: every step skips or updates what already exists.
set -euo pipefail

PROFILE="study-rag"
NAMESPACE="study-rag"
GHCR_USER="fezz00"

echo "==> Starting minikube profile '$PROFILE'"
minikube start --profile "$PROFILE" --driver=docker --cpus=4 --memory=6g

echo "==> Enabling ingress"
minikube addons enable ingress --profile "$PROFILE"

echo "==> Creating namespace '$NAMESPACE'"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Image pull secret for ghcr.io"
if kubectl -n "$NAMESPACE" get secret ghcr-pull >/dev/null 2>&1; then
  echo "    already exists, skipping (delete it to replace: kubectl -n $NAMESPACE delete secret ghcr-pull)"
else
  # Read the token without showing it, so it never ends up in the terminal or shell history.
  read -rsp "    GitHub token with read:packages: " GHCR_TOKEN
  echo
  kubectl -n "$NAMESPACE" create secret docker-registry ghcr-pull \
    --docker-server=ghcr.io \
    --docker-username="$GHCR_USER" \
    --docker-password="$GHCR_TOKEN"
fi

echo
echo "Cluster is ready:"
kubectl get nodes
