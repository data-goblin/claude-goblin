# Dockerfile for Claude Code sandboxed development environment
# Python-based project using uv for package management

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm

ARG TZ=UTC
ARG CLAUDE_VERSION=latest
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV DEVCONTAINER=true
ENV TZ=${TZ}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        git \
        procps \
        sudo \
        fzf \
        zsh \
        man-db \
        unzip \
        gnupg2 \
        curl \
        wget \
        iptables \
        ipset \
        iproute2 \
        dnsutils \
        aggregate \
        jq \
        nano \
        vim \
        ca-certificates \
        nodejs \
        npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} -s /bin/zsh \
    && echo ${USERNAME} ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Set up bash history persistence
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R ${USERNAME}:${USERNAME} /commandhistory \
    && echo "$SNIPPET" >> /home/${USERNAME}/.bashrc \
    && echo "$SNIPPET" >> /home/${USERNAME}/.zshrc

# Install uv (Python package manager)
ENV UV_LINK_MODE=copy
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/ \
    && mv /root/.local/bin/uvx /usr/local/bin/ \
    && chmod +x /usr/local/bin/uv /usr/local/bin/uvx

# Install zsh with powerline10k theme
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v1.2.1/zsh-in-docker.sh)" -- \
    -t robbyrussell \
    -p git \
    -p fzf

# Create workspace directory
RUN mkdir -p /workspace && chown -R ${USERNAME}:${USERNAME} /workspace

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

# Create Claude config directory
RUN mkdir -p /home/${USERNAME}/.claude && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.claude

# Copy firewall initialization script
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD: /usr/local/bin/init-firewall.sh" >> /etc/sudoers.d/${USERNAME}

# Set default editor and shell
ENV EDITOR=nano
ENV SHELL=/bin/zsh

# Switch to non-root user
USER ${USERNAME}

WORKDIR /workspace
