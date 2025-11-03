import os
import subprocess

def run_cmd(cmd):
    """Run a shell command and stream its output."""
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {cmd}")
        exit(1)

def main():
    print("🧠 Git + Commitizen helper")
    branch = input("Enter branch name (e.g., feat/login-page): ").strip()

    run_cmd(f"git checkout -b {branch} || git checkout {branch}")

    run_cmd("git add .")

    print("\n🚀 Launching Commitizen (npm run commit)...")
    run_cmd("npm run commit")

if __name__ == "__main__":
    main()