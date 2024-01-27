import os
import requests
from datetime import datetime, timedelta
import time

# 从环境变量读取GitHub Token和GitHub用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')

# 设置请求头
headers = {
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

def delete_run(owner, repo, run_id):
    """删除指定的工作流运行记录"""
    delete_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    delete_response = requests.delete(delete_url, headers=headers)
    if delete_response.status_code == 204:
        print(f"Deleted run {run_id} from repo {repo}")
    else:
        print(f"Failed to delete run {run_id} from repo {repo}, status code: {delete_response.status_code}")

def get_repos(username):
    """获取用户的所有仓库"""
    repos_url = f"https://api.github.com/users/{username}/repos"
    repos_response = requests.get(repos_url, headers=headers)
    if repos_response.status_code == 200:
        return repos_response.json()
    else:
        print(f"Failed to fetch repositories for user {username}, status code: {repos_response.status_code}")
        return []

def delete_non_successful_runs_for_repo(owner, repo):
    """删除仓库中所有未成功的工作流运行记录"""
    runs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    page = 1
    while True:
        runs_response = requests.get(runs_url, headers=headers, params={'page': page, 'per_page': 100})
        if runs_response.status_code != 200:
            print(f"Failed to fetch workflow runs for repo {repo}, status code: {runs_response.status_code}")
            break

        runs = runs_response.json().get('workflow_runs', [])
        if not runs:
            break  # 如果没有更多的运行记录，退出循环

        for run in runs:
            if run['conclusion'] != 'success':
                delete_run(owner, repo, run['id'])

        page += 1  # 增加页码，获取下一页的数据

def comment_on_pr(owner, repo, pr_number, body):
    """在指定的PR上发布评论"""
    comment_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = requests.post(comment_url, headers=headers, json={'body': body})
    if response.status_code == 201:
        print(f"Commented on PR #{pr_number} in {owner}/{repo}")
    else:
        print(f"Failed to comment on PR #{pr_number} in {owner}/{repo}. Status code: {response.status_code}")

def process_dependabot_prs(owner, repo):
    """评论所有dependabot的open PR并在30秒后关闭没有更新的PR"""
    prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    response = requests.get(prs_url, headers=headers)

    if response.status_code == 200:
        prs = response.json()
        for pr in prs:
            if pr['user']['login'] == 'dependabot[bot]':
                comment_on_pr(owner, repo, pr['number'], "@dependabot rebase")
                time.sleep(30)  # 给dependabot一些时间来回应评论
                
                # 重新获取PR信息来检查是否已经有更新
                pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr['number']}"
                pr_response = requests.get(pr_url, headers=headers)
                if pr_response.status_code == 200:
                    updated_pr = pr_response.json()
                    # 如果PR在评论后30秒内没有更新，则关闭它
                    if updated_pr['updated_at'] <= pr['updated_at']:
                        close_pull_request(owner, repo, pr['number'])
                else:
                    print(f"Failed to get PR #{pr['number']} info from repo {repo}, status code: {pr_response.status_code}")
    else:
        print(f"Failed to get PRs from repo {repo}, status code: {response.status_code}")
        
def is_inactive(pr_last_updated_at):
    """判断PR是否未活动超过1天"""
    last_updated_at = datetime.strptime(pr_last_updated_at, "%Y-%m-%dT%H:%M:%SZ")
    return datetime.utcnow() - last_updated_at > timedelta(days=1)

def close_pull_request(owner, repo, pr_number):
    """关闭指定的PR"""
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    data = {'state': 'closed'}
    response = requests.patch(pr_url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Closed PR #{pr_number} from repo {repo}")
    else:
        print(f"Failed to close PR #{pr_number} from repo {repo}, status code: {response.status_code}")

def close_inactive_pull_requests_for_repo(owner, repo):
    """关闭仓库中所有1天未活动的PR"""
    pulls_url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open"
    response = requests.get(pulls_url, headers=headers)
    if response.status_code == 200:
        pull_requests = response.json()
        for pr in pull_requests:
            if is_inactive(pr['updated_at']):
                close_pull_request(owner, repo, pr['number'])
    else:
        print(f"Failed to fetch pull requests for repo {repo}, status code: {response.status_code}")

# 主逻辑
repos = get_repos(USERNAME)
for repo in repos:
    repo_name = repo['name']
    delete_non_successful_runs_for_repo(USERNAME, repo_name)
    process_dependabot_prs(USERNAME, repo_name)
    close_inactive_pull_requests_for_repo(USERNAME, repo_name)
    