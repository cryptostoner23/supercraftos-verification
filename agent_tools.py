"""Agent file tools and a disposable Docker execution boundary."""
from __future__ import annotations
import asyncio
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

ROOT = Path(__file__).resolve().parent
MAX_FILE = 256_000
MAX_WORKSPACE = 50_000_000


class ToolUnavailable(RuntimeError):
    pass


class Workspace:
    def __init__(self, ident, root=ROOT / 'data/workspaces'):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', ident):
            raise ValueError('invalid workspace id')
        self.root = (Path(root) / ident).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, name, *, existing=False):
        if not isinstance(name, str) or not name or len(name) > 500 or '\x00' in name:
            raise ValueError('invalid file path')
        path = self.root / name
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('file path must stay inside the task workspace')
        for parent in [path, *path.parents]:
            if parent == self.root:
                break
            if parent.is_symlink():
                raise ValueError('symlinks are not supported')
        path = path.resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError('invalid workspace file')
        if existing and (not path.is_file() or not stat.S_ISREG(path.stat().st_mode)):
            raise ValueError('file does not exist')
        return path

    def files(self):
        result = []
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(directory)/d).is_symlink())
            for name in sorted(names):
                path = Path(directory)/name
                if path.is_symlink() or not path.is_file():
                    continue
                result.append({'path': str(path.relative_to(self.root)), 'bytes': path.stat().st_size})
                if len(result) > 1000:
                    raise ValueError('workspace has too many files')
        return result

    def size(self):
        return sum(item['bytes'] for item in self.files())

    def read(self, path):
        target = self.path(path, existing=True)
        if target.stat().st_size > MAX_FILE:
            raise ValueError('file exceeds the read limit')
        return {'path': path, 'content': target.read_text(encoding='utf-8')}

    def write(self, path, content):
        if not isinstance(content, str) or len(content.encode()) > MAX_FILE:
            raise ValueError('file content must be text no larger than 256 KB')
        if self.size() + len(content.encode()) > MAX_WORKSPACE:
            raise ValueError('workspace size limit exceeded')
        target = self.path(path)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = target.with_name('.write-' + uuid.uuid4().hex)
        try:
            temp.write_text(content, encoding='utf-8'); temp.chmod(0o600); temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
        return {'path': path, 'bytes': len(content.encode()), 'sha256': hashlib.sha256(content.encode()).hexdigest()}

    def manifest(self):
        files = self.files()
        if sum(f['bytes'] for f in files) > MAX_WORKSPACE:
            raise ValueError('workspace size limit exceeded')
        for item in files:
            path = self.path(item['path'], existing=True)
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    digest.update(chunk)
            item['sha256'] = digest.hexdigest()
        return files

    def write_many(self, files):
        if not isinstance(files, list) or not 1 <= len(files) <= 8:
            raise ValueError('write_files needs one to eight files')
        targets = set()
        for file in files:
            if not isinstance(file, dict) or set(file) != {'path', 'content'}:
                raise ValueError('Each file needs only path and content')
            target = self.path(file['path'])
            if target in targets:
                raise ValueError('Duplicate file in batch')
            targets.add(target)
            if not isinstance(file['content'], str) or len(file['content'].encode()) > MAX_FILE:
                raise ValueError('File content exceeds the write limit')
        if self.size() + sum(len(file['content'].encode()) for file in files) > MAX_WORKSPACE:
            raise ValueError('Workspace size limit exceeded')
        return {'files': [self.write(file['path'], file['content']) for file in files]}


class DockerSandbox:
    def __init__(self, image=None, timeout=60):
        self.image = image or os.environ.get('SUPERCRAFTOS_SANDBOX_IMAGE', 'python:3.12-slim')
        self.timeout = timeout

    async def cleanup(self, name):
        if not re.fullmatch(r'supercraft-job-[0-9a-f]{32}', name):
            raise ValueError('invalid sandbox identity')
        if not shutil.which('docker'):
            raise ToolUnavailable('Docker is required to reconcile the previous sandbox')
        process = await asyncio.create_subprocess_exec('docker', 'rm', '-f', name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 10)
        except asyncio.TimeoutError:
            process.kill(); await process.wait()
            raise ToolUnavailable('Docker did not stop the sandbox; retry after restoring the daemon')
        if process.returncode and b'No such container' not in output:
            raise ToolUnavailable('Docker could not reconcile the previous sandbox')

    async def run(self, workspace, command, *, name=None):
        if not isinstance(command, str) or not 1 <= len(command) <= 8000:
            raise ValueError('command must contain 1 to 8000 characters')
        if not shutil.which('docker'):
            raise ToolUnavailable('Docker is required for command execution; install/start it and pull the sandbox image')
        uid, gid = os.getuid(), os.getgid()
        if uid == 0:
            uid = gid = 65534
            for directory, dirs, files in os.walk(workspace.root, followlinks=False):
                os.chown(directory, uid, gid)
                for filename in files:
                    path = Path(directory)/filename
                    if not path.is_symlink():
                        os.chown(path, uid, gid)
        name = name or 'supercraft-job-' + uuid.uuid4().hex
        if not re.fullmatch(r'supercraft-job-[0-9a-f]{32}', name):
            raise ValueError('invalid sandbox identity')
        argv = ['docker', 'run', '--rm', '--init', '--name', name, '--pull=never', '--network=none',
                '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--pids-limit=64', '--memory=512m', '--memory-swap=512m', '--cpus=1',
                '--log-driver=none', '--tmpfs=/tmp:rw,nosuid,nodev,size=64m',
                '--user', f'{uid}:{gid}', '--mount', f'type=bind,source={workspace.root},target=/workspace',
                '--mount', f'type=bind,source={workspace.root},target=/task',
                '--workdir=/workspace', '-e', 'PYTHONDONTWRITEBYTECODE=1',
                self.image, 'timeout', '--signal=KILL', str(self.timeout+5), '/bin/sh', '-lc', command]
        process = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output = bytearray()
        async def collect():
            while chunk := await process.stdout.read(4096):
                output.extend(chunk)
                if len(output) > 64000:
                    raise ValueError('command output limit exceeded')
            return await process.wait()
        async def monitor():
            while True:
                await asyncio.sleep(.5)
                if workspace.size() > MAX_WORKSPACE:
                    raise ValueError('workspace size limit exceeded')
        collector, monitor_task = asyncio.create_task(collect()), asyncio.create_task(monitor())
        try:
            done, _ = await asyncio.wait([collector, monitor_task], timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED)
            if not done:
                return {'exit_code': 124, 'output': output.decode(errors='replace'), 'timed_out': True}
            for task in done:
                task.result()
            code = collector.result()
            if code == 125:
                raise ToolUnavailable('Docker could not start the configured sandbox; check daemon, image and permissions')
            return {'exit_code': code, 'output': output.decode(errors='replace'), 'timed_out': False}
        finally:
            collector.cancel(); monitor_task.cancel()
            # Kill the container as well as the Docker client on cancellation or timeout.
            async def cleanup():
                try:
                    await self.cleanup(name)
                finally:
                    if process.returncode is None:
                        process.kill()
                    await process.wait()
                    await asyncio.gather(collector, monitor_task, return_exceptions=True)
            cleaning = asyncio.create_task(cleanup())
            cancelled = False
            while not cleaning.done():
                try:
                    await asyncio.shield(cleaning)
                except asyncio.CancelledError:
                    cancelled = True
            cleaning.result()
            if cancelled:
                raise asyncio.CancelledError
