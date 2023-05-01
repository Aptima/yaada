ARG  YAADA_BASE_IMAGE=python:3.8
ARG  PLATFORM=amd64
FROM --platform=linux/${PLATFORM} ${YAADA_BASE_IMAGE}
ARG PLATFORM=amd64

RUN echo "building for platform: linux/${PLATFORM}"
RUN apt-get update && apt-get install -y dos2unix

RUN apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \ 
    jq \
    dos2unix

# Install Docker
RUN mkdir -p /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update
RUN apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
# RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
# RUN echo \
#   "deb [arch=${PLATFORM}} signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
#   $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
# RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io



RUN curl -L "https://github.com/docker/compose/releases/download/1.29.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose
RUN ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Install pipenv

RUN python -m pip install --upgrade pip
RUN pip install pipenv

# Set up workspace and environment

ENV YAADA_LOGLEVEL=ERROR
ENV TRANSFORMERS_CACHE=/workspace/modelcache/transformers
ENV WORKON_HOME=/workspace/.pipenv_local
ENV YAADA_HOSTNAME=host.docker.internal
WORKDIR /workspace
ADD ./entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"] 
