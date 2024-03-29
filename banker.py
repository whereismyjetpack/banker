import hvac
import os
import base64
import time
import sys
import json
import kubernetes
from threading import Thread
from loguru import logger

DOMAIN = "banker.jetpack"


class Banker:
    def __init__(self):
        self.in_kubernetes = False
        self.get_config()
        self.truthy_values = ["true", "yes", "y"]
        self.dont_sync = []
        self.vault_client = self.get_vault_client()

    def get_config(self):
        logger.remove(0)
        # TODO make json pattern
        logger.add(sys.stderr, level=os.environ.get("BANKER_LOG_LEVEL", "INFO"))

        if "KUBERNETES_PORT" in os.environ:
            self.in_kubernetes = True
        else:
            self.in_kubernetes = False

        valid_auth_types = ["ServiceAccount", "Token"]

        self.sync_frequency_seconds = os.environ.get(
            "BANKER_SYNC_FREQUENCY_SECONDS", 60
        )
        self.vault_addr = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self.vault_token = os.environ.get("VAULT_TOKEN", None)
        self.vault_auth_type = os.environ.get("VAULT_AUTH_TYPE", "ServiceAccount")
        if self.vault_auth_type not in valid_auth_types:
            logger.debug(
                f"{self.vault_auth_type} is not a valid auth type. Defaulting to Token"
            )
            self.vault_auth_type = "Token"
        self.kubernetes_vault_role = os.environ.get("KUBERNETES_VAULT_ROLE", None)
        self.vault_mount_path = os.environ.get("VAULT_MOUNT_PATH", "kubernetes")

        # TODO what to do if user sets token and AuthType to ServiceAccount? bail? default?

        if self.vault_auth_type == "ServiceAccount":
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            if os.path.isfile(token_path) and not self.vault_token:
                with open(token_path) as f:
                    logger.debug("reading kubernetes token")
                    self.vault_token = f.read()

    def get_vault_client(self):
        logger.debug("setting up vault client")
        vault_client = hvac.Client(url=self.vault_addr)
        if self.vault_auth_type == "ServiceAccount":
            logger.debug("setting up in_kubernetes vault client")
            vault_client.auth_kubernetes(
                self.kubernetes_vault_role,
                self.vault_token,
                mount_point=self.vault_mount_path,
            )
        else:
            logger.debug("using token auth for vault client")
            vault_client.token = self.vault_token

        return vault_client

    def create_secret(self, namespace, name, data, uid, secret_type):
        v1 = kubernetes.client.CoreV1Api()
        for k in data:
            data[k] = base64.b64encode(data[k].encode()).decode()
        kind = "Secret"
        owners = []
        owners.append(
            kubernetes.client.V1OwnerReference(
                api_version="banker.jetpack/v1", kind="Vault", name=name, uid=uid
            )
        )
        metadata = kubernetes.client.V1ObjectMeta(
            name=name, namespace=namespace, owner_references=owners
        )
        body = kubernetes.client.V1Secret("v1", data, kind, metadata, None, secret_type)
        try:
            logger.debug(f"checking secret {name} in namespace {namespace}")
            v1.create_namespaced_secret(namespace, body)
            logger.info(f"created secret {name} in namespace {namespace}")
        except kubernetes.client.rest.ApiException as e:
            if json.loads(e.body)["code"] == 409:
                sec = v1.read_namespaced_secret(name, namespace)
                if sec.data != data:
                    # TODO check if we own it before replacing
                    v1.replace_namespaced_secret(name, namespace, body)
                    logger.info("updating secret with new data")
                logger.debug("secret already exists")
            else:
                logger.debug(e)

    def reconcile(self, client):
        logger.debug(f"starting reconciliation loop")
        crds = kubernetes.client.CustomObjectsApi(client)
        objs = dict(crds.list_cluster_custom_object(DOMAIN, "v1", "vault"))
        self.resource_version = objs["metadata"]["resourceVersion"]
        while True:
            objs = dict(crds.list_cluster_custom_object(DOMAIN, "v1", "vault"))
            for obj in objs["items"]:
                self.process_object(obj, "reconcile")
            logger.debug(f"sleeping for {str(self.sync_frequency_seconds)}")
            time.sleep(int(self.sync_frequency_seconds))

    def process_object(self, obj, caller):
        name = obj["metadata"]["name"]
        namespace = obj["metadata"]["namespace"]
        uid = obj["metadata"]["uid"]
        path = obj["spec"].get("path", None)
        sync = str(obj["spec"].get("sync", "false")).lower()
        secret_type = obj["spec"].get("type", None)

        if sync in self.truthy_values:
            sync = True
        else:
            sync = False

        # If a user adds sync: true to an already proccessed object
        if sync and uid in self.dont_sync:
            self.dont_sync.remove(uid)

        if not sync and uid not in self.dont_sync:
            self.dont_sync.append(uid)
            logger.debug(f"not syncing {name}")
            return None

        if not sync:
            return None

        if not path:
            logger.debug(f"Vault object {name} is missing path property")
        else:
            # TODO make this a function and do error checking
            logger.debug(f"reading secret from {path}")
            secret = self.vault_client.secrets.kv.v2.read_secret_version(path=path)
            data = secret["data"]["data"]
            self.create_secret(namespace, name, data, uid, secret_type)

    def watch_stream(self, client):
        crds_watch = kubernetes.client.CustomObjectsApi(client)
        stream = kubernetes.watch.Watch().stream(
            crds_watch.list_cluster_custom_object,
            DOMAIN,
            "v1",
            "vault",
            resource_version=self.resource_version,
        )
        for event in stream:
            obj = event["object"]
            if event["type"] == "ADDED":
                self.process_object(obj, "event_stream")

    def renew_token(self, sleep_time):
        while True:
            time.sleep(sleep_time)
            logger.debug(f"renewing vault token")
            self.vault_client.renew_token()
            logger.debug(f"renewed vault token")

    def run(self):
        if self.in_kubernetes:
            logger.debug("we are in cluster")
            kubernetes.config.load_incluster_config()
        else:
            logger.debug("we are not in cluster")
            kubernetes.config.load_kube_config()

        # check for ttl, start thread to renew
        vault_token_ttl = self.vault_client.lookup_token()["data"]["ttl"]
        if vault_token_ttl:
            sleep_time = vault_token_ttl / 2
            renew = Thread(target=self.renew_token, args=(sleep_time,))
            renew.start()

        k8s_config = kubernetes.client.Configuration.get_default_copy()
        k8s_config.assert_hostname = False
        api_client = kubernetes.client.api_client.ApiClient(configuration=k8s_config)
        self.resource_version = ""
        reconcile = Thread(target=self.reconcile, args=(api_client,))
        reconcile.start()

        while True:
            if self.resource_version:
                event_loop = Thread(target=self.watch_stream, args=(api_client,))
                event_loop.start()
                break


if __name__ == "__main__":
    b = Banker()
    b.run()
