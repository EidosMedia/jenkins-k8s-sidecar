ARG BASE_TAG=3.6-slim-stretch
FROM python:${BASE_TAG}

LABEL maintainer="Eidosmedia <devops@eidosmedia.com>" \
    com.eidosmedia.version=1 \
    com.eidosmedia.is-production=1

ARG JENKINS_GID=1000
ARG JENKINS_GROUP=jenkins
ARG JENKINS_UID=1000
ARG JENKINS_USER=jenkins

ARG KUBERNETES_VERSION=9.0.0
ARG KUBERNETES_REQ=kubernetes==${KUBERNETES_VERSION}
ARG PARAMIKO_VERSION=2.4.2
ARG ADDITIONAL_PACKAGES

COPY sidecar/sidecar.py /app/

RUN if [ X"${ADDITIONAL_PACKAGES}" != X ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends \
            ${ADDITIONAL_PACKAGES} \
        && apt-get clean; \
    fi \
    && pip install --no-cache-dir \
        ${KUBERNETES_REQ} \
        paramiko==${PARAMIKO_VERSION} \
#        ipython \
    && groupadd -r -g ${JENKINS_GID} ${JENKINS_GROUP} \
    && useradd -r -u ${JENKINS_UID} -g ${JENKINS_GROUP} ${JENKINS_USER} \
    && chown -R ${JENKINS_USER}:${JENKINS_GROUP} /app \
    && chmod 700 /app \
    && if [ X"${ADDITIONAL_PACKAGES}" != X ]; then \
        apt-get -y purge ${ADDITIONAL_PACKAGES} \
        && apt-get -y autoremove; \
    fi

USER ${JENKINS_USER}

WORKDIR /app/

CMD ["python", "-u", "/app/sidecar.py"]
