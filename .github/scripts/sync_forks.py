import asyncio
import aiohttp
import os
import git

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
                print(f"请求失败，状态码: {response.status}")
                break

            # 获取当前页面的仓库数据
            repos = await response.json()
            if not repos:  # 如果没有更多仓库，退出循环
                break

            forks.extend(repos)  # 将当前页面的仓库添加到 forks 列表
            page += 1  # 增加页面计数

    return forks


async def sync_fork(repo):
    try:
        # 克隆 fork 的仓库
        repo_dir = f"./{repo['name']}"
        if not os.path.exists(repo_dir):
            print(f"正在克隆 {repo['full_name']}...")
            git.Repo.clone_from(repo["git_url"], repo_dir)

        # 打开克隆的仓库
        repo_obj = git.Repo(repo_dir)

        # 添加 upstream 远程仓库
        upstream_url = repo["parent"]["git_url"]
        if "upstream" not in [remote.name for remote in repo_obj.remotes]:
            repo_obj.create_remote("upstream", upstream_url)

        # 获取 upstream 的更新
        repo_obj.remotes.upstream.fetch()

        # 检查 fork 是否落后于 upstream
        if repo_obj.is_ancestor(
            repo_obj.remotes.upstream.refs.master, repo_obj.head.ref
        ):
            print(f"{repo['full_name']} 落后于 upstream，正在尝试同步...")
            try:
                repo_obj.git.merge("upstream/master")
                print(f"{repo['full_name']} 同步成功。")
            except git.exc.GitCommandError as e:
                print(f"{repo['full_name']} 发生冲突，需要手动处理。")
                print(e)
        else:
            print(f"{repo['full_name']} 已与 upstream 同步。")

    except Exception as e:
        print(f"处理 {repo['full_name']} 时出错: {e}")


async def main():
    async with aiohttp.ClientSession() as session:
        # 获取所有 fork 仓库
        forks = await fetch_forks(session)
        tasks = []

        for repo in forks:
            # 检查是否为分叉且有父仓库
            if (
                repo.get("fork") is True and repo.get("parent") is not None
            ):  # 确保 fork 为 True 并且有 parent
                tasks.append(sync_fork(repo))
            else:
                print(
                    f"跳过仓库 {repo['full_name']}，因为它不是有效的有父仓库的 fork。"
                )

        # 并发执行所有同步任务
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    # 确保环境变量已设置
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        print("请设置环境变量 GITHUB_TOKEN 和 GITHUB_USERNAME。")
    else:
        asyncio.run(main())
