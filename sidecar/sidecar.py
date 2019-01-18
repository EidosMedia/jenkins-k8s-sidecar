from kubernetes import client, config, watch
import os
import requests
import sys
import paramiko
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import io
import logging
import socket
import time


def jenkinsReloadConfig(admin_private_key, admin_user, ssh_port, logger):
  logger.debug("Start of jenkins reload function")
  private_key_file = io.StringIO()
  private_key_file.write(admin_private_key)
  private_key_file.seek(0)
  private_key = paramiko.RSAKey.from_private_key(private_key_file)
  ssh_client = paramiko.SSHClient()
  ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh_client.connect('127.0.0.1', port=ssh_port, username=admin_user, pkey=private_key)
  stdin, stdout, stderr = ssh_client.exec_command("reload-jcasc-configuration")
  result = stderr.read().decode("utf-8")
  if result == '':
    logger.info("jcasc successfully reloaded")
  else:
    logger.error("jcasc failed to reload due to error: %s" % result)
  logger.debug("Closing ssh client")
  ssh_client.close()


def writeTextToFile(folder, filename, data):
  with open(folder + "/" + filename, 'w') as f:
    f.write(data)
    f.close()


def request(url, method, payload, logger):
  r = requests.Session()
  retries = Retry(total=5,
                  connect=5,
                  backoff_factor=0.2,
                  status_forcelist=[500, 502, 503, 504])
  r.mount('http://', HTTPAdapter(max_retries=retries))
  r.mount('https://', HTTPAdapter(max_retries=retries))
  if url is None:
    logger.info("No url provided. Doing nothing.")
    # If method is not provided use GET as default
  elif method == "GET" or method is None:
    res = r.get("%s" % url, timeout=10)
    logger.info("%s request sent to %s. Response: %d %s" % (method, url, res.status_code, res.reason))
  elif method == "POST":
    res = r.post("%s" % url, json=payload, timeout=10)
    logger.info("%s request sent to %s. Response: %d %s" % (method, url, res.status_code, res.reason))


def removeFile(folder, filename, logger):
  completeFile = folder + "/" + filename
  if os.path.isfile(completeFile):
    os.remove(completeFile)
  else:
    logger.error("Error: %s file not found" % completeFile)


def setup_custom_logger(name):
  formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S')
  handler = logging.FileHandler('log.txt', mode='w')
  handler.setFormatter(formatter)
  screen_handler = logging.StreamHandler(stream=sys.stdout)
  screen_handler.setFormatter(formatter)
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)
  logger.addHandler(screen_handler)
  return logger


def watchForChanges(label, targetFolder, url, method, payload, namespace, logger, admin_private_key="", admin_user="",
                    ssh_port=944):
  v1 = client.CoreV1Api()
  w = watch.Watch()
  resource_version = ""
  while True:
    if namespace is None:
      logger.debug("namespace is: %s" % namespace)
      stream = w.stream(v1.list_namespaced_config_map, namespace=namespace, resource_version=resource_version, timeout_seconds=60)
      resource_version = v1.list_namespaced_config_map(namespace=namespace).metadata.resource_version
    elif namespace == "ALL":
      stream = w.stream(v1.list_config_map_for_all_namespaces, resource_version=resource_version, timeout_seconds=60)
      resource_version = v1.list_config_map_for_all_namespaces().metadata.resource_version
    else:
      logger.debug("namespace is: %s" % namespace)
      stream = w.stream(v1.list_namespaced_config_map, namespace=namespace, resource_version=resource_version, timeout_seconds=60)
      resource_version = v1.list_namespaced_config_map(namespace=namespace).metadata.resource_version
    for event in stream:
      logger.debug("Start of stream loop")
      metadata = event['object'].metadata
      logger.info(f'Working on configmap {metadata.namespace}/{metadata.name}')
      if metadata.labels is None:
        continue
      logger.info(f'Working on configmap {metadata.namespace}/{metadata.name}')
      if label in event['object'].metadata.labels.keys():
        logger.info("Configmap with label found")
        dataMap = event['object'].data
        if dataMap is None:
          logger.error("Configmap does not have data.")
          continue
        eventType = event['type']
        for filename in dataMap.keys():
          logger.info("File in configmap %s %s" % (filename, eventType))
          if (eventType == "ADDED") or (eventType == "MODIFIED"):
            logger.debug("Start of added\modified loop")
            writeTextToFile(targetFolder, filename, dataMap[filename])
            if url is not None:
              request(url, method, payload, logger)
            elif jenkinsReloadConfig is not None:
              jenkinsReloadConfig(admin_private_key, admin_user, ssh_port, logger)
          else:
            removeFile(targetFolder, filename, logger)
            if url is not None:
              request(url, method, payload, logger)


def main():
  logger = setup_custom_logger('sidecar')
  logger.info("Starting config map collector")
  label = os.getenv('LABEL')
  logger.info("label is: %s" % label)
  if label is None:
    logger.error("Should have added LABEL as environment variable! Exit")
    exit(1)
  targetFolder = os.getenv('FOLDER')
  logger.info("targetFolder is: %s" % targetFolder)
  if targetFolder is None:
    logger.error("Should have added FOLDER as environment variable! Exit")
    exit(1)
  method = os.getenv('REQ_METHOD')
  url = os.getenv('REQ_URL')
  payload = os.getenv('REQ_PAYLOAD')
  jenkinsReloadConfigEnabled = os.getenv('JENKINSRELOADCONFIG')
  config.load_incluster_config()
  logger.info("Config for cluster api loaded...")
  namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
  logger.info("namespace is: %s" % namespace)
  if jenkinsReloadConfigEnabled:
    admin_private_key = os.environ['ADMIN_PRIVATE_KEY']
    if admin_private_key is None:
      logger.error("Should have added ADMIN_PRIVATE_KEY as environment variable! Exit")
      exit(1)
    ssh_port = os.environ['SSH_PORT']
    if ssh_port is None:
      logger.error("Should have added SSH_PORT as environment variable! Exit")
      exit(1)
    logger.info("ssh_port is: %s" % ssh_port)
    ssh_port = int(ssh_port)
    jenkins_port = os.environ['JENKINS_PORT']
    if jenkins_port is None:
      logger.error("Should have added JENKINS_PORT as environment variable! Exit")
      exit(1)
    logger.info("jenkins_port is: %s" % jenkins_port)
    jenkins_port = int(jenkins_port)
    admin_user = os.environ['ADMIN_USER']
    logger.info("admin_user is: %s" % admin_user)
    if admin_user is None:
      logger.error("Should have added ADMIN_USER as environment variable! Exit")
      exit(1)
    host = '127.0.0.1'
    while True:
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      try:
        s.connect((host, jenkins_port))
        logger.info("Jenkins is contactable, continuing.")
        break
      except Exception:
        logging.info("Jenkins is not up yet.  Waiting...")
        time.sleep(5)
    s.close()
    time.sleep(15)  # Wait for sshd daemon to start
    watchForChanges(label, targetFolder, url, method, payload, namespace, logger, admin_private_key, admin_user,
                    ssh_port)
  watchForChanges(label, targetFolder, url, method, payload, namespace, logger)


if __name__ == '__main__':
  main()
