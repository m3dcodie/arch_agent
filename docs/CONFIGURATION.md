# Configuration Reference

All ADAG configuration is done via environment variables, either in a `.env` file or exported in the shell. This document covers every available variable, the three operating mode configurations, and a ready-to-use `.env` template.

---

## Table of Contents

1. [Environment Variable Reference](#1-environment-variable-reference)
2. [Three Mode Configurations](#2-three-mode-configurations)
3. [.env Template](#3-env-template)

---

## 1. Environment Variable Reference

### Core

| Variable       | Default          | Description                                                                                |
| -------------- | ---------------- | ------------------------------------------------------------------------------------------ |
| `LLM_PROVIDER` | `bedrock`        | LLM backend. One of: `bedrock`, `github-models`, `github-copilot`, `huggingface`, `ollama` |
| `USE_RAG`      | `false`          | Enable RAG microservices pipeline. `true` = Mode 3, `false` = offline disk mode            |
| `ADAG_APPID`   | `archapp`        | Application ID sent to RAG microservices. Used to namespace policy collections.            |
| `DB_PROVIDER`  | `sqlite`         | Database backend for LangGraph checkpointing. Currently only `sqlite` is supported.        |
| `DB_PATH`      | `./data/adag.db` | Path to the SQLite database file used for LangGraph checkpoints.                           |

### AWS Bedrock

| Variable        | Default                                     | Description                                                                           |
| --------------- | ------------------------------------------- | ------------------------------------------------------------------------------------- |
| `AWS_PROFILE`   | _(AWS SDK default)_                         | Named AWS credential profile to use.                                                  |
| `AWS_REGION`    | `us-east-1`                                 | AWS region for Bedrock API calls.                                                     |
| `BEDROCK_MODEL` | `anthropic.claude-sonnet-4-5-20250929-v1:0` | Full Bedrock model ID, including cross-region inference profile prefix if applicable. |
| `INTAKE_MODEL`  | _(same as BEDROCK_MODEL)_                   | Override model for the intake agent role.                                             |
| `AUDITOR_MODEL` | _(same as BEDROCK_MODEL)_                   | Override model for the auditor agent role.                                            |

**Backwards compatibility:** `ANTHROPIC_MODEL` is still supported but deprecated. Use `BEDROCK_MODEL` for consistency with other providers.

**Cross-region inference profile prefixes:**

| Prefix | Region                 |
| ------ | ---------------------- |
| `us.`  | United States          |
| `eu.`  | Europe                 |
| `ap.`  | Asia Pacific (general) |
| `au.`  | Australia              |

The provider auto-detects inference profile models (2-char prefix) and switches to the Converse API automatically.

### GitHub Models

| Variable                    | Default             | Description                                                                                                                                                                                                      |
| --------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_MODELS_TOKEN`       | _(required)_        | Fine-grained PAT with **GitHub Copilot → Read** + **Models → Read** account permissions. Create one at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new). |
| `GITHUB_MODELS_MODEL`       | `openai/gpt-4.1`    | Default model for all agents. Use `vendor/model-id` format (e.g. `openai/gpt-4o-mini`).                                                                                                                          |
| `INTAKE_MODEL`              | _(same as default)_ | Override model for the intake agent role.                                                                                                                                                                        |
| `AUDITOR_MODEL`             | _(same as default)_ | Override model for the auditor agent role.                                                                                                                                                                       |
| `GITHUB_MODELS_TEMPERATURE` | `0.1`               | Sampling temperature.                                                                                                                                                                                            |
| `GITHUB_MODELS_MAX_TOKENS`  | `4096`              | Max completion tokens.                                                                                                                                                                                           |
| `GITHUB_MODELS_TIMEOUT`     | `60`                | Request timeout in seconds.                                                                                                                                                                                      |

**Available GitHub Models (as of May 2026):**

| Model                         | Notes                                          |
| ----------------------------- | ---------------------------------------------- |
| `openai/gpt-4.1`              | Default — strong reasoning, policy analysis    |
| `openai/gpt-4o-mini`          | Fast, cheap — ideal for intake structured JSON |
| `openai/gpt-4o`               | Balanced quality/cost                          |
| `openai/o1`                   | Maximum reasoning depth                        |
| `meta/llama-3.3-70b-instruct` | Open-weights alternative                       |

Model names use the `vendor/model-id` format as listed in the [GitHub Models marketplace](https://github.com/marketplace/models).

### GitHub Copilot (IDE OAuth)

| Variable               | Default             | Description                                                                                                                         |
| ---------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `GITHUB_COPILOT_TOKEN` | _(auto-resolved)_   | GitHub OAuth token with Copilot scope. If not set, resolved from `~/.config/gh/hosts.yml` or `~/.config/github-copilot/hosts.json`. |
| `GITHUB_COPILOT_MODEL` | `claude-sonnet-4.5` | Default model for all agents.                                                                                                       |
| `INTAKE_MODEL`         | _(same as default)_ | Override model for the intake agent role.                                                                                           |
| `AUDITOR_MODEL`        | _(same as default)_ | Override model for the auditor agent role.                                                                                          |

**Available Copilot models (as of April 2026):**

| Model               | Plan Required                    |
| ------------------- | -------------------------------- |
| `gpt-4o`            | Individual, Business, Enterprise |
| `gpt-4.1-mini`      | Individual, Business, Enterprise |
| `claude-sonnet-4.5` | Pro+, Enterprise                 |
| `claude-opus-4.5`   | Enterprise                       |

### HuggingFace

| Variable        | Default                    | Description                                                                                          |
| --------------- | -------------------------- | ---------------------------------------------------------------------------------------------------- |
| `HF_TOKEN`      | _(required)_               | HuggingFace API token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). |
| `HF_MODEL`      | `Qwen/Qwen2.5-7B-Instruct` | Default model served via HuggingFace Inference Router.                                               |
| `INTAKE_MODEL`  | _(same as HF_MODEL)_       | Override model for the intake agent role.                                                            |
| `AUDITOR_MODEL` | _(same as HF_MODEL)_       | Override model for the auditor agent role.                                                           |

**Recommended HuggingFace models for auditing:**

| Model                                | Size | Notes                    |
| ------------------------------------ | ---- | ------------------------ |
| `Qwen/Qwen2.5-72B-Instruct`          | 72B  | Best quality, slower     |
| `Qwen/Qwen2.5-7B-Instruct`           | 7B   | Fast, free tier friendly |
| `mistralai/Mistral-7B-Instruct-v0.3` | 7B   | Alternative              |

### Ollama

| Variable          | Default                  | Description                                                             |
| ----------------- | ------------------------ | ----------------------------------------------------------------------- |
| `OLLAMA_MODEL`    | `deepseek-r1:8b`         | Model name as shown in `ollama list`.                                   |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of the Ollama server.                                          |
| `OLLAMA_TIMEOUT`  | `120`                    | Request timeout in seconds. Increase for large models on slow hardware. |
| `INTAKE_MODEL`    | _(same as OLLAMA_MODEL)_ | Override model for the intake agent role.                               |
| `AUDITOR_MODEL`   | _(same as OLLAMA_MODEL)_ | Override model for the auditor agent role.                              |

### RAG Microservices (Mode 3 only)

| Variable          | Default                 | Description                                    |
| ----------------- | ----------------------- | ---------------------------------------------- |
| `RAG_CONTEXT_URL` | `http://localhost:8000` | Base URL for the context augmentation service. |
| `RAG_INGEST_URL`  | `http://localhost:8001` | Base URL for the ingestion service.            |
| `RAG_CHUNK_URL`   | `http://localhost:8002` | Base URL for the chunking service.             |
| `RAG_EMBED_URL`   | `http://localhost:8003` | Base URL for the embedding service.            |
| `RAG_VECTOR_URL`  | `http://localhost:8004` | Base URL for the vector store service.         |

### CLI Flags (override env vars per-invocation)

| Flag                    | Env Equivalent  | Description                                     |
| ----------------------- | --------------- | ----------------------------------------------- |
| `--llm-provider` / `-l` | `LLM_PROVIDER`  | LLM provider for this scan.                     |
| `--policies-dir` / `-p` | —               | Custom policies directory (replaces built-ins). |
| `--format` / `-f`       | —               | Output format: `text`, `json`, `sarif`.         |
| `--no-rag`              | `USE_RAG=false` | Force offline disk mode for this scan.          |
| `--quiet` / `-q`        | —               | Suppress headers and banners.                   |

---

## 2. Three Mode Configurations

### Mode 1 — Offline (recommended for CI/CD)

Scans against policies loaded directly from disk. No external services required.

```ini
# .env (Mode 1 — GitHub Models, recommended)
LLM_PROVIDER=github-models
GITHUB_MODELS_TOKEN=github_pat_your_token_here
GITHUB_MODELS_MODEL=openai/gpt-4.1

INTAKE_MODEL=openai/gpt-4o-mini
AUDITOR_MODEL=openai/gpt-4.1

USE_RAG=false

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

```ini
# .env (Mode 1 — Bedrock)
LLM_PROVIDER=bedrock
AWS_PROFILE=default
AWS_REGION=us-east-1
BEDROCK_MODEL=anthropic.claude-sonnet-4-5-20250929-v1:0

USE_RAG=false

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

```ini
# .env (Mode 1 — Ollama, fully local)
LLM_PROVIDER=ollama
OLLAMA_MODEL=deepseek-r1:8b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=120

USE_RAG=false

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

### Mode 2 — MCP Server

Same `.env` as Mode 1. The MCP server is started differently:

```bash
python -m adag.mcp_server
```

Or configured in Claude Desktop:

```json
{
  "mcpServers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"],
      "env": {
        "LLM_PROVIDER": "github-models",
        "GITHUB_MODELS_TOKEN": "github_pat_your_token_here",
        "GITHUB_MODELS_MODEL": "openai/gpt-4.1",
        "USE_RAG": "false"
      }
    }
  }
}
```

### Mode 3 — Advanced RAG

Requires the RAG microservices to be running. See [RAG_PIPELINE.md](RAG_PIPELINE.md) for setup.

```ini
# .env (Mode 3)
LLM_PROVIDER=github-models
GITHUB_MODELS_TOKEN=github_pat_your_token_here
GITHUB_MODELS_MODEL=openai/gpt-4.1

