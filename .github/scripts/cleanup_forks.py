import os
import requests
from requests.exceptions import HTTPError

def get_github_token():
    # 从环境变量中获取GitHub Token
    return os.getenv('GH_TOKEN')

def get_github_username():
    # 从环境变量中获取GitHub用户名
    return os.getenv('USERNAME')

def get_repositories(username, token):
    # 获取用户的所有仓库
    page = 1
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    while True:
        url = f"https://api.github.com/users/{username}/repos?type=all&per_page=100&page={page}"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            repos = response.json()
            if not repos:
                break
            for repo in repos:
                yield repo
            page += 1
        except HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            break
        except Exception as err:
            print(f"Other error occurred: {err}")
            break

def create_pull_request(repo, token):
    # 为Fork的仓库创建拉取请求
    repo_name = repo['name']
    fork_full_name = repo['full_name']
    upstream_branch = "master"  # 或者根据需要选择分支

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    pull_data = {
        "title": f"更新从 {repo['parent']['full_name']}",
        "head": f"{repo['parent']['owner']['login']}:{upstream_branch}",
        "base": "master"
    }

    try:
        response = requests.post(f"https://api.github.com/repos/{fork_full_name}/pulls", json=pull_data, headers=headers)
        response.raise_for_status()
        print(f"成功创建拉取请求: {response.json()['html_url']}")
    except HTTPError as http_err:
        print(f"HTTP error occurred while creating pull request for {repo_name}: {http_err}")
    except Exception as err:
        print(f"Other error occurred: {err}")

def main():
    token = get_github_token()
    username = get_github_username()
    if not token or not username:
        print("GitHub Token或用户名未设置。")
        return

    for repo in get_repositories(username, token):
        print(f"仓库名称: {repo['name']}, 是否 Fork: {repo['fork']}")
        if repo['fork'] and 'parent' in repo:
            create_pull_request(repo, token)

if __name__ == "__main__":
    main()
