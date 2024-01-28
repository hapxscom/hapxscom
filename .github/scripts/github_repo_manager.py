import logging
from datetime import datetime, timedelta
from github_api_client import GitHubAPIClient

class GitHubRepoManager:
    def __init__(self):
        self.client = GitHubAPIClient()

    def delete_run(self, owner, repo, run_id):
        """删除指定的工作流运行记录"""
        endpoint = f"repos/{owner}/{repo}/actions/runs/{run_id}"
        response = self.client.api_request('DELETE', endpoint)
        if response and response.status_code == 204:
            logging.info(f"从仓库 {repo} 删除运行记录 {run_id}")
        else:
            logging.error(f"无法从仓库 {repo} 删除运行记录 {run_id}")

    def get_repos(self, username):
        """获取用户的所有仓库，支持分页"""
        repos = []
        page = 1
        while True:
            endpoint = f"users/{username}/repos?page={page}&per_page=100"
            response = self.client.api_request('GET', endpoint)
            if response and response.status_code == 200:
                page_repos = response.json()
                if not page_repos:
                    break
                repos.extend(page_repos)
                page += 1
            else:
                break
        return repos

    def delete_non_successful_runs_for_repo(self, owner, repo):
        """删除仓库中所有未成功的工作流运行记录"""
        page = 1
        while True:
            endpoint = f"repos/{owner}/{repo}/actions/runs?page={page}&per_page=100"
            response = self.client.api_request('GET', endpoint)
            if response and response.status_code == 200:
                runs_data = response.json()
                runs = runs_data.get('workflow_runs', [])
                if not runs:
                    break

                for run in runs:
                    if run['conclusion'] != 'success':
                        self.delete_run(owner, repo, run['id'])

                page += 1
            else:
                break

    def comment_on_pr(self, owner, repo, pr_number, body):
        """在指定的PR上发布评论"""
        endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self.client.api_request('POST', endpoint, json={'body': body})
        if response and response.status_code == 201:
            logging.info(f"在 {owner}/{repo} 的PR #{pr_number} 上发表评论")
        else:
            logging.error(f"无法在 {owner}/{repo} 的PR #{pr_number} 上发表评论")

    def close_pr(self, owner, repo, pr_number):
        """关闭指定的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.client.api_request('PATCH', endpoint, json={'state': 'closed'})
        if response and response.status_code == 200:
            logging.info(f"关闭了 {owner}/{repo} 的PR #{pr_number}")
        else:
            logging.error(f"无法关闭 {owner}/{repo} 的PR #{pr_number}")

    def process_dependabot_prs(self, owner, repo):
        """处理指定仓库中由dependabot创建的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls"
        response = self.client.api_request('GET', endpoint)
        if response and response.status_code == 200:
            prs = response.json()
            for pr in prs:
                if pr['user']['login'] == 'dependabot[bot]':
                    mergeable_state = pr.get('mergeable_state')
                    if mergeable_state is not None and mergeable_state == 'behind':
                        self.comment_on_pr(owner, repo, pr['number'], "@dependabot rebase")

                    pr_created_at = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if datetime.now() - pr_created_at > timedelta(days=30):
                        self.close_pr(owner, repo, pr['number'])
        else:
            logging.error(f"无法从仓库 {repo} 获取PRs")

    def is_inactive(self, updated_at):
        """判断PR是否不活跃（默认2天未活动）"""
        inactive_time = datetime.now() - timedelta(days=2)
        pr_last_updated = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%SZ')
        return pr_last_updated < inactive_time

    def has_recent_activity(self, owner, repo, pr_number):
        """检查PR在过去2天内是否有评论或活动"""
        comments_endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        events_endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/events"
        
        comments_response = self.client.api_request('GET', comments_endpoint)
        if comments_response and comments_response.status_code == 200:
            comments = comments_response.json()
            for comment in comments:
                if datetime.strptime(comment['created_at'], '%Y-%m-%dT%H:%M:%SZ') > datetime.now() - timedelta(days=2):
                    return True

        events_response = self.client.api_request('GET', events_endpoint)
        if events_response and events_response.status_code == 200:
            events = events_response.json()
            for event in events:
                if datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ') > datetime.now() - timedelta(days=2):
                    return True

        return False

    def close_inactive_pull_requests_for_repo(self, owner, repo):
        """关闭仓库中所有2天未活动的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls?state=open"
        response = self.client.api_request('GET', endpoint)
        if response and response.status_code == 200:
            pull_requests = response.json()
            for pr in pull_requests:
                if self.is_inactive(pr['updated_at']) and not self.has_recent_activity(owner, repo, pr['number']):
                    self.close_pr(owner, repo, pr['number'])
                    logging.info(f"由于长时间无活动，关闭了 {owner}/{repo} 的PR #{pr['number']}")
        else:
            logging.error(f"无法获取 {owner}/{repo} 的开放PR列表，状态码: {response.status_code}")
    
    def get_workflow_runs(self, owner, repo, per_page=100):
        """获取仓库中的所有工作流运行的详细信息，遍历所有页面"""
        runs_data = []
        page = 1
        while True:
            endpoint = f"repos/{owner}/{repo}/actions/runs?page={page}&per_page={per_page}"
            response = self.client.api_request('GET', endpoint)
            if response and response.status_code == 200:
                runs = response.json().get('workflow_runs', [])
                runs_data.extend(runs)

                if len(runs) < per_page:
                    break
                page += 1
            else:
                logging.error(f"获取仓库 '{repo}' 的工作流运行失败。状态码：{response.status_code}")
                break
        return runs_data

    def delete_workflow(self, owner, repo, workflow_id):
        """删除指定仓库中的特定工作流"""
        endpoint = f"repos/{owner}/{repo}/actions/runs/{workflow_id}"
        response = self.client.api_request('DELETE', endpoint)
        if response and response.status_code == 204:
            logging.info(f"已成功删除仓库 '{repo}' 中ID为 '{workflow_id}' 的工作流。")
        else:
            logging.error(f"尝试删除仓库 '{repo}' 中ID为 '{workflow_id}' 的工作流失败。状态码：{response.status_code}")

    def maintain_repo_workflows(self, owner, repo):
        """维护特定仓库的工作流，保留最新的工作流运行并删除其他的"""
        all_runs = self.get_workflow_runs(owner, repo)
        latest_runs = {}
        for run in all_runs:
            workflow_name = run['name']
            if workflow_name not in latest_runs or latest_runs[workflow_name]['created_at'] < run['created_at']:
                latest_runs[workflow_name] = run

        for run in all_runs:
            if run['id'] != latest_runs[run['name']]['id']:
                self.delete_workflow(owner, repo, run['id'])