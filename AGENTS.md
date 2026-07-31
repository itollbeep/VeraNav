# VeraNav Project Instructions

These instructions apply to the entire repository.

## 1. Project purpose

VeraNav is a reproducible framework for evaluating the reliability, consistency, fault detection, and recovery behaviour of navigation state estimators under sensor degradation and faults.

The current target is VeraNav V0.1. It is not yet a new navigation algorithm, product, or production safety system.

## 2. Current V0.1 scope

V0.1 is limited to:

- deterministic synthetic trajectory generation
- synthetic IMU generation
- a minimal error-state Kalman filter
- GNSS position updates
- GNSS outage and bias fault injection
- trajectory error metrics
- NIS and NEES consistency metrics
- deterministic Monte Carlo experiments
- configuration files
- automated tests
- reproducible reports

Do not add ROS, ROS2, PX4, OpenVINS, KF-GINS, OB_GINS, Docker, large datasets, or GUI components unless explicitly requested.

## 3. Development environment

Primary environment:

- Ubuntu 22.04 under WSL2
- Python 3.10
- C++17 when C++ is introduced
- CMake and Ninja for C++ builds
- repository path: /home/itoll/GitHub/VeraNav

V0.1 should be Python-first. Do not introduce C++ merely for perceived performance.

## 4. Scientific requirements

All scientific code must:

- use explicit coordinate frames and units
- document state-vector ordering
- distinguish nominal state and error state
- define covariance dimensions and conventions
- define quaternion and rotation conventions
- use deterministic random seeds
- avoid hidden global state
- avoid silently correcting invalid inputs
- validate dimensions, timestamps, and numerical finiteness
- include tests for important equations and edge cases
- make assumptions explicit in code and documentation

Do not invent physical parameters, sensor specifications, benchmark results, or experimental conclusions.

## 5. Software quality

Use:

- small, focused modules
- type hints for public Python interfaces
- concise docstrings for public functions and classes
- pathlib instead of manually constructed path strings
- standard logging instead of ad hoc print statements in library code
- configuration-driven experiments
- deterministic and isolated tests
- clear error messages
- UTF-8 text files
- English identifiers and technical documentation

Avoid:

- unnecessary abstractions
- premature optimization
- duplicated logic
- hidden file-system side effects
- hard-coded machine-specific paths
- generated files committed to source control
- large binary files in Git
- decorative comments or obvious AI-generated filler

## 6. Repository and licensing rules

- The repository uses Apache License 2.0.
- Do not copy GPL-licensed source code into this repository.
- External estimators must remain separate upstream repositories or independent processes.
- Record upstream repository URLs, versions, and commit SHAs when integrations are later added.
- Do not add external code, datasets, model files, archives, or generated experiment outputs without explicit approval.
- Do not expose credentials, tokens, private paths, or personal data.

## 7. Change-control rules

Before modifying files:

1. inspect the relevant files
2. run git status
3. identify the smallest necessary change
4. preserve existing behaviour unless the task explicitly changes it

Do not:

- modify files outside this repository
- install system packages
- change WSL or Windows settings
- delete files
- rewrite Git history
- commit
- push
- create branches
- open pull requests
- enable GitHub Actions
- add secrets
- use paid services

unless the user explicitly authorizes that exact action.

## 8. Verification requirements

For every implementation task:

- run the narrowest relevant tests first
- run the full available test suite before completion when practical
- report every command executed
- report test results and exit codes
- report all created, modified, moved, or deleted paths
- report whether any files outside the repository were affected
- show git status at the end
- do not claim success when verification was not performed

## 9. Communication requirements

At the end of every task, provide:

1. a concise description of what was done
2. exact affected paths
3. commands executed
4. test and validation results
5. exit codes
6. Git status
7. unresolved risks
8. the recommended next step

Be explicit when information is uncertain or when a task was only partially completed.

## 10. Response language

- All progress updates, explanations, audit reports, validation reports, and final task summaries must be written in Chinese.
- Code, commands, file names, paths, API names, identifiers, mathematical symbols, and established technical terms may remain in English.
- Repository source code and technical documentation should remain in English unless the user explicitly requests otherwise.
