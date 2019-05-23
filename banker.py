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

class Banker(object):
    def __init__(self):
        ## TODO determine if we are in kubernetes. 
        logger.add(sys.stderr, level="DEBUG")
        self.in_kubernetes = True
        self.get_config()
        self.vault_client = self.get_vault_client()
        self.run()

    def get_config(self):
        self.vault_addr = os.environ.get('VAULT_ADDR', "http://127.0.0.1:8200")
        self.vault_token = os.environ.get("VAULT_TOKEN", None)
        # TODO enum
        self.vault_auth_type = os.environ.get("VAULT_AUTH_TYPE", "ServiceAccount")
        self.kubernetes_vault_role = os.environ.get("KUBERNETES_VAULT_ROLE", None)
        self.vault_mount_path = os.environ.get("VAULT_MOUNT_PATH", "kubernetes")

        if self.vault_auth_type == 'ServiceAccount':
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            if os.path.isfile(token_path):
                # TODO if user sets token, don't mutate here
                with open(token_path) as f:
                    self.vault_token = f.read()
            # else:
            #     raise AttributeError("auth type is set to ServiceAccount, but we can't find a token file")

    def get_vault_client(self):
        vault_client = hvac.Client(url=self.vault_addr)
        if self.in_kubernetes:
            vault_client.auth_kubernetes(self.kubernetes_vault_role, self.vault_token, mount_point=self.vault_mount_path)
        else:
            vault_client.token = self.vault_token
        
        return vault_client

    def create_secret(self, namespace, name, data, uid):
        # create secret 
        # TODO add annotation so we know we own this secret
        # if exists, and annotation doesn't -- log 
        v1 = kubernetes.client.CoreV1Api()
        for k in data:
            data[k] = base64.b64encode(data[k].encode()).decode()
        kind = 'Secret'
        owners = []
        owners.append(kubernetes.client.V1OwnerReference(api_version='banker.jetpack/v1', kind='Vault', name=name, uid=uid))
        metadata = kubernetes.client.V1ObjectMeta(name=name, namespace=namespace, owner_references=owners)
        body = kubernetes.client.V1Secret('v1', data, kind, metadata)
        sec = None
        try:
            sec = v1.read_namespaced_secret(name, namespace)
            print(sec)
        except kubernetes.client.rest.ApiException as e:
            print(e)
            if json.loads(e.body)['code'] == 404:
                v1.create_namespaced_secret(namespace, body)

    def run(self):
        # TODO this is here for testing
        self.in_kubernetes = True

        if self.in_kubernetes:
            kubernetes.config.load_incluster_config()
        else:
            kubernetes.config.load_kube_config()

        k8s_config = kubernetes.client.Configuration()
        k8s_config.assert_hostname = False
        api_client = kubernetes.client.api_client.ApiClient(configuration=k8s_config)
        v1 = kubernetes.client.ApiextensionsV1beta1Api(api_client)
        crds = kubernetes.client.CustomObjectsApi(api_client)
        resource_version = ''

        logger.debug("starting to watch stream")
        while True:
            stream = kubernetes.watch.Watch().stream(crds.list_cluster_custom_object, DOMAIN, "v1", "vault", resource_version=resource_version)
            for event in stream:
                print(event)
                obj = event['object']
                namespace = obj['metadata']['namespace']
                name = obj['metadata']['name']
                spec = obj.get('spec')
                uid = obj['metadata']['uid']
                if not spec:
                    logger.debug("event does not have spec. skipping")
                if event['type'] == 'ADDED':
                    path = spec.get('path')
                    logger.debug(path)
                    if not path:
                        logger.debug("no path to retrive secrets. skipping")
                    
                    # TODO perhaps take secret/ and place on mount= in read_secret_version 
                    # error handling
                    secret = self.vault_client.secrets.kv.v2.read_secret_version(path=path)
                    data = secret['data']['data']
                    self.create_secret(namespace, name, data, uid)

b = Banker()