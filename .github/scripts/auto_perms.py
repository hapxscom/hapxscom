import os
import requests
import logging
from requests.structures import CaseInsensitiveDict

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# GitHub API URL
base_url = 'https://api.github.com'

# 使用环境变量来获取GitHub Token和用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')

def create_headers():
    """创建请求头"""
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    return headers

def list_repositories(user):
    """获取用户的所有仓库列表，并处理分页"""
    all_repos = []
    page = 1
    headers = create_headers()
    while True:
        repos_url = f"{base_url}/users/{user}/repos?page={page}&per_page=100"
        try:
            response = requests.get(repos_url, headers=headers)
            response.raise_for_status()
            repos = response.json()
            if not repos:
                break
            all_repos.extend(repos)
            page += 1
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to list repositories: {e}")
            break
    return all_repos

def get_workflow_permissions(repo):
    """获取仓库的当前工作流权限"""
    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = create_headers()
    try:
        response = requests.get(permissions_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get workflow permissions for repo {repo['name']}: {e}")

def set_workflow_permissions(repo, permission):
    """设置仓库的工作流权限"""
    if permission == "all":
        logging.info(f"Repo {repo['name']} workflow permissions already set to 'all'.")
        return

    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = create_headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    data = {"permission": permission}
    try:
        response = requests.put(permissions_url, headers=headers, json=data)
        response.raise_for_status()
        logging.info(f"Updated workflow permissions for repo {repo['name']}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to set workflow permissions for repo {repo['name']}: {e}")

def main():
    repos = list_repositories(USERNAME)
    logging.info(f"Total repositories to check: {len(repos)}")

    for repo in repos:
        permissions = get_workflow_permissions(repo)
        if permissions and permissions.get('enabled', False) and permissions.get('allowed_actions', '') != 'all':
            logging.info(f"Updating permissions to 'all' for repo: {repo['name']}")
            set_workflow_permissions(repo, "all")

if __name__ == "__main__":
    main()
