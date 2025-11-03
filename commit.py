import os
import subprocess
import sys
from urllib.parse import quote

def run(cmd, check=True, capture=False):
    """Run a shell command; stream output by default."""
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, check=check,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=check)
            return ""
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Command failed: {cmd}")
        if e.stdout:
            print(e.stdout)
        sys.exit(1)

def get_current_branch():
    out = run("git rev-parse --abbrev-ref HEAD", capture=True)
    return out

def branch_exists(branch):
    code = subprocess.run(f"git rev-parse --verify {branch}",
                          shell=True).returncode
    return code == 0

def normalize_remote_to_https(remote_url):
    # Convert git@github.com:org/repo.git → https://github.com/org/repo
    # Leave https URLs mostly as-is, strip trailing .git
    remote_url = remote_url.strip()
    if remote_url.startswith("git@github.com:"):
        path = remote_url.split("git@github.com:")[-1]
        if path.endswith(".git"):
            path = path[:-4]
        return f"https://github.com/{path}"
    if remote_url.startswith("https://github.com/"):
        url = remote_url
        if url.endswith(".git"):
            url = url[:-4]
        return url
    # Fallback: return as-is (may not build PR link)
    return remote_url

def main():
    print("🧠 Git + Commitizen helper (create/switch branch → commit → push → PR link)\n")

    # Ensure we’re in a git repo
    subprocess.run("git rev-parse --is-inside-work-tree", shell=True, check=True)

    # Ask for branch
    default_branch = get_current_branch()
    branch = input(f"Enter branch name (e.g., feat/login-page) [{default_branch}]: ").strip()
    if not branch:
        branch = default_branch

    # Create or switch
    if branch_exists(branch):
        print(f"🔀 Switching to existing branch: {branch}")
        run(f"git checkout {branch}")
    else:
        print(f"🌱 Creating new branch: {branch}")
        run(f"git checkout -b {branch}")

    # Stage all changes
    print("➕ Staging all changes (git add .)")
    run("git add .")

    # Quick check: any changes to commit?
    status = run("git status --porcelain", capture=True)
    if not status:
        print("ℹ️ No changes to commit. If you expected changes, save files or check .gitignore.")
        # Still offer to push (useful if commit already happened)
        choice = input("Push current branch to origin anyway? [y/N]: ").strip().lower()
        if choice == "y":
            run(f"git push -u origin {branch}")
        sys.exit(0)

    # Launch Commitizen
    print("\n🚀 Launching Commitizen (npm run commit)...")
    run("npm run commit")

    # After commit, push automatically
    print(f"\n☁️ Pushing to origin {branch} (with upstream)...")
    run(f"git push -u origin {branch}")

    # Build a PR URL
    remote = run("git config --get remote.origin.url", capture=True)
    https_repo = normalize_remote_to_https(remote)
    if "github.com" in https_repo and "/" in https_repo:
        pr_url = f"{https_repo}/compare/main...{quote(branch)}?expand=1"
        print(f"\n✅ Done! Open PR: {pr_url}")
    else:
        print("\n✅ Done! Open a Pull Request in your repo (couldn’t auto-detect PR URL).")

if __name__ == "__main__":
    try:
        #test
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")