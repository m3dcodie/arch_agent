# Getting Started

This guide walks you through installing ADAG, configuring an LLM provider, and running your first compliance scan.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [LLM Provider Setup](#3-llm-provider-setup)
4. [Your First Scan](#4-your-first-scan)
5. [MCP Server Setup](#5-mcp-server-setup)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Prerequisites

| Requirement  | Minimum                     | Notes            |
| ------------ | --------------------------- | ---------------- |
| Python       | 3.10+                       | 3.11 recommended |
| LLM provider | One of four options         | See Section 3    |
| OS           | Linux, macOS, Windows (WSL) |                  |

You do **not** need:

- Terraform CLI installed
- AWS provider plugins
- Docker or any container runtime (for Modes 1 and 2)

---

## 2. Installation

### Option A — Install from PyPI (recommended)

```bash
pip install adag
```

Verify:

```bash
adag --help
```

### Option B — Editable Install from Source (for contributors)

```bash
git clone https://github.com/your-org/arch_agent.git
cd arch_agent
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode — changes to the source are reflected immediately without reinstalling.

### Option C — Install with ChromaDB support (Mode 3 RAG)

```bash
pip install "adag[rag]"
```

This adds the `chromadb` dependency for local vector store support.

---

## 3. LLM Provider Setup

ADAG supports four LLM providers. You only need one. Choose the option that fits your situation.

### Option A — GitHub Copilot (recommended for most users)

**Requirements:** An active [GitHub Copilot subscription](https://github.com/features/copilot/plans) (Individual, Business, or Enterprise).

**Step 1:** Install the GitHub CLI and authenticate.

```bash
# Ubuntu / Debian
sudo apt install gh

# macOS
brew install gh

# Authenticate with Copilot scope
gh auth login --scopes 'copilot'
```

**Step 2:** Get your OAuth token.

```bash
gh auth status --show-token
# Copy the ghu_... value shown
```

**Step 3:** Create a `.env` file in your project root.

```ini
LLM_PROVIDER=github-copilot
GITHUB_COPILOT_TOKEN=ghu_your_token_here

# Default model (available on all plans)
GITHUB_COPILOT_MODEL=gpt-4o

# Optional: use Claude for the auditor (Pro+ / Enterprise)
# AUDITOR_MODEL=claude-sonnet-4.5

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

**Verify:**

```bash
adag scan tests/fixtures/bad_terraform.tf
```

You should see violations reported for deletion protection and other policies.

---

### Option B — AWS Bedrock

**Requirements:** AWS account with Bedrock access to Claude Sonnet. Your IAM role/user must have `bedrock:InvokeModel` permissions.

**Step 1:** Configure AWS credentials.

```bash
aws configure
# or
export AWS_PROFILE=my-profile
```

**Step 2:** Request model access in the Bedrock console.

Go to AWS Console → Amazon Bedrock → Model access → Enable `Claude Sonnet`.

**Step 3:** Create `.env`.

```ini
LLM_PROVIDER=bedrock
AWS_PROFILE=default
AWS_REGION=us-east-1

# Standard Bedrock model ID
BEDROCK_MODEL=anthropic.claude-sonnet-4-5-20250929-v1:0

# Or use a cross-region inference profile (au. prefix for Asia Pacific)
# BEDROCK_MODEL=au.anthropic.claude-sonnet-4-5-20250929-v1:0

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

**Verify credentials:**

```bash
aws sts get-caller-identity
aws bedrock list-foundation-models --region ap-southeast-2
```

---

### Option C — HuggingFace (free tier available)

**Requirements:** A free HuggingFace account and API token.

**Step 1:** Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). Select "Read" scope.

**Step 2:** Create `.env`.

```ini
LLM_PROVIDER=huggingface
HF_TOKEN=hf_your_token_here
HF_MODEL=Qwen/Qwen2.5-72B-Instruct

# Use a smaller model for speed (free tier has rate limits)
# HF_MODEL=Qwen/Qwen2.5-7B-Instruct

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

**Note:** The HuggingFace free tier has rate limits. If scans are slow or return errors, wait a few minutes and retry, or upgrade to a paid tier.

---

### Option D — Ollama (fully local, no API key)

**Requirements:** [Ollama](https://ollama.com) installed and running locally.

**Step 1:** Install Ollama and pull a model.

```bash
# Install (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a recommended model
ollama pull deepseek-r1:8b

# Or a smaller/faster model
ollama pull qwen2.5:7b
```

**Step 2:** Start the Ollama server (if not already running).

```bash
ollama serve
```

**Step 3:** Create `.env`.

```ini
LLM_PROVIDER=ollama
OLLAMA_MODEL=deepseek-r1:8b
OLLAMA_BASE_URL=http://localhost:11434

DB_PROVIDER=sqlite
DB_PATH=./data/adag.db
```

**Note:** Ollama runs entirely on your machine. No data leaves your environment. Larger models produce better audit results but require more RAM (8B models need ~8GB RAM).

---

## 4. Your First Scan

ADAG ships with fixture Terraform files you can use immediately.

### Run against a non-compliant file

```bash
adag scan tests/fixtures/bad_terraform.tf
```

Expected output:

```
======================================================================
  ADAG - AI-Driven Architecture Guardrail
======================================================================

File: tests/fixtures/bad_terraform.tf
Resources Analyzed: 2
Violations Found: 3

----------------------------------------------------------------------
VIOLATIONS
----------------------------------------------------------------------

1. [HIGH] aws_db_instance / main
   Policy:      delete_protection
   Issue:       Database instance does not have deletion protection enabled.
   Line:        3
   Remediation: Add 'deletion_protection = true' to the resource block.

...

Status: FAILED
```

Exit code will be `1`.

### Run against a compliant file

```bash
adag scan tests/fixtures/good_terraform.tf
```

Expected output:

```
File: tests/fixtures/good_terraform.tf
Resources Analyzed: 2
Violations Found: 0

Status: PASSED
```

Exit code will be `0`.

### Scan a directory

```bash
adag scan ./infra/ --format json
```

### Scan with a custom policies directory

```bash
adag scan ./infra/ --policies-dir ./my-policies/
```

### Get SARIF output for GitHub

```bash
adag scan ./infra/ --format sarif > results.sarif
gh code-scanning upload --sarif results.sarif
```

---

## 5. MCP Server Setup

The MCP server lets Claude Desktop (or any MCP-compatible AI assistant) call ADAG as a tool mid-conversation.

### Claude Desktop

Add this to your Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "adag": {
      "command": "python",
      "args": ["-m", "adag.mcp_server"],
      "env": {
        "LLM_PROVIDER": "github-copilot",
        "GITHUB_COPILOT_TOKEN": "ghu_your_token_here",
        "USE_RAG": "false"
      }
    }
  }
}
```

Restart Claude Desktop. You can now ask Claude:

> "Can you check my Terraform file at `/home/me/infra/main.tf` for compliance violations?"

Claude will call `check_terraform_file` and return the violations in the conversation.

### VS Code Copilot

See [MCP.md](MCP.md) for VS Code Copilot configuration.

---

## 6. Troubleshooting

### "No module named 'adag'"

The package is not installed or the virtualenv is not active.

```bash
source venv/bin/activate
pip install adag
```

### "AWS credentials not found" (Bedrock)

```bash
aws configure list          # check which profile is active
aws sts get-caller-identity  # verify credentials work
```

If using a named profile, set `AWS_PROFILE=your-profile` in `.env`.

### "Connection refused" (Ollama)

Ollama is not running. Start it:

```bash
ollama serve
```

Check it is reachable:

```bash
curl http://localhost:11434/api/tags
```

### "Rate limit exceeded" (HuggingFace)

HuggingFace free tier limits concurrent requests. Wait 60 seconds and retry. For production use, upgrade to a paid HuggingFace Inference Endpoints plan or switch to Bedrock.

### "GitHub Copilot token invalid"

```bash
gh auth status --show-token   # verify token is still valid
gh auth refresh               # refresh if expired
```

### "No resources found" for a valid .tf file

The intake agent only extracts a specific set of resource types. If your `.tf` file contains only unsupported types (e.g., `aws_lambda_function`, `aws_ecs_service`), ADAG will report zero resources. Support for additional resource types can be added — see [CONTRIBUTING.md](CONTRIBUTING.md).

### Structured output errors (Ollama/HuggingFace)

Some smaller models do not reliably produce valid JSON even with a structured output prompt. Try a larger model:

```ini
# Ollama
OLLAMA_MODEL=qwen2.5:32b

# HuggingFace
HF_MODEL=Qwen/Qwen2.5-72B-Instruct
```
