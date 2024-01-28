import os
import requests
from requests.structures import CaseInsensitiveDict

# GitHub API URL
base_url = 'https://api.github.com'

# 使用环境变量来获取GitHub Token和用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')

def list_repositories(user):
    """获取用户的所有仓库列表，并处理分页"""
    all_repos = []
    page = 1
    while True:
        repos_url = f"{base_url}/users/{user}/repos?page={page}&per_page=100"
        headers = CaseInsensitiveDict()
        headers["Authorization"] = f"token {TOKEN}"
        response = requests.get(repos_url, headers=headers)
        response.raise_for_status()
        
        repos = response.json()
        if not repos:
            break
        all_repos.extend(repos)
        page += 1
    return all_repos

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
    # 如果权限是'all'，则返回日志信息并不执行API调用
    if permission == "all":
        return f"Repo {repo['name']} workflow permissions set to 'all'. No further action taken."

    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    headers["Accept"] = "application/vnd.github.v3+json"
    data = {"permission": permission}
    response = requests.put(permissions_url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def main():
    # 获取所有仓库
    repos = list_repositories(USERNAME)
    print(f"Total repositories to check: {len(repos)}")

    # 遍历仓库
    for repo in repos:
        try:
            permissions = get_workflow_permissions(repo)
            # 检查是否需要将工作流权限更新为 'all'
            current_actions = permissions.get('allowed_actions', None)
            if permissions['enabled'] and current_actions != 'all':
                # 输出当前权限和更新状态
                print(f"Current permissions for repo {repo['name']}: {current_actions}")
                print(f"Updating permissions to 'all' for repo: {repo['name']}")
                update_response = set_workflow_permissions(repo, "all")
                print(update_response)  # 输出更新后的权限状态
            else:
                print(f"Permissions for repo {repo['name']} already allow all actions")
        except requests.exceptions.RequestException as e:
            print(f"Failed to process repo {repo['name']}: {e}")

if __name__ == "__main__":
    main()
