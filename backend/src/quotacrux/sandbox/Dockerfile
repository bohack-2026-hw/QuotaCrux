# Candidate sandbox. Only the harness lives in the image; candidate code is mounted read-only per sample,
# input arrives on stdin, and no evaluator, reference output or credentials are ever present.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
COPY harness.py /opt/quotacrux/harness.py
RUN chmod 0444 /opt/quotacrux/harness.py
USER 65534:65534
WORKDIR /work
