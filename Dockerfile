FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        gnupg \
        make \
        nodejs \
        npm \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Terraform
ARG TERRAFORM_VERSION=1.7.5
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
        -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin/ \
    && rm /tmp/terraform.zip

# tflint
RUN curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

# Python tooling
RUN pip install --no-cache-dir \
        ruff \
        pre-commit \
        ansible \
        ansible-lint

WORKDIR /workspace
COPY . .

RUN pip install --no-cache-dir -r python/requirements.txt

CMD ["make", "ci"]
