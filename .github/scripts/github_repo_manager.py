import logging
from datetime import datetime, timedelta
from github_api_client import GitHubAPIClient


class GitHubRepoManager:
    """
    GitHub仓库管理类，提供对GitHub仓库的各种操作，如删除工作流运行、获取仓库列表、关闭PR等。
    """

    def __init__(self):
        """
        初始化GitHubAPIClient用于API请求。
        """
        self.client = GitHubAPIClient()

    def delete_run(self, owner, repo, run_id):
        """
        删除指定仓库的工作流运行。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param run_id: 工作流运行ID。
        """
        """删除指定的工作流运行记录"""
        endpoint = f"repos/{owner}/{repo}/actions/runs/{run_id}"
        response = self.client.api_request("DELETE", endpoint)
        if response and response.status_code == 204:
            logging.info(f"从仓库 {repo} 删除运行记录 {run_id}")
        else:
            logging.error(f"无法从仓库 {repo} 删除运行记录 {run_id}")

    def get_repos(self, username):
        """
        获取指定用户的所有仓库。

        :param username: 用户名。
        :return: 仓库列表。
        """
        """获取用户的所有仓库，支持分页"""
        repos = []
        page = 1
        while True:
            endpoint = f"users/{username}/repos?page={page}&per_page=100"
            response = self.client.api_request("GET", endpoint)
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
        """
        删除指定仓库中所有未成功的工作流运行。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        """删除仓库中所有未成功的工作流运行记录"""
        page = 1
        while True:
            endpoint = f"repos/{owner}/{repo}/actions/runs?page={page}&per_page=100"
            response = self.client.api_request("GET", endpoint)
            if response and response.status_code == 200:
                runs_data = response.json()
                runs = runs_data.get("workflow_runs", [])
                if not runs:
                    break

                for run in runs:
                    if run["conclusion"] != "success":
                        self.delete_workflow(
                            owner, repo, run["id"]
                        )  # 使用统一的删除方法

                page += 1
            else:
                break

    def comment_on_pr(self, owner, repo, pr_number, body):
        """
        在指定的PR上发表评论。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param pr_number: PR编号。
        :param body: 评论内容。
        """
        """在指定的PR上发布评论"""
        endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        response = self.client.api_request("POST", endpoint, json={"body": body})
        if response and response.status_code == 201:
            logging.info(f"在 {owner}/{repo} 的PR #{pr_number} 上发表评论")
        else:
            logging.error(f"无法在 {owner}/{repo} 的PR #{pr_number} 上发表评论")

    def close_pr(self, owner, repo, pr_number):
        """
        关闭指定的PR。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param pr_number: PR编号。
        """
        """关闭指定的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.client.api_request("PATCH", endpoint, json={"state": "closed"})
        if response and response.status_code == 200:
            logging.info(f"关闭了 {owner}/{repo} 的PR #{pr_number}")
        else:
            logging.error(f"无法关闭 {owner}/{repo} 的PR #{pr_number}")

    def process_dependabot_prs(self, owner, repo):
        """
        处理指定仓库中由dependabot创建的PR。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        """处理指定仓库中由dependabot创建的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls"
        response = self.client.api_request("GET", endpoint)
        if response and response.status_code == 200:
            prs = response.json()
            for pr in prs:
                if pr["user"]["login"] == "dependabot[bot]":
                    mergeable_state = pr.get("mergeable_state")
                    if mergeable_state is not None and mergeable_state == "behind":
                        self.comment_on_pr(
                            owner, repo, pr["number"], "@dependabot rebase"
                        )

                    pr_created_at = datetime.strptime(
                        pr["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    if datetime.now() - pr_created_at > timedelta(days=30):
                        self.close_pr(owner, repo, pr["number"])
        else:
            logging.error(f"无法从仓库 {repo} 获取PRs")

    def is_inactive(self, updated_at):
        """
        判断PR是否不活跃。

        :param updated_at: PR的最后更新时间。
        :return: 如果PR不活跃返回True，否则返回False。
        """
        """判断PR是否不活跃（默认2天未活动）"""
        inactive_time = datetime.now() - timedelta(days=2)
        pr_last_updated = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
        return pr_last_updated < inactive_time

    def has_recent_activity(self, owner, repo, pr_number):
        """
        检查PR在过去2天内是否有评论或活动。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param pr_number: PR编号。
        :return: 如果PR有 recent activity 返回True，否则返回False。
        """
        """检查PR在过去2天内是否有评论或活动"""
        comments_endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        events_endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/events"

        comments_response = self.client.api_request("GET", comments_endpoint)
        if comments_response and comments_response.status_code == 200:
            comments = comments_response.json()
            for comment in comments:
                if datetime.strptime(
                    comment["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                ) > datetime.now() - timedelta(days=2):
                    return True

        events_response = self.client.api_request("GET", events_endpoint)
        if events_response and events_response.status_code == 200:
            events = events_response.json()
            for event in events:
                if datetime.strptime(
                    event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                ) > datetime.now() - timedelta(days=2):
                    return True

        return False

    def add_comment_to_pr(self, owner, repo, pr_number, comment):
        """
        给指定的Pull Request添加评论。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param pr_number: Pull Request的编号。
        :param comment: 要添加的评论内容。
        """
        endpoint = f"repos/{owner}/{repo}/issues/{pr_number}/comments"
        data = {"body": comment}
        response = self.client.api_request("POST", endpoint, json=data)
        if response.status_code != 201:
            logging.error(f"添加评论到PR #{pr_number} 失败")

    def close_inactive_pull_requests_for_repo(self, owner, repo):
        """
        关闭指定仓库中所有超过2天没有活动的PR，并在关闭时添加评论说明原因。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        endpoint = f"repos/{owner}/{repo}/pulls?state=open"
        response = self.client.api_request("GET", endpoint)
        if response and response.status_code == 200:
            pull_requests = response.json()
            for pr in pull_requests:
                if self.is_inactive(pr["updated_at"]) and not self.has_recent_activity(
                    owner, repo, pr["number"]
                ):
                    comment = "由于长时间无活动，此Pull Request已被自动关闭。"
                    self.add_comment_to_pr(owner, repo, pr["number"], comment)
                    self.close_pr(owner, repo, pr["number"])
                    logging.info(
                        f"由于长时间无活动，关闭了 {owner}/{repo} 的PR #{pr['number']} 并添加了评论"
                    )
        else:
            logging.error(f"无法获取 {owner}/{repo} 的开放PR列表")

    def get_workflow_runs(self, owner, repo, per_page=100):
        """
        获取指定仓库的所有工作流运行的详细信息，改进错误处理。
        """
        runs_data = []
        page = 1
        while True:
            endpoint = (
                f"repos/{owner}/{repo}/actions/runs?page={page}&per_page={per_page}"
            )
            response = self.client.api_request("GET", endpoint)

            if response is not None:
                if response.status_code == 200:
                    runs = response.json().get("workflow_runs", [])
                    runs_data.extend(runs)

                    if len(runs) < per_page:
                        break
                    page += 1
                else:
                    logging.error(
                        f"获取仓库 '{repo}' 的工作流运行失败。状态码：{response.status_code}"
                    )
                    break
            else:
                logging.error(f"请求仓库 '{repo}' 的工作流运行时未获得响应。")
                break

        return runs_data

    def delete_workflow(self, owner, repo, workflow_id):
        """
        删除指定仓库中的指定工作流。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        :param workflow_id: 工作流ID。
        """
        # 先检查工作流是否正在运行
        endpoint = f"repos/{owner}/{repo}/actions/runs/{workflow_id}"
        response = self.client.api_request("GET", endpoint)

        if response is not None and response.status_code == 200:
            workflow_run = response.json()
            if workflow_run.get("status") == "in_progress":
                logging.info(
                    f"工作流 ID {workflow_id} 在仓库 '{repo}' 中正在运行，跳过删除。"
                )
                return
            else:
                # 获取详细信息
                commit_id = workflow_run.get("head_sha", "未知")
                commit_pusher = (
                    workflow_run.get("head_commit", {})
                    .get("committer", {})
                    .get("name", "未知")
                )
                created_at = workflow_run.get("created_at", "未知")
                branch = workflow_run.get("head_branch", "未知")
                logging.info(
                    f"工作流 ID {workflow_id} 状态为 '{workflow_run.get('status')}'，准备删除。"
                )
                logging.info(f"  commit_id={commit_id}")
                logging.info(f"  推送者={commit_pusher}")
                logging.info(f"  创建时间={created_at}")
                logging.info(f"  分支={branch}")
        else:
            logging.error(f"获取工作流 {workflow_id} 状态时失败，无法进行删除。")
            return

        # 尝试删除工作流
        endpoint = f"repos/{owner}/{repo}/actions/runs/{workflow_id}"
        response = self.client.api_request("DELETE", endpoint)

        if response is None:
            logging.error(
                f"尝试删除仓库 '{repo}' 中ID为 '{workflow_id}' 的工作流失败。未收到有效响应。"
            )
        elif response.status_code == 204:
            logging.info(f"已成功删除仓库 '{repo}' 中ID为 '{workflow_id}' 的工作流。")
        else:
            logging.error(
                f"尝试删除仓库 '{repo}' 中ID为 '{workflow_id}' 的工作流失败。状态码：{response.status_code}"
            )

    def maintain_repo_workflows(self, owner, repo):
        """
        维护指定仓库的工作流，保留最新的工作流运行并删除其他运行。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        """维护特定仓库的工作流，保留最新的工作流运行并删除其他的"""
        all_runs = self.get_workflow_runs(owner, repo)
        latest_runs = {}
        for run in all_runs:
            workflow_name = run["name"]
            if (
                workflow_name not in latest_runs
                or latest_runs[workflow_name]["created_at"] < run["created_at"]
            ):
                latest_runs[workflow_name] = run

        for run in all_runs:
            if run["id"] != latest_runs[run["name"]]["id"]:
                self.delete_workflow(owner, repo, run["id"])  # 统一调用删除方法

    def close_all_open_prs(self, owner, repo):
        """
        关闭指定仓库中所有打开的PR。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        """关闭指定仓库中所有打开的PR"""
        endpoint = f"repos/{owner}/{repo}/pulls?state=open"
        response = self.client.api_request("GET", endpoint)
        if response and response.status_code == 200:
            pull_requests = response.json()
            for pr in pull_requests:
                self.close_pr(owner, repo, pr["number"])
                logging.info(f"关闭了 {owner}/{repo} 的PR #{pr['number']}")
        else:
            logging.error(f"无法获取 {owner}/{repo} 的开放PR列表")

    def delete_dependabot_runs_for_repo(self, owner, repo):
        """
        删除指定仓库中所有由 dependabot[bot] 触发的工作流运行。

        :param owner: 仓库所有者。
        :param repo: 仓库名称。
        """
        all_runs = self.get_workflow_runs(owner, repo)
        for run in all_runs:
            actor = run.get("triggering_actor") or run.get("actor")
            # triggering_actor 结构为 dict，actor 也可能为 dict
            login = None
            if isinstance(actor, dict):
                login = actor.get("login")
            elif isinstance(actor, str):
                login = actor
            if login == "dependabot[bot]":
                # 打印详细信息
                commit_id = run.get("head_sha", "未知")
                commit_pusher = (
                    run.get("head_commit", {}).get("committer", {}).get("name", "未知")
                )
                created_at = run.get("created_at", "未知")
                branch = run.get("head_branch", "未知")
                logging.info(f"准备删除 dependabot 触发的 workflow_run:")
                logging.info("  id=" + str(run["id"]))
                logging.info(f"  commit_id={commit_id}")
                logging.info(f"  推送者={commit_pusher}")
                logging.info(f"  创建时间={created_at}")
                logging.info(f"  分支={branch}")
                self.delete_workflow(owner, repo, run["id"])
