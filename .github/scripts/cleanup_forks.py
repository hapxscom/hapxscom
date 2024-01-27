import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

# 从环境变量读取GitHub Token和邮件服务器信息
TOKEN = os.getenv('GH_TOKEN')
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
ADMIN_EMAIL = 'admin@wdsj.one'

# 设置请求头
headers = {
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

def get_forks():
    """获取用户的所有fork仓库"""
    url = 'https://api.github.com/user/repos?type=forks'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch repositories, HTTP status code: {response.status_code}")
        return []

def merge_upstream(repo):
    """尝试合并上游仓库的改动"""
    compare_url = f"{repo['parent']['url']}/compare/{repo['default_branch']}...{repo['owner']['login']}:{repo['default_branch']}"
    compare_response = requests.get(compare_url, headers=headers)
    if compare_response.status_code == 200 and compare_response.json()['status'] == 'identical':
        print(f"{repo['full_name']} is up to date with upstream.")
        return
    elif compare_response.status_code == 200 and compare_response.json()['ahead_by'] > 0:
        # Fork ahead of upstream, no merge needed
        print(f"{repo['full_name']} is ahead of upstream, no merge needed.")
        return
    merge_url = f"{repo['url']}/merges"
    merge_data = {
        'base': repo['default_branch'],
        'head': repo['parent']['default_branch'],
        'commit_message': f"Merge upstream changes from {repo['parent']['full_name']} into {repo['default_branch']}"
    }
    merge_response = requests.post(merge_url, headers=headers, json=merge_data)
    if merge_response.status_code in [200, 201]:
        print(f"Successfully merged {repo['parent']['full_name']} into {repo['full_name']}")
    else:
        error_message = merge_response.json().get('message', 'No error message')
        print(f"Failed to merge {repo['parent']['full_name']} into {repo['full_name']}: {error_message}")
        # Construct email content
        subject = f"Merge conflict: {repo['full_name']}"
        body = f"There was an error merging upstream changes from the fork at: {repo['html_url']}\n\nError message: {error_message}\n\nPlease check manually."
        send_email(subject, body, ADMIN_EMAIL)

def send_email(subject, body, recipient):
    """发送电子邮件"""
    message = MIMEMultipart()
    message['From'] = Header(EMAIL_HOST_USER)
    message['To'] = Header(recipient)
    message['Subject'] = Header(subject)
    message.attach(MIMEText(body, 'plain', 'utf-8'))
    with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.sendmail(EMAIL_HOST_USER, recipient, message.as_string())
        print(f"Email sent to {recipient} with subject: {subject}")

# 主逻辑
forks = get_forks()
for fork in forks:
    merge_upstream(fork)