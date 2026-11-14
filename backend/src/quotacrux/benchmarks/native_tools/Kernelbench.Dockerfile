FROM nvidia/cuda:12.6.3-devel-ubuntu22.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip g++ ninja-build ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cu126
RUN python3 -m pip install --no-cache-dir numpy==2.2.6
COPY kernel_harness.py kernel_check.py /opt/quotacrux/
USER 65534:65534
WORKDIR /tmp
