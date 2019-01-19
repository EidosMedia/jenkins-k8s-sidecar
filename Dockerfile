FROM       python:3.6-slim-stretch
RUN        pip install --no-cache-dir kubernetes==6.0.0
RUN        pip install --no-cache-dir paramiko
RUN        pip install --no-cache-dir ipython
RUN        groupadd -r -g 1000 jenkins && useradd -r -u 1000 -g jenkins jenkins
USER       root
WORKDIR    /app/
RUN        chown -R jenkins:jenkins /app
COPY       sidecar/sidecar.py /app/
RUN        chmod 700 /app
ENV         PYTHONUNBUFFERED=1
USER       jenkins
CMD [ "python", "-u", "/app/sidecar.py" ]
