# 导入requests库，用于发送HTTP请求
import requests
# 导入requests的异常类，用于处理请求中可能出现的异常
from requests.exceptions import HTTPError, Timeout, TooManyRedirects
# 导入logging库，用于记录日志
import logging
# 导入os库，用于获取环境变量
import os
# 导入time库，用于延迟操作
import time

# 设置日志记录的基本配置
# 设置日志记录
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("github_api_client.log"), logging.StreamHandler()])

class GitHubAPIClient:
    """
    GitHub API客户端类，用于封装对GitHub API的请求。
    """
    def __init__(self):
        """
        初始化方法，设置API的基础URL和请求的默认头部。
        """
        self.base_url = 'https://api.github.com'  # GitHub API的基础URL
        self.session = requests.Session()  # 创建一个请求会话，用于复用连接和头部信息
        # 更新会话的头部，包括认证令牌和接受的API版本
        self.session.headers.update({
            'Authorization': f'token {os.getenv("GH_TOKEN")}',
            'Accept': 'application/vnd.github.v3+json'
        })

    def api_request(self, method, endpoint, max_retries=3, **kwargs):
        """
        发送API请求，并处理重试逻辑。
        
        参数:
        method - 请求的方法（GET、POST等）。
        endpoint - API的端点路径。
        max_retries - 最大重试次数，默认为3。
        **kwargs - 传递给requests请求方法的额外参数。
        
        返回:
        requests.Response对象，如果所有重试都失败，则返回None。
        """
        """
        发送API请求并返回响应，带重试逻辑，并自动设置头部
        """
        url = f"{self.base_url}/{endpoint}"  # 构建请求的完整URL
        retries = 0  # 初始化重试次数
        while retries < max_retries:
            try:
                response = self.session.request(method, url, **kwargs)  # 发送请求
                response.raise_for_status()  # 检查响应状态码，如有异常则抛出
                self._check_rate_limit(response)  # 检查速率限制
                return response  # 返回响应对象
            except (HTTPError, Timeout, TooManyRedirects) as e:  # 捕获请求过程中可能出现的异常
                retries += 1  # 增加重试次数
                logging.error(f"请求失败: {e}, URL: {url}. 重试 {retries}/{max_retries}")  # 记录错误日志
                if e.response:
                    logging.error(f"响应内容: {e.response.text}")  # 如果有响应内容，则记录响应内容
                time.sleep(2**retries)  # 指数退避策略，延迟重试时间
        return None  # 如果重试次数达到上限，返回None

    def _check_rate_limit(self, response):
        """
        检查API速率限制，并根据情况暂停请求。
        
        参数:
        response - requests.Response对象，用于获取响应头部信息。
        """
        """
        检查速率限制，如果接近限制则暂停
        """
        if 'X-RateLimit-Remaining' in response.headers:  # 检查剩余请求次数
            remaining = int(response.headers['X-RateLimit-Remaining'])  # 获取剩余请求次数
            if remaining < 10:  # 如果剩余请求次数少于10次
                reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))  # 获取速率限制重置的时间戳
                sleep_time = max(reset_time - time.time(), 3)  # 计算需要暂停的时间，至少为3秒
                logging.info(f"达到速率限制，暂停 {sleep_time} 秒")  # 记录信息日志
                time.sleep(sleep_time)  # 暂停请求