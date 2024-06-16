# test_auto_perms.py

import os
from unittest.mock import patch, Mock
import pytest

# 这里需要从auto_perms.py导入我们要测试的函数
from auto_perms import create_headers, list_repositories, get_workflow_permissions, set_workflow_permissions, main

# 由于我们的代码依赖于环境变量TOKEN和USERNAME，我们需要在测试中设置它们
os.getenv['GH_TOKEN'] = 'test_token'
os.getenv['USERNAME'] = 'test_user'

# 请求的模拟响应
mock_response_success = Mock(status_code=200, json=lambda: {})
mock_response_error = Mock(status_code=404, raise_for_status=lambda: Mock(side_effect=Exception("Not Found")))

# 模拟requests.get函数
@patch('auto_perms.requests.get')
def test_create_headers(mock_get):
    headers = create_headers()
    assert isinstance(headers, dict)
    assert 'Authorization' in headers
    assert headers['Authorization'] == 'token test_token'

@patch('auto_perms.requests.get')
def test_list_repositories(mock_get):
    # 假设API返回两个仓库
    mock_get.return_value = mock_response_success
    mock_get.return_value.json.return_value = [{'name': 'repo1'}, {'name': 'repo2'}]
    
    repos = list_repositories('test_user')
    assert len(repos) == 2
    mock_get.assert_called_with(any, headers=any)

@patch('auto_perms.requests.get')
def test_get_workflow_permissions(mock_get):
    mock_get.return_value = mock_response_success
    mock_get.return_value.json.return_value = {'enabled': True, 'allowed_actions': 'all'}
    
    repo = {'name': 'test_repo'}
    permissions = get_workflow_permissions(repo)
    assert permissions['enabled'] is True
    assert permissions['allowed_actions'] == 'all'

@patch('auto_perms.requests.put')
def test_set_workflow_permissions(mock_put):
    mock_put.return_value = mock_response_success
    
    repo = {'name': 'test_repo'}
    set_workflow_permissions(repo, 'all')
    mock_put.assert_called_with(any, headers=any, json=any)

# 因为main函数执行了网络请求并且依赖外部因素，我们可能不测试它或用不同的方式来测试
@pytest.mark.skip("Skipping main function test as it requires external interaction")
def test_main():
    with patch('auto_perms.list_repositories') as mock_list_repos, \
         patch('auto_perms.get_workflow_permissions') as mock_get_perms, \
         patch('auto_perms.set_workflow_permissions') as mock_set_perms:
        
        # 我们需要确保模拟的函数返回值是合理的
        mock_list_repos.return_value = [{'name': 'repo1'}]
        mock_get_perms.return_value = {'enabled': True, 'allowed_actions': 'some'}
        
        # 调用main函数
        main()

        # 检查是否调用了模拟的函数
        mock_list_repos.assert_called_once_with('test_user')
        mock_get_perms.assert_called_once()
        mock_set_perms.assert_called_once_with(any, 'all')