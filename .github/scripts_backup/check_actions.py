import os
import logging
from github import Github

# 初始化日志记录器，用于记录程序运行过程中的信息
# 启用日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_automation.log"), logging.StreamHandler()])
logger = logging.getLogger()

def get_github_actions(repo):
    """
    获取给定仓库的GitHub Actions运行信息。
    
    参数:
    repo -- Github仓库对象。
    
    返回:
    一个包含Actions名称、URL和状态的列表。
    """
    """获取一个仓库的 GitHub Actions"""
    try:
        workflow_runs = repo.get_workflow_runs()
        action_runs = [(run.name, run.html_url, run.status) for run in workflow_runs]
        return action_runs
    except Exception as e:
        logger.error(f"获取仓库 {repo.name} 的 GitHub Actions 出错: {e}")
        return []

def get_repositories(user):
    """
    获取给定用户的所有仓库。
    
    参数:
    user -- Github用户对象。
    
    返回:
    一个生成器，生成用户的所有仓库对象。
    """
    """获取用户的所有仓库"""
    try:
        for repo in user.get_repos():
            yield repo
    except Exception as e:
        logger.error(f"获取用户 {user.login} 的仓库时出错: {e}")

def main():
    """
    主函数，程序的入口点。
    它负责配置GitHub客户端并遍历用户仓库，获取并记录每个仓库的GitHub Actions信息。
    """
    try:
        GITHUB_TOKEN = os.getenv('GH_TOKEN')
        GITHUB_USERNAME = os.getenv('USERNAME')

        if not GITHUB_TOKEN or not GITHUB_USERNAME:
            logger.error("环境变量中未找到 GitHub 令牌或用户名。")
            return

        g = Github(GITHUB_TOKEN)
        user = g.get_user(GITHUB_USERNAME)

        for repo in get_repositories(user):
            logger.info(f"检索仓库 {repo.name} (作者: {repo.owner.login}, 私有: {'是' if repo.private else '否'})")
            action_runs = get_github_actions(repo)
            if action_runs:
                for run_name, run_url, run_status in action_runs:
                    logger.info(f"Action 名称: {run_name}, 状态: {run_status}, URL: {run_url}")

    except Exception as e:
        logger.error(f"获取用户仓库时出错: {e}")

if __name__ == '__main__':
    main()