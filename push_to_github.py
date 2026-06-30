import os
import re
import subprocess
from github import Github

def get_token():
    env_path = os.path.join("codereview_sensei", ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'GITHUB_TOKEN\s*=\s*["\']?([^"\n\'\s]+)["\']?', content)
    return match.group(1) if match else None

def main():
    token = get_token()
    if not token:
        print("Error: GITHUB_TOKEN not found in .env")
        return
        
    g = Github(token)
    user = g.get_user()
    username = user.login
    print(f"Authenticated as: {username}")
    
    repo_name = "Sensei"
    remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
    try:
        remotes = subprocess.check_output(["git", "remote"], text=True).strip().split()
        if "origin" in remotes:
            subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
        else:
            subprocess.run(["git", "remote", "add", "origin", remote_url], check=True)
    except Exception as e:
        print(f"Git remote failed: {e}")
        return

    try:
        subprocess.run(["git", "branch", "-M", "main"], check=True)
    except Exception as e:
        print(f"Failed to rename branch: {e}")
        
    print("Pushing repository to GitHub...")
    try:
        subprocess.run(["git", "push", "-u", "origin", "main", "--force"], check=True)
        print(f"\n🚀 Successfully pushed to: https://github.com/{username}/{repo_name}")
    except Exception as e:
        print(f"Git push failed: {e}")
        print("\nTip: If you get a 'Repository not found' or '403 Forbidden' error, please verify that you have manually created a repository named 'Sensei' on GitHub under your account first.")

if __name__ == "__main__":
    main()
