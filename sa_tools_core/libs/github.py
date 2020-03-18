import requests
import base64
import json
import logging
from sa_tools_core.consts import (GITHUB_USERNAME, GITHUB_PERSONAL_TOKEN, GITHUB_API_ENTRYPOINT)

logger = logging.getLogger(__name__)


class GithubRepo:
    def __init__(self, org, repo, entrypoint="https://github.intra.douban.com/api/v3",
                 user_name=None, personal_token=None, author=None, skip_ssl=False):
        self.org = org
        self.repo = repo
        self.author = author
        self.entrypoint = entrypoint
        self.base_commit = None
        self.base_tree = None
        self.head_commit = None
        self.head_tree = None
        self.user_name = user_name
        self.personal_token = personal_token
        self.session = requests.Session()
        self.session.auth = (self.user_name, self.personal_token)
        self.skip_ssl = skip_ssl

    def make_request(self, method, api_path, **kwargs):
        r = self.session.request(method, f"{self.entrypoint}{api_path}", verify=(not self.skip_ssl), **kwargs)
        try:
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(r.text)
            raise e
        return r.json()

    def get_file(self, path, reference=None):
        """get content
        GET /repos/:owner/:repo/contents/:path
        :: params
        reference: str 分支, tag 或 commit id, 默认获取repo 的默认分支
        path: str 相对路径
        :: return
        dict 文件内容在 content 内, 按照 encoding 的encoding 方法 encode.
        """
        return self.make_request('GET', f"/repos/{self.org}/{self.repo}/contents/{path}",
                                 params={'ref': reference or 'master'})

    def get_reference(self, reference):
        return self.make_request('GET', f"/repos/{self.org}/{self.repo}/git/ref/heads/{reference}")

    def get_commit(self, commit_sha):
        return self.make_request('GET', f"/repos/{self.org}/{self.repo}/git/commits/{commit_sha}")

    def update_a_file(self, path, content, message, sha):
        return self.make_request('PUT', f"/repos/{self.org}/{self.repo}/contents/{path}",
                                 data=json.dumps({
                                     'message': message,
                                     'content': base64.encodebytes(content).decode(),
                                     'sha': sha
                                 }))

    def upload_one_file(self, content):
        """ 用blobs 接口把文件上传到 github, 返回github 接口返回的字典, 相当于加入工作区
        POST /repos/:owner/:repo/git/blobs
        :: input
        {
            "content": "Content of the blob",
            "encoding": "utf-8"
        }
        :: return
        {
            "url": "https://api.github.com/repos/octocat/example/git/blobs/3a0f86fb8db8eea7ccbb9a95f325ddbedfb25e15",
            "sha": "3a0f86fb8db8eea7ccbb9a95f325ddbedfb25e15"
        }

        """
        return self.make_request('POST', f"/repos/{self.org}/{self.repo}/git/blobs",
                                 data=json.dumps({
                                     'content': base64.encodebytes(content).decode(),
                                     'encoding': 'base64'
                                 }))

    def create_tree(self, base_tree, files):
        """ 相当于加入 git 的索引 git add
        """
        return self.make_request('POST', f"/repos/{self.org}/{self.repo}/git/trees",
                                 data=json.dumps({
                                     'base_tree': base_tree,
                                     'tree': files
                                 }))

    def create_commit(self, base, tree, message):
        """ 相当于 git commit
        """
        return self.make_request('POST', f"/repos/{self.org}/{self.repo}/git/commits",
                                 data=json.dumps({
                                     'message': message,
                                     'tree': tree,
                                     'parents': [base]
                                 }))

    def update_reference(self, reference, commit_sha):
        """ 相当于 git push
        PATCH /repos/:owner/:repo/git/refs/:ref
        可能会产生 None fast farword 的错误
        """
        return self.make_request('PATCH', f"/repos/{self.org}/{self.repo}/git/refs/heads/{reference}",
                                 data=json.dumps({
                                     "sha": commit_sha,
                                     'force': False
                                 }))

    # high level api starts here
    def add(self, files, base_reference):
        """add files to the tree, generate a tree , store the tree_sha to self.head_tree"""
        files_sha = []
        # upload
        for path, content in files.items():
            remote_content = self.get_file(path, reference=base_reference)
            if remote_content['content'] == base64.encodebytes(content).decode():
                logger.info(f'{path} unchange, ignored')
                continue
            upload_result = self.upload_one_file(content)
            files_sha += [{
                'path': path,
                'sha': upload_result['sha'],
                'type': 'blob',
                'mode': '100644'
            }]
        if len(files_sha) == 0:
            logger.info("changelist empty, ignored")
            return

        # add to index, need tree base sha
        base_branch = self.get_reference(base_reference)
        self.base_commit = self.get_commit(base_branch['object']['sha'])
        self.head_tree = self.create_tree(self.base_commit['tree']['sha'], files_sha)

    def commit(self, message):
        self.head_commit = self.create_commit(self.base_commit['sha'], self.head_tree['sha'], message)
        logger.info('commit create: %s', self.head_commit['url'])

    def push(self, reference):
        self.update_reference(reference, self.head_commit['sha'])

    def update_files(self, reference, files, message):
        """update reference
        reference: str 分支, tag
        files: dict {file_path, filecontent}
            file_path -> str
            filecontent -> bytes
            example: {'example.md', b'Hello world', 'libs/example2.md', b'Hello world2'}
        possible erros:
        Web failed, timeout, 404, 403.
        None fast forward.
        No change.
        """
        if len(files.keys()) == 1:
            # simple update file
            path = list(files.keys())[0]
            content = files[path]
            base_file = self.get_file(path, reference=reference)
            if base_file['content'] == base64.encodebytes(content).decode():
                logger.info(f'{path} unchange, ignored')
            else:
                self.update_a_file(path, content, message, base_file['sha'])
            return

        self.add(files, reference)
        self.commit(message)
        self.push(reference)


def commit_github(org, repo, branch, files, message, retry=2):
    """通过 Github API 更新某个repo的某个branch
    ::params:
        org: str
        repo: str
        branch: str
        files: dict {file_path, filecontent}
            file_path -> str
            filecontent -> bytes
            example: {'example.md', b'Hello world', 'libs/example2.md', b'Hello world2'}
    """
    gh = GithubRepo(org, repo,
                    user_name=GITHUB_USERNAME, personal_token=GITHUB_PERSONAL_TOKEN, entrypoint=GITHUB_API_ENTRYPOINT)
    return_value = -1
    for _ in retry + 1:
        try:
            gh.update_files(branch, files, message)
            return_value = 0
            break
        except Exception as e:
            logger.warning(e)
            logger.warning('Request failed , retrying')
    return return_value
