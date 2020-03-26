#!/usr/bin/env bash

INPUT_DIR="/input"
OUTPUT_DIR="/output"

function help_message {
  echo ""
  echo "pynguin-docker.sh"
  echo "Script to run Pynguin inside a Docker container"
  echo "This script can only be used inside a Docker container, it checks that certain"
  echo "mounts are set, installs possible dependencies of a project for Pynguin,"
  echo "executes Pynguin and provides the results to an output share."
  echo "In order to use this, you have to provide two mount points with your Docker run"
  echo "command:"
  echo "docker run \\"
  echo "    --mount type=bind,source=/path/to/project,target=${INPUT_DIR} \\"
  echo "    --mount type=bind,source=/path/for/output,target=${OUTPUT_DIR} \\"
  echo "    ..."
  echo ""
}

function error_echo {
  RED="\033[0;31m"
  NC="\033[0m"
  echo -e "${RED}ERROR: ${1}${NC}\n"
}


# Check if we are in a running Docker container.
# TODO This does not seem to be the most stable variant of doing this, as the
# TODO .dockerenv file is not supposed to be used for this.  Change this, if we have a
# TODO more stable variant to detect whether we are inside a container!
if [[ ! -f /.dockerenv ]]
then
  error_echo "This script is only supposed to be run within a Docker container!"
  error_echo "You cannot run it as a standalone script!"
  help_message
  exit 1
fi

# Check if the /input mount point is present
if [[ ! -d ${INPUT_DIR} ]]
then
  error_echo "You need to specify a mount to ${INPUT_DIR}"
  help_message
  exit 1
fi

# Check if the /output mount point is present
if [[ ! -d ${OUTPUT_DIR} ]]
then
  error_echo "You need to specify a mount to ${OUTPUT_DIR}"
  help_message
  exit 1
fi

# Install dependencies from requirements.txt file, if present in /input
if [[ -f "${INPUT_DIR}/requirements.txt" ]]
then
  echo "Install requirements"
  pip install -r "${INPUT_DIR}/requirements.txt"
fi

# Execute Pynguin with all arguments passed to this script
pynguin "$@"
