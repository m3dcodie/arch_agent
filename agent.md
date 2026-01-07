# LLM Model selection
* by default we use AWS Bedrock provider for the agent. 
* Model Id: anthropic.claude-sonnet-4-5-20250929-v1:0
* Assume AWS Profile for access*
* Code in such a way later if we want we can change the provider and the LLM model

# Database
* Abstract the database implementation
* Default start with SqliteSaver
* Code in such a way we can use other databases. 
