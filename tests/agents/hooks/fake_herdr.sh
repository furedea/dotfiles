#!/bin/sh
set -eu
exec cat "${HERDR_TEST_DIRECTORY}/${1}s.json"
