#!/usr/bin/env bash
# Install Argo CD + Argo CD Image Updater into the cluster and point Argo CD at this repo.
#
# Usage:  ./scripts/gitops-up.sh     (after ./scripts/cluster-up.sh)
#
# Safe to run again: helm upgrades what's installed, kubectl apply updates what exists.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Helm chart repository for Argo"
helm repo add argo https://argoproj.github.io/argo-helm >/dev/null 2>&1 || true
helm repo update argo

echo "==> Installing Argo CD (takes a few minutes the first time)"
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --values gitops/argocd-values.yaml \
  --wait

echo "==> Installing Argo CD Image Updater"
helm upgrade --install argocd-image-updater argo/argocd-image-updater \
  --namespace argocd \
  --wait

echo "==> Copying the ghcr.io pull secret to the argocd namespace (Image Updater reads it there)"
kubectl -n study-rag get secret ghcr-pull -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d |
  kubectl -n argocd create secret docker-registry ghcr-pull \
    --from-file=.dockerconfigjson=/dev/stdin --dry-run=client -o yaml |
  kubectl apply -f -

echo "==> Grafana admin password (Secret 'grafana-admin' in the monitoring namespace)"
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
if kubectl -n monitoring get secret grafana-admin >/dev/null 2>&1; then
  echo "    already exists, skipping (to change it: kubectl -n monitoring delete secret grafana-admin, then run this again)"
else
  read -rsp "    Choose a Grafana admin password: " GRAFANA_PASSWORD
  echo
  kubectl -n monitoring create secret generic grafana-admin \
    --from-literal=admin-user=admin \
    --from-literal=admin-password="$GRAFANA_PASSWORD"
fi

echo "==> Registering the app and the monitoring stack with Argo CD"
kubectl apply -f gitops/application.yaml -f gitops/image-updater.yaml -f gitops/monitoring.yaml

echo
echo "Argo CD UI: http://argocd.study-rag.local  (needs 'minikube tunnel -p study-rag' and an /etc/hosts entry)"
echo "Grafana:    http://grafana.study-rag.local (user admin, the password you chose)"
echo "User: admin   Password:"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
echo
