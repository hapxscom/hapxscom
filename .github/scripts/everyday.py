from github import Github, GithubException
import logging

# 日志配置
logging.basicConfig(filename='trending_repos.log', level=logging.INFO)

# 设置GitHub Token（应从安全的环境变量或配置文件中获取）
g = Github("your_github_token_here")

def get_trending_repositories():
    try:
        trending_repositories = g.search_repositories(query='stars:>1', sort='stars')
        for repo in trending_repositories[:10]:
            information = f"Repository: {repo.name} Description: {repo.description} Stars: {repo.stargazers_count}"
            logging.info(information)

            for issue in repo.get_issues(state='open'):
                for label in issue.labels:
                    if any(keyword in label.name.lower() for keyword in ["chatgpt", "spigot", "minecraft"]):
                        special_info = f"Special Attention to Issue: {issue.title} in Repository: {repo.name} with label: {label.name}"
                        print(special_info)
                        logging.info(special_info)
    except GithubException as e:
        logging.error(f"GitHub API error: {e}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

get_trending_repositories()
