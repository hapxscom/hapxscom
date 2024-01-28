import os
import logging
from github_repo_manager import GitHubRepoManager

# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("main.log"), logging.StreamHandler()])

def main():
    # 从环境变量获取GitHub Token和用户名
    token = os.getenv('GH_TOKEN')
    username = os.getenv('USERNAME')

    if not token or not username:
        logging.error("GitHub Token或用户名未设置。")
        return

    # 创建GitHub仓库管理器实例
    manager = GitHubRepoManager()

    # 获取用户的所有仓库
    repos = manager.get_repos(username)

    for repo in repos:
        repo_name = repo['name']
        repo_owner = repo['owner']['login']

        # 获取该仓库所有工作流运行的详细信息
        all_runs = manager.get_workflow_runs(repo_owner, repo_name)

        # 按工作流名称分组，并保留每个名称的最新运行
        latest_runs = {}
        for run in all_runs:
            workflow_name = run['name']
            if workflow_name not in latest_runs or latest_runs[workflow_name]['created_at'] < run['created_at']:
                latest_runs[workflow_name] = run

        # 删除除最新之外的所有运行
        for run in all_runs:
            if run['id'] != latest_runs[run['name']]['id']:
                manager.delete_workflow(repo_owner, repo_name, run['id'])

        # 处理PRs和工作流运行记录
        manager.delete_non_successful_runs_for_repo(repo_owner, repo_name)
        manager.process_dependabot_prs(repo_owner, repo_name)
        manager.close_inactive_pull_requests_for_repo(repo_owner, repo_name)

if __name__ == "__main__":
    main()
