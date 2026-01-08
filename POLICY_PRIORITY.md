# Policy Priority Order for Phase 2 MVP

## 🎯 Prioritization Framework

Policies are prioritized based on three factors:
1. **Risk Impact:** Severity of security/compliance breach
2. **Frequency:** How often this issue appears in real-world IaC
3. **Demonstration Value:** Shows RAG system's versatility

---

## 📊 Priority Order (Top 10 Policies)

### **Tier 1: Critical Security (Weeks 1-2)**

#### 1. ✅ Deletion Protection (EXISTING)
- **Status:** Already implemented in Phase 1
- **Severity:** HIGH
- **Resources:** `aws_db_instance`, `aws_rds_cluster`
- **Why Priority #1:** Data loss prevention is non-negotiable
- **File:** [`policies/delete_protection.md`](policies/delete_protection.md:1)

#### 2. 🔐 Encryption at Rest
- **Severity:** HIGH
- **Resources:** `aws_db_instance`, `aws_rds_cluster`, `aws_s3_bucket`, `aws_ebs_volume`
- **Why Priority #2:** 
  - Compliance requirement (GDPR, HIPAA, PCI-DSS)
  - Most common security audit failure
  - Affects multiple resource types (good for RAG testing)
- **Example Violation:** Database without `storage_encrypted = true`
- **Business Impact:** Data breach fines can reach millions

#### 3. 🌐 Public Access Block
- **Severity:** HIGH
- **Resources:** `aws_s3_bucket`, `aws_db_instance`, `aws_security_group`
- **Why Priority #3:**
  - Frequent cause of data leaks (S3 bucket breaches)
  - Easy to accidentally misconfigure
  - High visibility in security audits
- **Example Violation:** S3 bucket with `acl = "public-read"`
- **Business Impact:** Public data exposure, regulatory fines

---

### **Tier 2: Availability & Resilience (Week 3)**

#### 4. 🔄 Multi-AZ Requirement
- **Severity:** MEDIUM
- **Resources:** `aws_db_instance`, `aws_rds_cluster`, `aws_elasticache_cluster`
- **Why Priority #4:**
  - Production availability requirement
  - Common oversight in non-prod → prod promotions
  - Demonstrates policy context (only for production)
- **Example Violation:** Production DB with `multi_az = false`
- **Business Impact:** Downtime during AZ failures

#### 5. 💾 Backup Retention
- **Severity:** MEDIUM
- **Resources:** `aws_db_instance`, `aws_rds_cluster`, `aws_dynamodb_table`
- **Why Priority #5:**
  - Disaster recovery requirement
  - Often forgotten until needed
  - Shows numeric threshold checking (e.g., `backup_retention_period >= 7`)
- **Example Violation:** `backup_retention_period = 0`
- **Business Impact:** Data loss during incidents

#### 6. 🔄 Automated Backups Enabled
- **Severity:** MEDIUM
- **Resources:** `aws_db_instance`, `aws_rds_cluster`
- **Why Priority #6:**
  - Complements backup retention policy
  - Simple boolean check (good for testing)
- **Example Violation:** `backup_window` not defined
- **Business Impact:** Manual backup burden, recovery delays

---

### **Tier 3: Operational Excellence (Week 4)**

#### 7. 🏷️ Required Tagging
- **Severity:** LOW
- **Resources:** ALL (universal policy)
- **Why Priority #7:**
  - Cost allocation requirement
  - Demonstrates universal policy application
  - Shows metadata validation (not just security)
- **Example Violation:** Missing `Environment`, `Owner`, `CostCenter` tags
- **Business Impact:** Cost tracking issues, resource ownership confusion

#### 8. 📝 Naming Conventions
- **Severity:** LOW
- **Resources:** ALL (universal policy)
- **Why Priority #8:**
  - Organizational standard enforcement
  - Shows regex/pattern matching in policies
  - Good for demonstrating non-security use cases
- **Example Violation:** Resource name doesn't match `^[a-z][a-z0-9-]*$`
- **Business Impact:** Inconsistent infrastructure, harder troubleshooting

#### 9. 🔒 KMS Key Rotation
- **Severity:** MEDIUM
- **Resources:** `aws_kms_key`
- **Why Priority #9:**
  - Security best practice
  - Compliance requirement (some frameworks)
  - Shows time-based policy checking
- **Example Violation:** `enable_key_rotation = false`
- **Business Impact:** Cryptographic key compromise risk

#### 10. 🌍 Allowed Regions
- **Severity:** MEDIUM
- **Resources:** ALL (universal policy)
- **Why Priority #10:**
  - Data sovereignty requirement
  - Demonstrates company-specific policies
  - Shows RAG's ability to handle custom rules
- **Example Violation:** Resource in `us-west-2` when only `us-east-1` allowed
- **Business Impact:** Compliance violations, data residency issues

---

## 📈 Implementation Strategy

### Phase 2.1 (Week 1-2): Core Security Trio
Focus on **Policies #1-3** (Deletion Protection, Encryption, Public Access)
- **Rationale:** Highest risk, most common violations
- **Goal:** Demonstrate RAG can handle critical security policies
- **Success Metric:** Catch 90%+ of common security misconfigurations

### Phase 2.2 (Week 3): Availability Policies
Add **Policies #4-6** (Multi-AZ, Backup Retention, Automated Backups)
- **Rationale:** Production readiness checks
- **Goal:** Show RAG handles different policy types (boolean, numeric thresholds)
- **Success Metric:** Identify production-readiness gaps