USE_RAG=true
ADAG_APPID=archapp

RAG_CONTEXT_URL=http://localhost:8000
RAG_INGEST_URL=http://localhost:8001
RAG_CHUNK_URL=http://localhost:8002
RAG_EMBED_URL=http://localhost:8003
RAG_VECTOR_URL=http://localhost:8004

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

---

## 3. .env Template

Copy this to `.env` in the project root and fill in the values for your chosen provider.

```ini
# ============================================================
# ADAG Configuration Template
# ============================================================
# Choose ONE provider section and fill it in. Comment out the rest.
# ============================================================

# ------------------------------------------------------------
# REQUIRED: LLM Provider
# Options: bedrock | github-models | github-copilot | huggingface | ollama
# ------------------------------------------------------------
LLM_PROVIDER=github-models

# ------------------------------------------------------------
# PROVIDER: GitHub Models (recommended for GitHub Copilot users)
# Create a fine-grained PAT: https://github.com/settings/personal-access-tokens/new
# Account permissions: GitHub Copilot → Read, Models → Read
# ------------------------------------------------------------
GITHUB_MODELS_TOKEN=github_pat_your_token_here
GITHUB_MODELS_MODEL=openai/gpt-4.1
INTAKE_MODEL=openai/gpt-4o-mini
AUDITOR_MODEL=openai/gpt-4.1

# ------------------------------------------------------------
# PROVIDER: GitHub Copilot IDE OAuth (comment out if using github-models)
# ------------------------------------------------------------
# LLM_PROVIDER=github-copilot
# GITHUB_COPILOT_TOKEN=ghu_your_token_here
# GITHUB_COPILOT_MODEL=gpt-4o

# ------------------------------------------------------------
# PROVIDER: AWS Bedrock (comment out if using Copilot)
# ------------------------------------------------------------
# LLM_PROVIDER=bedrock
# AWS_PROFILE=default
# AWS_REGION=us-east-1
# BEDROCK_MODEL=anthropic.claude-sonnet-4-5-20250929-v1:0
# # Or use cross-region inference profile:
# # BEDROCK_MODEL=au.anthropic.claude-sonnet-4-5-20250929-v1:0

# ------------------------------------------------------------
# PROVIDER: HuggingFace (comment out if using Copilot)
# ------------------------------------------------------------
# LLM_PROVIDER=huggingface
# HF_TOKEN=hf_your_token_here
# HF_MODEL=Qwen/Qwen2.5-72B-Instruct

# ------------------------------------------------------------
# PROVIDER: Ollama (comment out if using Copilot)
# ------------------------------------------------------------
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=deepseek-r1:8b
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_TIMEOUT=120

# ------------------------------------------------------------
# RAG Mode (set to true for Mode 3 / Advanced RAG)
# ------------------------------------------------------------
USE_RAG=false
ADAG_APPID=archapp

# RAG service URLs (only needed when USE_RAG=true)
# RAG_CONTEXT_URL=http://localhost:8000
# RAG_INGEST_URL=http://localhost:8001
# RAG_CHUNK_URL=http://localhost:8002
# RAG_EMBED_URL=http://localhost:8003
# RAG_VECTOR_URL=http://localhost:8004

# ------------------------------------------------------------
# Database (LangGraph checkpointing)
# ------------------------------------------------------------
DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```
