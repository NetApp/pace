FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        gnupg \
        make \
        nodejs \
        npm \
        unzip \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Go
ARG GO_VERSION=1.22.4
RUN wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -O /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

# Terraform + tflint + Python tooling
ARG TERRAFORM_VERSION=1.7.5
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
        -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin/ \
    && rm /tmp/terraform.zip \
    && curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash \
    && pip install --no-cache-dir \
        ruff \
        pyyaml \
        pre-commit \
        ansible \
        ansible-lint

WORKDIR /workspace
COPY . .

RUN pip install --no-cache-dir -r python/requirements.txt

CMD ["make", "ci"]
