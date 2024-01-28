import os
import requests
from datetime import datetime, timedelta
import time
import logging
from requests.exceptions import RequestException

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 从环境变量读取GitHub Token和GitHub用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')
DEPENDABOT_WAIT_TIME = int(os.getenv('DEPENDABOT_WAIT_TIME', '30'))  # 默认等待时间为30秒

# 创建会话实例
session = requests.Session()
session.headers.update({
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
})

def api_request(method, url, max_retries=3, **kwargs):
    """
    发送API请求并返回响应，带重试逻辑
    """
    retries = 0
    while retries < max_retries:
        try:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except RequestException as e:
            retries += 1
            logging.error(f"Request failed: {e}, URL: {url}. Retry {retries}/{max_retries}")
            time.sleep(2**retries)  # 指数退避
    return None

def delete_run(owner, repo, run_id):
    """删除指定的工作流运行记录"""
    delete_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    delete_response = api_request('DELETE', delete_url)
    if delete_response and delete_response.status_code == 204:
        logging.info(f"Deleted run {run_id} from repo {repo}")
    else:
        logging.error(f"Failed to delete run {run_id} from repo {repo}")

def get_repos(username):
    """获取用户的所有仓库，支持分页"""
    repos = []
    page = 1
    while True:
        repos_url = f"https://api.github.com/users/{username}/repos?page={page}&per_page=100"
        repos_response = api_request('GET', repos_url)
        if repos_response and repos_response.status_code == 200:
            page_repos = repos_response.json()
            if not page_repos:
                break  # 如果没有更多的仓库，退出循环
            repos.extend(page_repos)
            page += 1
        else:
            break
    return repos

def delete_non_successful_runs_for_repo(owner, repo):
    """删除仓库中所有未成功的工作流运行记录，支持分页"""
    page = 1
    while True:
        runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?page={page}&per_page=100"
        runs_response = api_request('GET', runs_url)
        if runs_response and runs_response.status_code == 200:
            runs_data = runs_response.json()
            runs = runs_data.get('workflow_runs', [])
            if not runs:
                break  # 没有更多的运行记录，退出循环

            for run in runs:
                if run['conclusion'] != 'success':
                    delete_run(owner, repo, run['id'])

            page += 1  # 增加页码，获取下一页的数据
        else:
            break

def comment_on_pr(owner, repo, pr_number, body):
    """在指定的PR上发布评论"""
    comment_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = api_request('POST', comment_url, json={'body': body})
    if response and response.status_code == 201:
        logging.info(f"Commented on PR #{pr_number} in {owner}/{repo}")
    else:
        logging.error(f"Failed to comment on PR #{pr_number} in {owner}/{repo}")

def is_inactive(updated_at):
    """判断PR是否不活跃（默认1天未活动）"""
    inactive_time = datetime.now() - timedelta(days=1)
    pr_last_updated = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%SZ')
    return pr_last_updated < inactive_time

def close_pull_request(owner, repo, pr_number):
    """关闭指定的PR"""
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = api_request('PATCH', pr_url, json={'state': 'closed'})
    if response and response.status_code == 200:
        logging.info(f"Closed PR #{pr_number} in {owner}/{repo}")
    else:
        logging.error(f"Failed to close PR #{pr_number} in {owner}/{repo}")

def process_dependabot_prs(owner, repo):
    """评论所有dependabot的open PR并在30秒后关闭没有更新的PR"""
    prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    response = api_request('GET', prs_url)

    if response and response.status_code == 200:
        prs = response.json()
        for pr in prs:
            if pr['user']['login'] == 'dependabot[bot]':
                comment_on_pr(owner, repo, pr['number'], "@dependabot rebase")
                time.sleep(DEPENDABOT_WAIT_TIME)  # 给dependabot一些时间来回应评论
                
                pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}"
                pr_response = api_request('GET', pr_url)
                if pr_response and pr_response.status_code == 200:
                    updated_pr = pr_response.json()
                    if updated_pr['updated_at'] <= pr['updated_at']:
                        close_pull_request(owner, repo, pr['number'])
                else:
                    logging.error(f"Failed to get PR #{pr['number']} info from repo {repo}")
    else:
        logging.error(f"Failed to get PRs from repo {repo}")

def close_inactive_pull_requests_for_repo(owner, repo):
    """关闭仓库中所有1天未活动的PR"""
    pulls_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open"
    response = api_request('GET', pulls_url)
    if response and response.status_code == 200:
        pull_requests = response.json()
        for pr in pull_requests:
            if is_inactive(pr['updated_at']):
                close_pull_request(owner, repo, pr['number'])
    else:
        logging.error(f"Failed to fetch pull requests for repo {repo}, status code: {response.status_code}")

def main():
    if not TOKEN or not USERNAME:
        logging.error("GitHub Token或用户名未设置。")
        return

    repos = get_repos(USERNAME)
    for repo in repos:
        repo_name = repo['name']
        delete_non_successful_runs_for_repo(USERNAME, repo_name)
        process_dependabot_prs(USERNAME, repo_name)
        close_inactive_pull_requests_for_repo(USERNAME, repo_name)

if __name__ == "__main__":
    main()
