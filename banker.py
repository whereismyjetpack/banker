import hvac
import pprint
import os
import base64
import sys
import yaml
import json
import kubernetes
from loguru import logger

DOMAIN = "banker.jetpack"

class Banker():
    def __init__(self):
        self.in_kubernetes = False
        self.get_config()
        self.vault_client = self.get_vault_client()
        self.run()

    def get_config(self):
        if 'KUBERNETES_PORT' in os.environ:
            self.in_kubernetes = True
        else:
            self.in_kubernetes = False

        valid_auth_types = ['ServiceAccount', 'Token']

        self.vault_addr = os.environ.get('VAULT_ADDR', "http://127.0.0.1:8200")
        self.vault_token = os.environ.get("VAULT_TOKEN", None)
        self.vault_auth_type = os.environ.get("VAULT_AUTH_TYPE", "ServiceAccount")
        if self.vault_auth_type not in valid_auth_types:
            logger.debug(f"{self.vault_auth_type} is not a valid auth type. Defaulting to Token")
            self.vault_auth_type = "Token"
        self.kubernetes_vault_role = os.environ.get("KUBERNETES_VAULT_ROLE", None)
        self.vault_mount_path = os.environ.get("VAULT_MOUNT_PATH", "kubernetes")

        # TODO what to do if user sets token and AuthType to ServiceAccount? bail? default?

        if self.vault_auth_type == 'ServiceAccount':
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            if os.path.isfile(token_path) and not self.vault_token:
                with open(token_path) as f:
                    logger.debug("reading kubernetes token")
                    self.vault_token = f.read()

    def get_vault_client(self):
        logger.debug("setting up vault client")
        vault_client = hvac.Client(url=self.vault_addr)
        if self.vault_auth_type == 'ServiceAccount':
            logger.debug("setting up in_kubernetes vault client")
            vault_client.auth_kubernetes(self.kubernetes_vault_role, self.vault_token, mount_point=self.vault_mount_path)
        else:
            logger.debug("using token auth for vault client")
            vault_client.token = self.vault_token
        
        return vault_client

    def create_secret(self, namespace, name, data, uid):
        # create secret 
        v1 = kubernetes.client.CoreV1Api()
        for k in data:
            data[k] = base64.b64encode(data[k].encode()).decode()
        kind = 'Secret'
        owners = []
        owners.append(kubernetes.client.V1OwnerReference(api_version='banker.jetpack/v1', kind='Vault', name=name, uid=uid))
        metadata = kubernetes.client.V1ObjectMeta(name=name, namespace=namespace, owner_references=owners)
        body = kubernetes.client.V1Secret('v1', data, kind, metadata)
        try:
            logger.info(f"creating secret {name} in namespace {namespace}")
            v1.create_namespaced_secret(namespace, body)
        except kubernetes.client.rest.ApiException as e:
            if json.loads(e.body)['code'] == 409:
                sec = v1.read_namespaced_secret(name, namespace)
                if sec.data != data:
                    # TODO check if we own it before replacing
                    v1.replace_namespaced_secret(name, namespace, body)
                    logger.debug("updating secret with new data")
                logger.debug("secret already exists")
        # try:
        #     sec = v1.read_namespaced_secret(name, namespace)
        # except kubernetes.client.rest.ApiException as e:
        #     if json.loads(e.body)['code'] == 404:
        #         v1.create_namespaced_secret(namespace, body)

    def run(self):
        if self.in_kubernetes:
            kubernetes.config.load_incluster_config()
        else:
            kubernetes.config.load_kube_config()

        k8s_config = kubernetes.client.Configuration()
        k8s_config.assert_hostname = False
        api_client = kubernetes.client.api_client.ApiClient(configuration=k8s_config)
        # v1 = kubernetes.client.ApiextensionsV1beta1Api(api_client)
        crds = kubernetes.client.CustomObjectsApi(api_client)
        # secrets = kubernetes.client.CoreV1Api(api_client)
        # s = secrets.list_secret_for_all_namespaces(limit=100)
        logger.debug("starting to watch stream")
        # while True:
        print('thing')
        resource_version=''
        # resp = crds.list_cluster_custom_object(DOMAIN, "v1", "vault")
        # for item in resp:
        #     print(item)
        while True:
            stream = kubernetes.watch.Watch().stream(crds.list_cluster_custom_object, DOMAIN, "v1", "vault", resource_version=resource_version)
            for event in stream:
                obj = event['object']
                namespace = obj['metadata']['namespace']
                name = obj['metadata']['name']
                spec = obj.get('spec')
                uid = obj['metadata']['uid']
                if not spec:
                    logger.debug("event does not have spec. skipping")
                if event['type'] == 'ADDED':
                    path = spec.get('path')
                    if not path:
                        logger.debug("no path to retrive secrets. skipping")
                    
                    # TODO perhaps take secret/ and place on mount= in read_secret_version 
                    # error handling
                    secret = self.vault_client.secrets.kv.v2.read_secret_version(path=path)
                    data = secret['data']['data']
                    self.create_secret(namespace, name, data, uid)
                

if __name__ == '__main__':
    b = Banker()

def run():
    Banker()