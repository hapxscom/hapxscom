import os
import requests
from requests.structures import CaseInsensitiveDict

# 使用环境变量来获取GitHub Token和用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')

# GitHub API URL
base_url = 'https://api.github.com'

def list_repositories(user):
    """获取用户的所有仓库列表"""
    repos_url = f"{base_url}/users/{user}/repos"
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    response = requests.get(repos_url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_workflow_permissions(repo):
    """获取仓库的当前工作流权限"""
    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    response = requests.get(permissions_url, headers=headers)
    response.raise_for_status()
    return response.json()

def set_workflow_permissions(repo, permission):
    """设置仓库的工作流权限"""
    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    headers["Accept"] = "application/vnd.github.v3+json"
    data = {
        "permission": permission
    }
    response = requests.put(permissions_url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def main():
    # 获取所有仓库
    repos = list_repositories(USERNAME)

    # 遍历仓库
    for repo in repos:
        permissions = get_workflow_permissions(repo)
        # 检查工作流权限是否为可读写（write）
        if permissions['enabled'] and permissions['allowed_actions'] != 'write':
            # 输出当前权限和更新状态
            print(f"Current permissions for repo {repo['name']}: {permissions['allowed_actions']}")
            print(f"Updating permissions for repo: {repo['name']}")
            set_workflow_permissions(repo, "write")
        else:
            print(f"Permissions for repo {repo['name']} are already set to read/write")

if __name__ == "__main__":
    main()