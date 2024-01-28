import os
import requests
import logging
from requests.structures import CaseInsensitiveDict

# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_automation.log"), logging.StreamHandler()])

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
            logging.error(f"无法列出仓库: {e}")
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
        logging.error(f"无法获取仓库 {repo['name']} 的工作流权限: {e}")

def set_workflow_permissions(repo, permission):
    """设置仓库的工作流权限"""
    if permission == "all":
        logging.info(f"仓库 {repo['name']} 的工作流权限已设置为 'all'.")
        return

    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = create_headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    data = {"permission": permission}
    try:
        response = requests.put(permissions_url, headers=headers, json=data)
        response.raise_for_status()
        logging.info(f"已更新仓库 {repo['name']} 的工作流权限")
    except requests.exceptions.RequestException as e:
        logging.error(f"无法设置仓库 {repo['name']} 的工作流权限: {e}")

def main():
    repos = list_repositories(USERNAME)
    logging.info(f"需要检查的仓库总数: {len(repos)}")

    for repo in repos:
        permissions = get_workflow_permissions(repo)
        if permissions and permissions.get('enabled', False) and permissions.get('allowed_actions', '') != 'all':
            logging.info(f"正在将仓库: {repo['name']} 的权限更新为 'all'")
            set_workflow_permissions(repo, "all")

if __name__ == "__main__":
    main()
