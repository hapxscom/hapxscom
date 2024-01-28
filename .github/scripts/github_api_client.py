import requests
from requests.exceptions import HTTPError, Timeout, TooManyRedirects
import logging
import os
import time

# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_api_client.log"), logging.StreamHandler()])

class GitHubAPIClient:
    def __init__(self):
        self.base_url = 'https://api.github.com'
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {os.getenv("GH_TOKEN")}',
            'Accept': 'application/vnd.github.v3+json'
        })

    def api_request(self, method, endpoint, max_retries=3, **kwargs):
        """
        发送API请求并返回响应，带重试逻辑，并自动设置头部
        """
        url = f"{self.base_url}/{endpoint}"
        retries = 0
        while retries < max_retries:
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                self._check_rate_limit(response)
                return response
            except (HTTPError, Timeout, TooManyRedirects) as e:
                retries += 1
                logging.error(f"请求失败: {e}, URL: {url}. 重试 {retries}/{max_retries}")
                if e.response:
                    logging.error(f"响应内容: {e.response.text}")
                time.sleep(2**retries)  # 指数退避
        return None

    def _check_rate_limit(self, response):
        """
        检查速率限制，如果接近限制则暂停
        """
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                sleep_time = max(reset_time - time.time(), 3)  # 至少等待3秒
                logging.info(f"达到速率限制，暂停 {sleep_time} 秒")
                time.sleep(sleep_time)
