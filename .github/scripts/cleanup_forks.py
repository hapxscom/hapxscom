# 导入必要的库，用于与GitHub API交互和日志记录
import os
import requests
import logging
from requests.exceptions import HTTPError, RetryError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志记录的基本设置
# 设置日志记录的基本配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_github_token():
    """
    获取GitHub令牌环境变量。

    返回:
        GitHub令牌（字符串）。
    """
    return os.getenv('GH_TOKEN')

def get_github_username():
    """
    获取GitHub用户名环境变量。

    返回:
        GitHub用户名（字符串）。
    """
    return os.getenv('USERNAME')

def create_headers(token):
    """
    创建GitHub API请求的头部。

    参数:
        token (str): GitHub令牌。

    返回:
        包含授权信息的字典。
    """
    # 为GitHub API请求创建头部信息
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

def get_repositories(username, token):
    """
    获取用户的GitHub仓库列表。

    参数:
        username (str): GitHub用户名。
        token (str): GitHub令牌。

    返回:
        一个生成器，生成每个仓库的详细信息（字典）。
    """
    page = 1
    headers = create_headers(token)
    
    # 设置重试策略
    retry_strategy = Retry(
        total=5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],  # 将method_whitelist更改为allowed_methods
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)

    while True:
        url = f"https://api.github.com/users/{username}/repos?type=all&per_page=100&page={page}"
        try:
            with session.get(url, headers=headers) as response:
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
    获取上游仓库的信息。

    参数:
        repo (dict): 仓库的详细信息。

    返回:
        上游仓库的详细信息（字典）和上游仓库的URL（字符串）。
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
    """
    为仓库创建一个拉取请求，以同步更新上游仓库的更改。

    参数:
        repo (dict): 需要创建拉取请求的仓库的详细信息。
        token (str): GitHub令牌。
    """
    upstream_repo_info, upstream_repo_url = get_upstream_repo_info(repo)
    if not upstream_repo_info:
        logging.warning(f"仓库 {repo['name']} 无法获取上游仓库信息。")
        return

    repo_name = repo['name']
    fork_full_name = repo['full_name']

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
    """
    主函数，执行程序的主要逻辑。
    """
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