### Phase 2.3 (Week 4): Operational Policies
Add **Policies #7-10** (Tagging, Naming, KMS, Regions)
- **Rationale:** Operational excellence, custom rules
- **Goal:** Demonstrate RAG's versatility beyond security
- **Success Metric:** Enforce organizational standards

---

## 🎓 Why This Order?

### 1. **Risk-First Approach**
Start with policies that prevent catastrophic failures:
- Data loss (deletion protection)
- Data breaches (encryption, public access)
- Downtime (multi-AZ)

### 2. **Incremental Complexity**
- **Simple:** Boolean checks (deletion_protection = true)
- **Medium:** Numeric thresholds (backup_retention >= 7)
- **Complex:** Pattern matching (naming conventions), context-aware (region restrictions)

### 3. **Stakeholder Value**
- **Security Team:** Policies #1-3, #9 (immediate security wins)
- **Operations Team:** Policies #4-6 (reliability improvements)
- **Finance Team:** Policy #7 (cost tracking)
- **Compliance Team:** Policies #2, #3, #10 (regulatory requirements)

### 4. **RAG System Validation**
This order tests RAG capabilities progressively:
- **Policies #1-3:** Basic retrieval (resource type matching)
- **Policies #4-6:** Context-aware retrieval (production vs. non-prod)
- **Policies #7-10:** Universal policies (apply to all resources)

---

## 📋 Policy Template Structure

Each policy should follow this markdown structure for consistent RAG indexing:

```markdown
# [Policy Title]

## Policy ID
`policy_id`

## Severity
**HIGH** | **MEDIUM** | **LOW**

## Description
Clear explanation of what this policy enforces and why.

## Scope
List of resource types this applies to:
- `aws_resource_type_1`
- `aws_resource_type_2`

## Requirements
Specific technical requirements (e.g., "deletion_protection must be true")

## Rationale
Business/security justification for this policy

## Examples

### ✅ Compliant
```hcl
[compliant code example]
```

### ❌ Non-Compliant
```hcl
[non-compliant code example]
```

## Remediation
Step-by-step fix instructions

## Exceptions
Any valid exceptions to this policy

## References
- External documentation links
```

---

## 🔄 Future Policies (Phase 3+)

### Additional High-Value Policies
11. **VPC Endpoint Usage** (cost optimization)
12. **Instance Type Restrictions** (cost control)
13. **Logging Enabled** (audit trail)
14. **Versioning Enabled** (S3 data protection)
15. **SSL/TLS Enforcement** (data in transit)
16. **IAM Role Least Privilege** (access control)
17. **Security Group Ingress Rules** (network security)
18. **Snapshot Encryption** (backup security)
19. **CloudWatch Alarms** (monitoring)
20. **Lifecycle Policies** (cost optimization)

---

## 💡 Policy Authoring Guidelines

### For Policy Authors

1. **Be Specific:** "deletion_protection = true" not "enable protection"
2. **Include Context:** Explain *why* this matters (business impact)
3. **Provide Examples:** Both compliant and non-compliant code
4. **Clear Remediation:** Step-by-step fix instructions
5. **Link References:** AWS docs, Terraform registry, compliance frameworks

### For RAG Optimization

1. **Use Keywords:** Include resource type names multiple times
2. **Semantic Richness:** Use synonyms (e.g., "encryption" and "encrypted")
3. **Structured Sections:** Consistent headings for better chunking
4. **Metadata Tags:** Severity, resource types, compliance frameworks

---

## 📊 Success Metrics by Policy

| Policy | Target Detection Rate | Acceptable False Positives |
|--------|----------------------|---------------------------|
| Deletion Protection | 100% | 0% |
| Encryption at Rest | 95%+ | < 5% |
| Public Access Block | 98%+ | < 2% |
| Multi-AZ | 90%+ | < 10% (context-dependent) |
| Backup Retention | 95%+ | < 5% |
| Required Tagging | 85%+ | < 15% (subjective) |
| Naming Conventions | 80%+ | < 20% (subjective) |

---

## 🎯 Quick Start Checklist

For Phase 2 MVP, create these policies in order:

- [x] **Policy #1:** Deletion Protection (already exists)
- [ ] **Policy #2:** Encryption at Rest (`policies/encryption_at_rest.md`)
- [ ] **Policy #3:** Public Access Block (`policies/public_access_block.md`)
- [ ] **Policy #4:** Multi-AZ Requirement (`policies/multi_az_requirement.md`)
- [ ] **Policy #5:** Backup Retention (`policies/backup_retention.md`)

**After creating each policy:**
1. Write the markdown file following the template
2. Run: `python scripts/index_policies.py --reindex`
3. Test retrieval: `python scripts/test_retrieval.py [policy_id]`
4. Validate with test fixtures

---

## 🤝 Stakeholder Alignment

### Present to Security Team
**Policies #1-3, #9** → "We're automating your top security checks"

### Present to Engineering Leadership
**Policies #4-6** → "We're preventing production outages before they happen"

### Present to Finance
**Policy #7** → "We're ensuring cost allocation accuracy"

### Present to Compliance
**Policies #2, #3, #10** → "We're automating regulatory compliance checks"

---

**Next Action:** Begin creating Policy #2 (Encryption at Rest) using the template above.
