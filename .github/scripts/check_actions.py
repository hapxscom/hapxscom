import os
import logging
from github import Github

# 启用日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_github_actions(repo):
    """获取一个仓库的 GitHub Actions"""
    try:
        workflow_runs = repo.get_workflow_runs()
        action_runs = [(run.name, run.html_url, run.status) for run in workflow_runs]
        return action_runs
    except Exception as e:
        logger.error(f"获取仓库 {repo.name} 的 GitHub Actions 出错: {e}")
        return []

def main():
    try:
        GITHUB_TOKEN = os.getenv('GH_TOKEN')
        GITHUB_USERNAME = os.getenv('USERNAME')

        if not GITHUB_TOKEN or not GITHUB_USERNAME:
            logger.error("环境变量中未找到 GitHub 令牌或用户名。")
            return

        g = Github(GITHUB_TOKEN)
        user = g.get_user(GITHUB_USERNAME)
        repos = user.get_repos()

        for repo in repos:
            action_runs = get_github_actions(repo)
            if action_runs:
                logger.info(f"仓库 {repo.name} 中的 GitHub Actions:")
                for run_name, run_url, run_status in action_runs:
                    logger.info(f"Action 名称: {run_name}, 状态: {run_status}, URL: {run_url}")

    except Exception as e:
        logger.error(f"获取用户仓库时出错: {e}")

if __name__ == '__main__':
    main()
