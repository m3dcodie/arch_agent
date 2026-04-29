# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog (https://keepachangelog.com/) and this
project follows Semantic Versioning (https://semver.org/).

## [1.0.0] - 2026-04-29

### Added

- Initial public release (v1.0.0):
  - Multi-agent LLM-driven Terraform policy scanner (Intake, Policy Analyst, Auditor)
  - Deterministic HCL parsing and 10 built-in compliance policies
  - Per-agent model selection and provider abstraction (Bedrock, Copilot, HF, Ollama)
  - RAG mode (ChromaDB) for scaling policy documents; MCP server for AI assistant integration
  - Output formats: text, JSON, SARIF
  - CI-ready behavior and example GitHub Actions workflow

### Notes

- Repository history has been rewritten into a single commit (v1.0.0) for a clean start.
- When publishing a new release, update `pyproject.toml`, `README.md` (version badge),
  and add a new section to this changelog with date and summary.

For release process guidance see docs/RELEASING.md.
