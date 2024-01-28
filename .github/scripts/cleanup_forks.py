import os
import requests
import logging
from requests.exceptions import HTTPError

# 设置日志记录，包括时间、日志级别和消息
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_github_token():
    # 从环境变量获取GitHub令牌
    return os.getenv('GH_TOKEN')

def get_github_username():
    # 从环境变量获取GitHub用户名
    return os.getenv('USERNAME')

def create_headers(token):
    # 为GitHub API请求创建头部信息
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def get_repositories(username, token):
    page = 1
    headers = create_headers(token)
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
            logging.error(f"发生HTTP错误: {http_err}")
            break
        except Exception as err:
            logging.error(f"发生其他错误: {err}")
            break
            
def get_upstream_repo_info(repo):
    """
    从仓库信息中提取上游仓库信息
    """
    if 'parent' in repo:
        return repo['parent']
    else:
        logging.warning(f"仓库 {repo['name']} 没有上游仓库信息。")
        return None

def create_pull_request(repo, token):
    upstream_repo = get_upstream_repo_info(repo)
    if not upstream_repo:
        return

    repo_name = repo['name']
    fork_full_name = repo['full_name']
    upstream_owner = upstream_repo['owner']['login']
    upstream_branch = upstream_repo['default_branch']

    headers = create_headers(token)

    pull_data = {
        "title": f"从上游仓库 {upstream_repo['full_name']} 同步更新",
        "head": f"{upstream_owner}:{upstream_branch}",
        "base": repo['default_branch']  # 使用 fork 仓库的默认分支
    }

    try:
        response = requests.post(f"https://api.github.com/repos/{fork_full_name}/pulls", json=pull_data, headers=headers)
        response.raise_for_status()
        logging.info(f"成功创建拉取请求: {response.json()['html_url']}")
    except HTTPError as http_err:
        logging.error(f"为仓库 {repo_name} 创建拉取请求时发生HTTP错误: {http_err}")
    except Exception as err:
        logging.error(f"发生其他错误: {err}")

def main():
    token = get_github_token()
    username = get_github_username()
    if not token or not username:
        logging.error("GitHub令牌或用户名未设置。")
        return

    for repo in get_repositories(username, token):
        logging.info(f"仓库名称: {repo['name']}, 是否为Fork: {repo['fork']}")
        if repo['fork']:
            create_pull_request(repo, token)

if __name__ == "__main__":
    main()
