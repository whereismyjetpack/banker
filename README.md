[![Build Status](https://drone-test.dsrd.libraries.psu.edu/api/badges/whereismyjetpack/banker/status.svg)](https://drone-test.dsrd.libraries.psu.edu/whereismyjetpack/banker)


# Banker 🏦
Banker is a controller meant to syncronize values from Vault, into proper Kubernetes secrets. 



# Crd Spec 
```
apiVersion: "banker.jetpack/v1"
kind: Vault
metadata:
  name: thingies
spec:
  path: "k8s-dev/newthing"
  sync: false

```

## Configuration 

All Configuration is done via Environment variagles sent to the banker pod

| Environment Variable   | Default               | Required |
|------------------------|-----------------------|----------|
| VAULT_ADDR             | http://127.0.0.1:8200 | No       |
| VAULT_TOKEN            | None                  | No       |
| VAULT_AUTH_TYPE        | "ServiceAccount"      | No       |
| KUBERNETES_VAULT_ROLE  | None                  | No       |
| VAULT_MOUNT_PATH       | "kubernetes"          | No       |
| SYNC_FREQUENCY_SECONDS | 60                    | No       |
| BANKER_LOG_LEVEL       | INFO                  | No       |


# Installation 

Open up `deploy/deployment.yaml` and configure for your environment

```
kubectl apply -f deploy
```

