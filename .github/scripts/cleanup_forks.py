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
    从仓库信息中提取上游仓库信息，包括上游仓库的地址。
    """
    if 'parent' in repo:
        parent_info = repo['parent']
        if 'owner' in parent_info and 'html_url' in parent_info['owner']:
            upstream_repo_url = parent_info['owner']['html_url']
            logging.info(f"找到上游仓库地址: {upstream_repo_url}")
            return parent_info, upstream_repo_url
        else:
            logging.warning(f"仓库 {repo['name']} 的上游仓库信息中缺少 'owner' 或 'html_url'。")
            return parent_info, None
    else:
        logging.warning(f"仓库 {repo['name']} 没有上游仓库信息。")
        return None, None


def create_pull_request(repo, token):
    upstream_repo_info, upstream_repo_url = get_upstream_repo_info(repo)
    if not upstream_repo_info:
        logging.warning(f"仓库 {repo['name']} 无法获取上游仓库信息。")
        return

    repo_name = repo['name']
    fork_full_name = repo['full_name']

    # 此处确保 upstream_repo_info 是一个字典
    if isinstance(upstream_repo_info, dict):
        upstream_owner = upstream_repo_info['owner']['login']
        upstream_branch = upstream_repo_info['default_branch']
    else:
        logging.error(f"仓库 {repo_name} 的上游仓库信息不正确。")
        return

    headers = create_headers(token)

    pull_data = {
        "title": f"从上游仓库 {upstream_repo_info['full_name']} 同步更新",
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
