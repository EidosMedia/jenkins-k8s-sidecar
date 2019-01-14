FROM       python:3.6-slim-stretch
RUN        pip install --no-cache-dir kubernetes==6.0.0
RUN        pip install --no-cache-dir paramiko
RUN        pip install --no-cache-dir ipython
RUN groupadd -r -g 999 sidecaruser && useradd -r -u 999 -g sidecaruser sidecaruser
USER sidecaruser
COPY       sidecar/sidecar.py /app/
ENV         PYTHONUNBUFFERED=1
WORKDIR    /app/
CMD [ "python", "-u", "/app/sidecar.py" ]
