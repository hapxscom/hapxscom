# 导入必要的库，用于操作GitHub API、处理HTTP请求和日志记录
import os
import requests
import logging
from requests.structures import CaseInsensitiveDict

# 配置日志记录，以便在文件和控制台中记录信息、警告和错误
# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_automation.log"), logging.StreamHandler()])

# 定义GitHub API的基础URL
# GitHub API URL
base_url = 'https://api.github.com'

# 从环境变量中获取GitHub Token和用户名，用于身份验证
# 使用环境变量来获取GitHub Token和用户名
TOKEN = os.getenv('GH_TOKEN')
USERNAME = os.getenv('USERNAME')

def create_headers():
    """
    创建请求头字典，包含GitHub Token进行身份验证
    返回:
        CaseInsensitiveDict: 包含Authorization头部的字典
    """
    """创建请求头"""
    headers = CaseInsensitiveDict()
    headers["Authorization"] = f"token {TOKEN}"
    return headers

def list_repositories(user):
    """
    获取指定用户的所有仓库列表，处理GitHub API的分页
    参数:
        user (str): GitHub用户名
    返回:
        list: 包含仓库信息的列表
    """
    all_repos = []
    page = 1
    headers = create_headers()
    while True:
        # 构建API URL，包括当前页码和每页项目数量
        repos_url = f"{base_url}/users/{user}/repos?page={page}&per_page=100"
        try:
            # 发送GET请求获取仓库列表
            response = requests.get(repos_url, headers=headers)
            response.raise_for_status()
            repos = response.json()
            # 如果当前页没有仓库，则停止循环
            if not repos:
                break
            # 将当前页的仓库添加到总列表中
            all_repos.extend(repos)
            # 增加页码以获取下一页
            page += 1
        except requests.exceptions.RequestException as e:
            # 记录请求异常并停止循环
            logging.error(f"无法列出仓库: {e}")
            break
    return all_repos

def get_workflow_permissions(repo):
    """
    获取指定仓库的工作流权限信息
    参数:
        repo (dict): 包含仓库名称和其它信息的字典
    返回:
        dict: 包含工作流权限信息的字典
    """
    """获取仓库的当前工作流权限"""
    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = create_headers()
    
    try:
        # 发送GET请求获取权限信息
        response = requests.get(permissions_url, headers=headers)
        response.raise_for_status()

        # 记录成功获取权限信息的日志
        # 添加详细日志记录
        logging.info(f"成功获取仓库 {repo['name']} 的工作流权限，状态码: {response.status_code}")
        permissions = response.json()
        # 记录详细权限信息的日志（调试级别）
        logging.debug(f"获取到的具体权限信息: {permissions}")

        return permissions

    except requests.exceptions.RequestException as e:
        # 记录请求异常的日志
        logging.error(f"无法获取仓库 {repo['name']} 的工作流权限: {e}")

def set_workflow_permissions(repo, permission):
    """
    设置指定仓库的工作流权限
    参数:
        repo (dict): 包含仓库名称和其它信息的字典
        permission (str): 需要设置的工作流权限，可以是"all"或其他限定权限
    """
    """设置仓库的工作流权限"""
    if permission == "all":
        # 如果权限为"all"，则记录日志并返回，不进行API请求
        logging.info(f"仓库 {repo['name']} 的工作流权限已设置为 'all'.")
        return

    permissions_url = f"{base_url}/repos/{USERNAME}/{repo['name']}/actions/permissions"
    headers = create_headers()
    headers["Accept"] = "application/vnd.github.v3+json"
    data = {"permission": permission}

    try:
        # 发送PUT请求更新权限
        response = requests.put(permissions_url, headers=headers, json=data)
        response.raise_for_status()

        # 记录成功更新权限的日志
        # 添加详细日志记录
        logging.info(f"成功更新仓库 {repo['name']} 的工作流权限，状态码: {response.status_code}")

    except requests.exceptions.RequestException as e:
        # 记录请求异常的日志
        logging.error(f"无法设置仓库 {repo['name']} 的工作流权限, 错误信息: {e}")

def main():
    # 获取用户名下的所有仓库
    repos = list_repositories(USERNAME)
    # 记录仓库总数的日志
    logging.info(f"需要检查的仓库总数: {len(repos)}")

    # 遍历所有仓库，检查并更新工作流权限
    for repo in repos:
        permissions = get_workflow_permissions(repo)
        # 如果工作流已启用但权限不是"all"，则更新权限为"all"
        if permissions and permissions.get('enabled', False) and permissions.get('allowed_actions', '') != 'all':
            logging.info(f"正在将仓库: {repo['name']} 的权限更新为 'all'")
            set_workflow_permissions(repo, "all")

# 当脚本直接运行时执行main函数
if __name__ == "__main__":
    main()