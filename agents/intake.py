"""
Intake agent - Parses Terraform/IaC code and extracts resource definitions.
"""

import json
import re
import time
from typing import Dict, Any, Type, TypeVar
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from core.state import AgentState
from models.violations import TerraformResource, ResourceList, AuditStatus

T = TypeVar("T", bound=BaseModel)

_RATE_LIMIT_SIGNALS = ("429", "rate limit", "too many requests", "ratelimit")


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RATE_LIMIT_SIGNALS)


def _invoke_structured(
    llm: BaseChatModel, prompt: ChatPromptTemplate, inputs: dict, schema: Type[T]
) -> T:
    """
    Invoke the LLM and parse the result into a Pydantic model.

    Tries with_structured_output first; if the provider doesn't support it
    (e.g. Ollama, or HF router models), falls back to plain invoke + JSON extraction.
    Retries up to 3 times with exponential backoff on rate-limit (429) errors.
    """

    def _plain_invoke():
        chain = prompt | llm
        response = chain.invoke(inputs)
        raw = response.content if hasattr(response, "content") else str(response)
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in model output: {raw[:300]}")
        return schema(**json.loads(match.group()))

    # OpenAI-compatible providers (including GitHub Copilot) require
    # method="function_calling" — their schemas don't pass the strict
    # structured-output validator introduced in langchain-openai 0.3.
    from langchain_openai import ChatOpenAI

    structured_kwargs = {}
    if isinstance(llm, ChatOpenAI):
        structured_kwargs["method"] = "function_calling"

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(3):
        try:
            chain = prompt | llm.with_structured_output(schema, **structured_kwargs)
            return chain.invoke(inputs)
        except Exception as exc:
            if _is_rate_limit(exc):
                wait = 15 * (2**attempt)  # 15s, 30s, 60s
                print(
                    f"[INTAKE] Rate limited — retrying in {wait}s (attempt {attempt + 1}/3)"
                )
                time.sleep(wait)
                last_exc = exc
                continue
            # Non-rate-limit error: fall back to plain invoke immediately
            try:
                return _plain_invoke()
            except Exception as plain_exc:
                if _is_rate_limit(plain_exc):
                    wait = 15 * (2**attempt)
                    print(f"[INTAKE] Rate limited (plain) — retrying in {wait}s")
                    time.sleep(wait)
                    last_exc = plain_exc
                    continue
                raise plain_exc
    raise last_exc


INTAKE_PROMPT = """You are a Terraform code parser. Your task is to extract all auditable infrastructure resources from the provided Terraform code.

Focus on these resource types:
- aws_db_instance
- aws_rds_cluster
- aws_db_cluster_instance
- aws_kms_key
- aws_s3_bucket
- aws_s3_bucket_public_access_block

For each resource, extract:
1. resource_type: The Terraform resource type
2. resource_name: The resource identifier/name
3. attributes: All configuration attributes as a dictionary
4. line_number: Approximate line number (if determinable)

Terraform Code:
```
{iac_code}
```

Return ONLY a valid JSON object with this structure:
{{
  "resources": [
    {{
      "resource_type": "aws_db_instance",
      "resource_name": "example",
      "attributes": {{"key": "value"}},
      "line_number": 10
    }}
  ]
}}

If no database resources are found, return: {{"resources": []}}
"""


def _extract_provider_blocks(iac_code: str) -> list:
    """
    Deterministically extract provider blocks from Terraform code.
    Provider blocks have fixed syntax so Python regex is more reliable
    than asking the LLM to extract them.

    Returns a list of dicts ready to be used as TerraformResource.model_dump().
    """
    providers = []
    # Match:  provider "NAME" {  ...  }
    pattern = re.compile(r'provider\s+"(\w+)"\s*\{([^}]*)\}', re.DOTALL)
    for i, m in enumerate(pattern.finditer(iac_code)):
        provider_name = m.group(1)
        body = m.group(2)
        line_number = iac_code[: m.start()].count("\n") + 1
        # Extract simple key = "value" pairs from the provider body
        attrs: Dict[str, Any] = {}
        for kv in re.finditer(r'(\w+)\s*=\s*"([^"]+)"', body):
            attrs[kv.group(1)] = kv.group(2)
        providers.append(
            {
                "resource_type": "provider",
                "resource_name": provider_name,
                "attributes": attrs,
                "line_number": line_number,
            }
        )
    return providers


def intake_node(state: AgentState, llm: BaseChatModel) -> Dict[str, Any]:
    """
    Parse Terraform code and extract database resources.

    Args:
        state: Current agent state
        llm: Language model instance

    Returns:
        Dict with updated state fields
    """
    try:
        # Create prompt
        prompt = ChatPromptTemplate.from_template(INTAKE_PROMPT)

        # Invoke LLM with provider-aware structured output
        result = _invoke_structured(
            llm, prompt, {"iac_code": state["iac_code"]}, ResourceList
        )

        parsed_resources = [
            r.model_dump() for r in (result.resources if result else [])
        ]

        # Always extract provider blocks deterministically (not via LLM)
        provider_resources = _extract_provider_blocks(state["iac_code"])
        # Prepend providers so region is visible to the auditor first
        all_resources = provider_resources + parsed_resources

        return {
            "parsed_resources": all_resources,
            "current_node": "intake",
            "status": AuditStatus.IN_PROGRESS,
            "messages": [
                f"[INTAKE] Parsed {len(all_resources)} resource(s) ({len(provider_resources)} provider block(s))"
            ],
        }

    except Exception as e:
        return {
            "parsed_resources": [],
            "current_node": "intake",
            "status": AuditStatus.ERROR,
            "error_message": f"Intake parsing failed: {str(e)}",
            "messages": [f"[INTAKE] ERROR: {str(e)}"],
        }
