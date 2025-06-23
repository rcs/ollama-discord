#!/usr/bin/env python3
"""
Script to set up branch protection rules for the repository.
This requires appropriate GitHub permissions.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests


def setup_branch_protection():
    """Set up branch protection rules for the master branch."""
    
    # Get GitHub token from environment
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("Please set it with: export GITHUB_TOKEN=your_token")
        return False
    
    # Repository details
    owner = "rcs"
    repo = "ollama-discord"
    branch = "master"
    
    # GitHub API endpoint
    url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"
    
    # Branch protection configuration
    protection_config = {
        "required_status_checks": {
            "strict": True,
            "contexts": [
                "test (3.9)",
                "test (3.10)", 
                "test (3.11)",
                "security"
            ]
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "required_approving_review_count": 1,
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "require_last_push_approval": False
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": True
    }
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        print(f"🔧 Setting up branch protection for {owner}/{repo}:{branch}")
        response = requests.put(url, json=protection_config, headers=headers)
        
        if response.status_code == 200:
            print("✅ Branch protection rules set successfully!")
            print("\nConfigured rules:")
            print("- Require pull request reviews before merging")
            print("- Require 1 approving review")
            print("- Dismiss stale PR approvals when new commits are pushed")
            print("- Require status checks to pass before merging")
            print("- Require branches to be up to date before merging")
            print("- Include administrators")
            print("- Require conversation resolution")
            return True
        else:
            print(f"❌ Failed to set branch protection: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up branch protection: {e}")
        return False


def main():
    """Main function."""
    print("🚀 Setting up GitHub PR approval workflow...")
    print()
    
    success = setup_branch_protection()
    
    if success:
        print()
        print("🎉 Setup complete! Your repository now has:")
        print("- Automated CI/CD pipeline")
        print("- Required PR approvals")
        print("- Code quality checks")
        print("- Security scanning")
        print()
        print("📖 See docs/PR_WORKFLOW.md for development guidelines")
    else:
        print()
        print("💡 Manual setup required:")
        print("1. Go to https://github.com/rcs/ollama-discord/settings/branches")
        print("2. Add rule for 'master' branch")
        print("3. Enable 'Require pull request reviews before merging'")
        print("4. Set required approving reviews to 1")
        print("5. Enable 'Require status checks to pass before merging'")
        print("6. Enable 'Include administrators'")


if __name__ == "__main__":
    main() 