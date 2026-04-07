#!/usr/bin/env bash
#
# Configure branch protection rules on main for NetApp/orchestrio.
#
# Prerequisites:
#   - gh CLI authenticated with admin access to the repo
#   - Chunks 1-3 merged and PR Checks workflow has run at least once
#     (GitHub must recognise the status check names before they can be required)
#
# Usage:
#   bash .github/scripts/setup-branch-protection.sh
#
# This script is idempotent — safe to re-run.

set -euo pipefail

OWNER="NetApp"
REPO="orchestrio"
BRANCH="main"

echo "Configuring branch protection on ${OWNER}/${REPO}@${BRANCH} ..."

gh api \
  --method PUT \
  "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "validate-and-lint",
      "test",
      "secret-scan"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo ""
echo "Branch protection applied. Summary:"
echo ""
echo "  Require PR before merging ............. yes"
echo "  Required approving reviewers .......... 1"
echo "  Require CODEOWNERS review ............. yes"
echo "  Dismiss stale reviews on push ......... yes"
echo "  Required status checks (strict) ....... validate-and-lint, test, secret-scan"
echo "  Require conversation resolution ....... yes"
echo "  Enforce for admins .................... no  (allows emergency merge)"
echo "  Allow force pushes .................... no"
echo "  Allow branch deletion ................. no"
echo ""
echo "Done. Verify at: https://github.com/${OWNER}/${REPO}/settings/branches"
