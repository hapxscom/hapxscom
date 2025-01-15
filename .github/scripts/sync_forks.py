import asyncio
import aiohttp
import os
import logging
import shutil
import subprocess
from bs4 import BeautifulSoup

# 设置日志配置
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 从环境变量中获取 GitHub API Token 和用户名
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

# GitHub API 基础 URL
GITHUB_API_URL = "https://api.github.com"


async def fetch_forks(session):
    # 获取当前用户的所有仓库
    url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/repos"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    forks = []
    page = 1
    while True:
        params = {"page": page, "per_page": 100}  # 每页请求 100 个仓库
        async with session.get(url, headers=headers, params=params) as response:
            # 检查响应状态
            if response.status != 200:
                logging.error(f"请求失败，状态码: {response.status}")
                break

            # 获取当前页面的仓库数据
            repos = await response.json()
            if not repos:  # 如果没有更多仓库，退出循环
                break

            forks.extend(repos)  # 将当前页面的仓库添加到 forks 列表
            page += 1  # 增加页面计数

    return forks


async def get_upstream_url(session, repo_full_name):
    """获取父仓库的 URL"""
    url = f"https://github.com/{repo_full_name}"
    async with session.get(url) as response:
        if response.status != 200:
            logging.error(f"无法获取仓库页面，状态码: {response.status}")
            return None

        # 解析 HTML 内容
        html_content = await response.text()
        soup = BeautifulSoup(html_content, "html.parser")

        # 查找父仓库的链接
        forked_from_span = soup.find(
            "span", class_="text-small lh-condensed-ultra no-wrap mt-1"
        )
        if forked_from_span:
            a_tag = forked_from_span.find("a")
            if a_tag and "href" in a_tag.attrs:
                upstream_repo = a_tag.attrs["href"].strip("/")
                upstream_url = f"https://github.com/{upstream_repo}.git"
                return upstream_url

    logging.warning(f"未找到 {repo_full_name} 的父仓库信息。")
    return None


def clone_repo(repo_url, repo_dir):
    """尝试使用 Git 命令克隆仓库"""
    # 将 git:// 替换为 https://
    if repo_url.startswith("git://"):
        repo_url = repo_url.replace("git://", "https://")

    try:
        logging.info(f"正在使用 Git 命令克隆 {repo_url} 到 {repo_dir}...")
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)
        logging.info(f"{repo_url} 克隆成功。")
    except subprocess.CalledProcessError:
        logging.error(f"使用 Git 命令克隆 {repo_url} 失败。")
        return False
    return True


def install_git():
    """检查 Git 是否安装，如果未安装则使用 apt 安装"""
    try:
        logging.info("检查 Git 是否安装...")
        subprocess.run(["git", "--version"], check=True)
        logging.info("Git 已安装。")
    except subprocess.CalledProcessError:
        logging.error("Git 未安装，正在使用 apt 安装 Git...")
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "git", "-y"], check=True)
        logging.info("Git 安装完成。")


async def sync_fork(session, repo):
    try:
        # 获取父仓库的 URL
        upstream_url = await get_upstream_url(session, repo["full_name"])
        if not upstream_url:
            logging.error(f"无法获取 {repo['full_name']} 的父仓库 URL，跳过该仓库。")
            return

        # 克隆 fork 的仓库
        repo_dir = f"./{repo['name']}"
        if not os.path.exists(repo_dir):
            logging.info(f"正在克隆 {repo['full_name']}...")

            # 尝试使用 Git 命令克隆
            if not clone_repo(repo["git_url"], repo_dir):
                # 如果 Git 命令失败，检查 Git 是否安装
                install_git()
                # 尝试再次使用 Git 命令克隆
                if not clone_repo(repo["git_url"], repo_dir):
                    logging.error(f"无法克隆 {repo['full_name']}，请手动检查。")
                    return

        # 添加 upstream 远程仓库
        logging.info(f"添加 upstream 远程仓库 {upstream_url} 到 {repo['full_name']}...")
        subprocess.run(
            ["git", "-C", repo_dir, "remote", "add", "upstream", upstream_url],
            check=True,
        )

        # 获取 upstream 的更新
        logging.info(f"获取 {repo['full_name']} 的 upstream 更新...")
        subprocess.run(["git", "-C", repo_dir, "fetch", "upstream"], check=True)

        # 检查 upstream 的默认分支
        default_branch = "master"  # 默认分支
        try:
            # 获取 upstream 的默认分支
            upstream_branches = (
                subprocess.check_output(["git", "-C", repo_dir, "branch", "-r"])
                .decode()
                .strip()
                .split("\n")
            )
            for branch in upstream_branches:
                if "upstream/main" in branch:
                    default_branch = "main"  # 如果找到 main 分支，则更新默认分支
                    break
        except Exception as e:
            logging.error(f"检查 upstream 默认分支时出错: {e}")

        # 检查 fork 是否落后于 upstream
        logging.info(f"检查 {repo['full_name']} 是否落后于 upstream...")
        if (
            subprocess.run(
                [
                    "git",
                    "-C",
                    repo_dir,
                    "merge-base",
                    "--is-ancestor",
                    f"upstream/{default_branch}",
                    "HEAD",
                ]
            ).returncode
            == 0
        ):
            logging.info(f"{repo['full_name']} 落后于 upstream，正在尝试同步...")
            try:
                subprocess.run(
                    ["git", "-C", repo_dir, "merge", f"upstream/{default_branch}"],
                    check=True,
                )
                logging.info(f"{repo['full_name']} 同步成功。")
            except subprocess.CalledProcessError as e:
                logging.error(f"{repo['full_name']} 发生冲突，需要手动处理。")
                logging.error(e)
        else:
            logging.info(f"{repo['full_name']} 已与 upstream 同步。")

    except Exception as e:
        logging.error(f"处理 {repo['full_name']} 时出错: {e}")
    finally:
        # 删除克隆的仓库
        if os.path.exists(repo_dir):
            logging.info(f"正在删除克隆的仓库 {repo['full_name']}...")
            shutil.rmtree(repo_dir)


async def main():
    async with aiohttp.ClientSession() as session:
        # 获取所有 fork 仓库
        forks = await fetch_forks(session)

        for repo in forks:
            # 检查是否为分叉且有父仓库
            if repo.get("fork") == True:  # 确保 fork 为 True
                await sync_fork(session, repo)  # 确保依次处理每个仓库
            else:
                logging.info(
                    f"跳过仓库 {repo['full_name']}，因为它不是有效的有父仓库的 fork。"
                )


if __name__ == "__main__":
    # 确保环境变量已设置
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        logging.error("请设置环境变量 GITHUB_TOKEN 和 GITHUB_USERNAME。")
    else:
        asyncio.run(main())
