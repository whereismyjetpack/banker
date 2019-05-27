[![Build Status](https://drone-test.dsrd.libraries.psu.edu/api/badges/whereismyjetpack/banker/status.svg)](https://drone-test.dsrd.libraries.psu.edu/whereismyjetpack/banker)


## Configuration 

All Configuration is done via Environment variagles sent to the banker pod 
| Environment Variable  | Default               | Required | 
|-----------------------|-----------------------|----------|
| VAULT_ADDR            | http://127.0.0.1:8200 | No       |
| VAULT_TOKEN           | None                  | No       |   
| VAULT_AUTH_TYPE       | "ServiceAccount"      | No       |
| KUBERNETES_VAULT_ROLE | None                  | No       | 
| VAULT_MOUNT_PATH      | "kubernetes"          | No       |
|                       |                       |          |

VAULT_ADDR: Address to the Vault server