# Part 8: Kubernetes and Argo CD

This lab uses local images loaded into kind. That makes the deployment independent of GHCR credentials and keeps the Part 7 release pipeline separate. The three tags below must match the manifests. When promoting changed images, use new tags and update them in Git; kind can otherwise reuse a cached tag.

## Start the lab

Run these from the repository root with Docker running in Linux container mode, kubectl installed, and [kind v0.31.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.31.0) on PATH.

```text
kind create cluster --name fulfillops --config infra/kind/kind-config.yaml
kubectl config current-context
docker build -t fulfillops-api:part8 api
docker build -t fulfillops-worker:part8 worker
docker build -t fulfillops-migrate:part8 db
kind load docker-image --name fulfillops fulfillops-api:part8 fulfillops-worker:part8 fulfillops-migrate:part8
kubectl --context kind-fulfillops create namespace argocd
kubectl --context kind-fulfillops apply -n argocd --server-side --force-conflicts -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.4.3/manifests/install.yaml
kubectl --context kind-fulfillops create namespace fulfillops
```

Create a temporary environment file outside Git containing POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and DATABASE_URL. Use a throwaway password. DATABASE_URL must use the same values and the in-cluster host and port postgres:5432. Create the namespace Secret from this file, then delete the local file. Avoid printing the file or the Secret.

```text
kubectl --context kind-fulfillops -n fulfillops create secret generic fulfillops-db --from-env-file=PATH_TO_TEMP_ENV_FILE
kubectl --context kind-fulfillops -n argocd rollout status deployment/argocd-server --timeout=240s
```

The tracked Application points to main on the team's GitHub repository. If the repository is private, connect it in Argo CD with a read-only deploy key or equivalent read-only credential before applying the Application. For a test before merging, change targetRevision to the pushed PR branch in a temporary copy of the Application. Keep credentials out of the repo.

```text
kubectl --context kind-fulfillops apply -f infra/argocd/application.yaml
kubectl --context kind-fulfillops -n argocd get application fulfillops
kubectl --context kind-fulfillops -n fulfillops get "deploy,pods,svc,pvc"
kubectl --context kind-fulfillops -n fulfillops logs job/migrate
```

The migration is a named Sync hook. It runs after PostgreSQL is ready and before Argo CD rolls out the API and worker. Argo CD recreates the Job on another full sync so changes don't hit Kubernetes' immutable Job pod template. The migration runner skips versions already applied.

## Verify drift correction

On the disposable cluster only, record the Application revision and its Synced and Healthy status. Confirm two Ready API replicas, two Ready workers, and a Bound PostgreSQL PVC. Then change the live API replica count to three and record that Argo CD restores two without a manual patch:

```text
kubectl --context kind-fulfillops -n fulfillops scale deploy/api --replicas=3
kubectl --context kind-fulfillops -n fulfillops get deploy/api -w
kubectl --context kind-fulfillops -n argocd get application fulfillops
```

Self-healing is appropriate for accidental drift in reviewed settings such as replica counts. Require a human to approve destructive changes, data migrations, PVC deletions, and emergency overrides where Git should temporarily stop reconciling the affected resource.

References: [Argo CD v3.4.3](https://github.com/argoproj/argo-cd/releases/tag/v3.4.3), [sync hooks and waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/), and [automated sync and self-healing](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

## Live verification

On 14 November 2026, kind v0.31.0 ran Kubernetes v1.35.0 with Argo CD v3.4.3. Argo CD reached Synced and Healthy. The migration completed through 004, PostgreSQL had a Bound 1 GiB volume, and both the API and worker had two Ready replicas. Manually scaling the API to three caused OutOfSync. Argo CD restored two replicas and returned to Synced and Healthy without a corrective patch.

The [timestamped evidence](evidence/part8-kind-argocd.txt) is from a temporary Git repository created from the working manifests so the uncommitted fixes could be tested. The checked-in Application still points to the team's GitHub main. After pushing, rerun against the team's GitHub revision if the assessor needs evidence from that source specifically.
