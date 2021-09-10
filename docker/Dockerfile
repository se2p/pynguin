# SPDX-FileCopyrightText: 2019-2021 Pynguin Contributors
#
# SPDX-License-Identifier: LGPL-3.0-or-later

###############################################################################
# Dockerfile to build a Docker container image for Pynguin.                   #
# This is a multi-stage image, i.e., it first builds the Pynguin tar-ball     #
# from the sources and installs it in a later stage for execution.            #
# The image is built in a way that it accepts all command-line parameters for #
# Pynguin as parameters to Docker's `run` command.                            #
###############################################################################

# Build stage for Pynguin
FROM python:3.8.10-slim-buster AS build
MAINTAINER Stephan Lukasczyk <stephan@lukasczyk.me>
ENV POETRY_VERSION "1.1.6"

COPY . /pynguin-build

WORKDIR /pynguin-build


RUN pip install poetry==$POETRY_VERSION \
    && poetry config virtualenvs.create false \
    && poetry build


# Execution stage for Pynguin
FROM python:3.8.10-slim-buster AS execute
ENV PYNGUIN_VERSION "0.9.3"
ENV PYNGUIN_DANGER_AWARE ""

# Temporarily add `git' here to install our MutPy fork from GitHub, which is a
# dependency of Pynguin
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /pynguin

COPY --from=build /pynguin-build/dist/pynguin-$PYNGUIN_VERSION.tar.gz .
COPY --from=build /pynguin-build/pynguin-docker.sh .

RUN pip install /pynguin/pynguin-$PYNGUIN_VERSION.tar.gz

ENTRYPOINT ["/pynguin/pynguin-docker.sh"]
CMD []
