import responses
import pytest
import mirrormaker
from mirrormaker import github
from mirrormaker import gitlab
from mirrormaker.mirrormaker import check_mirror_status


@responses.activate
def test_filter_forked_repos():
    resp_json = [{'name': 'repo_1', 'fork': True},
                 {'name': 'repo_2', 'fork': False}]

    responses.add(responses.GET, 'https://api.github.com/user/repos?type=public',
                  json=resp_json, status=200)

    github_repos = github.get_repos()

    assert len(github_repos) == 1
    assert github_repos[0]['name'] == 'repo_2'


@responses.activate
def test_filter_no_repos():
    responses.add(responses.GET, 'https://api.github.com/user/repos?type=public',
                  json=[], status=200)

    github_repos = github.get_repos()

    assert len(github_repos) == 0


def test_mirror_exists():
    mirrors = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    github_repos = [{'full_name': 'grdl/one'},
                    {'full_name': 'grdl/two'}]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == True

    mirrors = []
    github_repos = [{'full_name': 'grdl/one'}]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    github_repos = [{'full_name': 'grdl/two'}]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors = []
    github_repos = []

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors = [{'url': 'https://*****:*****@github.com/grdl/one.git'}]
    github_repos = []

    assert gitlab.mirror_target_exists(github_repos, mirrors) == False

    mirrors = [{'url': 'https://*****:*****@github.com/grdl/one.git'},
               {'url': 'https://*****:*****@github.com/grdl/two.git'}]
    github_repos = [{'full_name': 'grdl/two'},
                    {'full_name': 'grdl/three'}]

    assert gitlab.mirror_target_exists(github_repos, mirrors) == True


def test_github_repo_exists():
    github_repos = [{'full_name': 'grdl/one'},
                    {'full_name': 'grdl/two'}]

    slug = 'grdl/one'

    assert github.repo_exists(github_repos, slug) == True

    slug = 'grdl/three'

    assert github.repo_exists(github_repos, slug) == False

    assert github.repo_exists([], slug) == False


@responses.activate
def test_get_gitlab_repos():
    resp_json = [{'id': 1, 'path_with_namespace': 'user/repo1'},
                {'id': 2, 'path_with_namespace': 'user/repo2'}]
    
    responses.add(responses.GET, 'https://gitlab.com/api/v4/projects?visibility=public&owned=true&archived=false',
                  json=resp_json, status=200)
    
    gitlab_repos = gitlab.get_repos()
    
    assert len(gitlab_repos) == 2
    assert gitlab_repos[0]['path_with_namespace'] == 'user/repo1'
    assert gitlab_repos[1]['path_with_namespace'] == 'user/repo2'


@responses.activate
def test_check_mirror_status():
    gitlab_repo = {'id': 1, 'path_with_namespace': 'user/repo1', 'path': 'repo1'}
    github_repos = [{'full_name': 'user/repo1'}]
    
    # Test when no mirrors exist
    responses.add(responses.GET, 'https://gitlab.com/api/v4/projects/1/remote_mirrors',
                  json=[], status=200)
    
    action = check_mirror_status(gitlab_repo, github_repos)
    
    assert action['create_github'] == False
    assert action['create_mirror'] == True
    
    # Test when mirror exists
    responses.reset()
    responses.add(responses.GET, 'https://gitlab.com/api/v4/projects/1/remote_mirrors',
                  json=[{'url': 'https://*****:*****@github.com/user/repo1.git'}], status=200)
    
    action = check_mirror_status(gitlab_repo, github_repos)
    
    assert action['create_github'] == False
    assert action['create_mirror'] == False
