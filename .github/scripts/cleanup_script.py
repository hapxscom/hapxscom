import os
import requests
from datetime import datetime, timedelta
import time
import logging
from requests.exceptions import RequestException
from github import Github

# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_automation.log"), logging.StreamHandler()])


# 从环境变量读取GitHub Token和GitHub用户名
base_url = 'https://api.github.com'
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
    发送API请求并返回响应，带重试逻辑，并自动设置头部
    """
    headers = {
        'Authorization': f'token {TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    kwargs['headers'] = headers

    retries = 0
    while retries < max_retries:
        try:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()

            # 检查速率限制
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 10:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    sleep_time = max(reset_time - time.time(), 3)  # 至少等待3秒
                    logging.info(f"达到速率限制，暂停 {sleep_time} 秒")
                    time.sleep(sleep_time)

            return response
        except RequestException as e:
            retries += 1
            logging.error(f"请求失败: {e}, URL: {url}. 重试 {retries}/{max_retries}")
            if e.response:
                logging.error(f"响应内容: {e.response.text}")
            time.sleep(2**retries)  # 指数退避
    return None

def delete_run(owner, repo, run_id):
    """删除指定的工作流运行记录"""
    delete_url = f"{base_url}/repos/{owner}/{repo}/actions/runs/{run_id}"
    delete_response = api_request('DELETE', delete_url)
    if delete_response and delete_response.status_code == 204:
        logging.info(f"从仓库 {repo} 删除运行记录 {run_id}")
    else:
        logging.error(f"无法从仓库 {repo} 删除运行记录 {run_id}")

def get_repos(username):
    """获取用户的所有仓库，支持分页"""
    repos = []
    page = 1
    while True:
        repos_url = f"{base_url}/users/{username}/repos?page={page}&per_page=100"
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
        runs_url = f"{base_url}/repos/{owner}/{repo}/actions/runs?page={page}&per_page=100"
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
    comment_url = f"{base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = api_request('POST', comment_url, json={'body': body})
    if response and response.status_code == 201:
        logging.info(f"在 {owner}/{repo} 的PR #{pr_number} 上发表评论")
    else:
        logging.error(f"无法在 {owner}/{repo} 的PR #{pr_number} 上发表评论")

def close_pr(owner, repo, pr_number):
    """关闭指定的PR"""
    close_url = f"{base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
    response = api_request('PATCH', close_url, json={'state': 'closed'})
    if response and response.status_code == 200:
        logging.info(f"关闭了 {owner}/{repo} 的PR #{pr_number}")
    else:
        logging.error(f"无法关闭 {owner}/{repo} 的PR #{pr_number}")

def process_dependabot_prs(owner, repo):
    """处理指定仓库中由dependabot创建的PR"""
    prs_url = f"{base_url}/repos/{owner}/{repo}/pulls"
    response = api_request('GET', prs_url)
    if response and response.status_code == 200:
        prs = response.json()
        for pr in prs:
            if pr['user']['login'] == 'dependabot[bot]':
                mergeable_state = pr.get('mergeable_state')
                if mergeable_state is not None and mergeable_state == 'behind':
                    # 指示 Dependabot 更新 PR
                    comment_on_pr(owner, repo, pr['number'], "@dependabot rebase")
                
                # 检查 PR 创建时间，判断是否需要关闭
                pr_created_at = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if datetime.now() - pr_created_at > timedelta(days=30):
                    # 如果PR超过30天没有更新，则关闭PR
                    close_pr(owner, repo, pr['number'])
    else:
        logging.error(f"无法从仓库 {repo} 获取PRs")


def is_inactive(updated_at):
    """判断PR是否不活跃（默认2天未活动）"""
    inactive_time = datetime.now() - timedelta(days=2)
    pr_last_updated = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%SZ')
    return pr_last_updated < inactive_time

def has_recent_activity(owner, repo, pr_number):
    """检查PR在过去2天内是否有评论或活动"""
    comments_url = f"{base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    events_url = f"{base_url}/repos/{owner}/{repo}/issues/{pr_number}/events"
    
    # 检查评论
    comments_response = api_request('GET', comments_url)
    if comments_response and comments_response.status_code == 200:
        comments = comments_response.json()
        for comment in comments:
            comment_date = datetime.strptime(comment['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            if comment_date > datetime.now() - timedelta(days=2):
                return True
    
    # 检查事件
    events_response = api_request('GET', events_url)
    if events_response and events_response.status_code == 200:
        events = events_response.json()
        for event in events:
            event_date = datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            if event_date > datetime.now() - timedelta(days=2):
                return True

    return False

def close_inactive_pull_requests_for_repo(owner, repo):
    """关闭仓库中所有2天未活动的PR"""
    pulls_url = f"{base_url}/repos/{owner}/{repo}/pulls?state=open"
    response = api_request('GET', pulls_url)
    if response and response.status_code == 200:
        pull_requests = response.json()
        for pr in pull_requests:
            if is_inactive(pr['updated_at']) and not has_recent_activity(owner, repo, pr['number']):
                close_pr(owner, repo, pr['number'])
                logging.info(f"由于长时间无活动，关闭了 {owner}/{repo} 的PR #{pr['number']}")
    else:
        logging.error(f"无法获取 {owner}/{repo} 的开放PR列表，状态码: {response.status_code}")

def delete_workflow(repo, workflow_id):
    """删除指定仓库中的特定工作流"""
    headers = {
        'Authorization': f'token {TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    delete_workflow_url = f"{base_url}/repos/{repo.owner.login}/{repo.name}/actions/workflows/{workflow_id}"
    try:
        response = session.delete(delete_workflow_url, headers=headers)
        if response.status_code == 204:
            logging.info(f"已成功删除仓库 '{repo.name}' 中ID为 '{workflow_id}' 的工作流。")
        else:
            logging.error(f"尝试删除仓库 '{repo.name}' 中ID为 '{workflow_id}' 的工作流失败。状态码：{response.status_code}")
    except Exception as e:
        logging.error(f"删除仓库 '{repo.name}' 中ID为 '{workflow_id}' 的工作流时出错：{e}")

def main():
    if not TOKEN or not USERNAME:
        logging.error("GitHub Token或用户名未设置。")
        return

    g = Github(TOKEN)
    user = g.get_user(USERNAME)
    repos = user.get_repos()

    for repo in repos:
        repo_name = repo.name
        owner = repo.owner.login

        # 删除特定工作流
        workflows = repo.get_workflows()
        for workflow in workflows:
            if workflow.name == "Upstream Sync":
                delete_workflow(repo, workflow.id)

        # 处理PRs和工作流运行记录
        delete_non_successful_runs_for_repo(owner, repo_name)
        process_dependabot_prs(owner, repo_name)
        close_inactive_pull_requests_for_repo(owner, repo_name)

if __name__ == "__main__":
    main()
