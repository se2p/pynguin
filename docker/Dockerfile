# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

###############################################################################
# Dockerfile to build a Docker container image for Pynguin.                   #
# This is a multi-stage image, i.e., it first builds the Pynguin tar-ball     #
# from the sources and installs it in a later stage for execution.            #
# The image is built in a way that it accepts all command-line parameters for #
# Pynguin as parameters to Docker's `run` command.                            #
###############################################################################

# Build stage for Pynguin
FROM python:3.10.16-slim-bullseye AS build
LABEL org.opencontainers.image.authors="Stephan Lukasczyk <stephan@pynguin.eu>"
ENV POETRY_VERSION "1.8.4"

WORKDIR /pynguin-build

# Python shall not write the byte code to *.pyc files; they cannot be cached between
# runs of the container anyway, hence we save the required time and resources for that
ENV PYTHONDONTWRITEBYTECODE 1
# Prevent Python from buffering output that is written to STDOUT/STDERR; this allows to
# monitor the output in real time
ENV PYTHONUNBUFFERED 1

COPY . .

RUN pip install poetry==$POETRY_VERSION \
    && poetry config virtualenvs.create false \
    && poetry build


# Execution stage for Pynguin
FROM python:3.10.16-slim-bullseye AS execute

# Set environment variables
# Set the Pynguin version
ENV PYNGUIN_VERSION "0.41.0.dev0"
# Pynguin requires to set the variable to show it that the user is aware that running
# Pynguin executes third-party code, which could cause arbitrary harm to the system.
# By setting the variable, the user acknowledges that they are aware of this.  In the
# container this is not too much of an issue (if we forget about breaking out of the
# container and similar things, of course).
ENV PYNGUIN_DANGER_AWARE ""
# Python shall not write the byte code to *.pyc files; they cannot be cached between
# runs of the container anyway, hence we save the required time and resources for that
ENV PYTHONDONTWRITEBYTECODE 1
# Prevent Python from buffering output that is written to STDOUT/STDERR; this allows to
# monitor the output in real time
ENV PYTHONUNBUFFERED 1
# Disable random hash seeding for reproducible runs
ENV PYTHONHASHSEED 0

WORKDIR /pynguin

COPY --from=build /pynguin-build/dist/pynguin-${PYNGUIN_VERSION}-py3-none-any.whl .
COPY --from=build /pynguin-build/pynguin-docker.sh .

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install /pynguin/pynguin-${PYNGUIN_VERSION}-py3-none-any.whl \
    mypy==1.13.0 \
    typing-extensions==4.12.2

ENTRYPOINT ["/pynguin/pynguin-docker.sh"]
CMD []
