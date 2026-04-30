---
name: bash-style
description: >
    Bash script coding conventions and bats testing: shebang (#!/bin/bash), set -euxCo pipefail, cd "$(dirname "$0")", usage function with heredoc, readonly constants, SCREAMING_SNAKE_CASE constants, snake_case variables/functions, _snake_case local variables, bats test structure (test_helper/, setup/teardown lifecycle, run/status/output assertions). Load whenever writing, reviewing, or refactoring any Bash script (.sh files, shell scripts) or bats test (.bats files) — new files, bug fixes, function design, project setup, writing tests. Also load when PLANNING or DISCUSSING Bash/shell script implementation or test design, even before any code is written. Without this skill, you will use wrong conventions (missing set flags, wrong naming, no usage function, no readonly, wrong test directory structure) that this user explicitly does not want.
---

Read `INSTRUCTIONS.md` (in this skill's directory) for the full reference before proceeding.
