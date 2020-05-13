#!/usr/bin/env python3
from collections import defaultdict
import os
import re
import signal
import sys
import tempfile
import unittest

import pexpect


class TestInitramfsWrap(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.basedir = os.path.dirname(__file__)
        self.arches = defaultdict(list)
        state = 'find-arches'
        arch = None
        with open(os.path.join(self.basedir, 'README.md')) as fp:
            for line in fp:
                if state == 'find-arches':
                    if line == '# Architectures\n':
                        state = 'find-arch'
                elif state == 'find-arch':
                    if line.startswith('#'):
                        break
                    elif line.startswith('* ['):
                        arch = line[3:line.index(']')]
                        state = 'find-commands'
                elif state == 'find-commands':
                    if line == '```\n':
                        state = 'read-commands'
                elif state == 'read-commands':
                    if line == '```\n':
                        state = 'find-arch'
                        arch = None
                    else:
                        self.arches[arch].append(line.strip())

    def _test_arch(self, arch):
        env_path = self.basedir + os.pathsep + os.environ['PATH']
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, 'cache')
            commands = self.arches[arch]
            for i, command in enumerate(commands):
                child = pexpect.spawn(
                    'sh',
                    args=['-c', command],
                    timeout=300,
                    logfile=sys.stdout.buffer,
                    cwd=tmpdir,
                    env={
                        **os.environ,
                        'PATH': env_path,
                        'INITRAMFS_WRAP_CACHE_DIR': cache_dir,
                    },
                )
                if i == len(commands) - 1:
                    prompt = 'root@(none):/#'
                    child.expect_exact(prompt)
                    child.sendline('strace /bin/true')
                    child.expect_exact('+++ exited with 0 +++')
                    child.expect_exact(prompt)
                    if arch != 's390x':
                        # All programs crash under gdb on s390x:
                        # Program received signal SIGSEGV, Segmentation fault.
                        # 0x000003fffdf906d2 in ?? () from /lib/ld64.so.1
                        child.sendline('gdb -batch -ex r /bin/true')
                        child.expect(re.compile(
                            br'\[Inferior 1 \(process \d+\) exited normally\]'))
                        child.expect_exact(prompt)
                    child.kill(signal.SIGHUP)
                child.expect(pexpect.EOF)
                child.close()
                if os.WIFEXITED(child.status):
                    self.assertEqual(0, os.WEXITSTATUS(child.status))
                elif os.WIFSIGNALED(child.status):
                    self.assertEqual(signal.SIGHUP, os.WTERMSIG(child.status))
                else:
                    self.fail()

    def test_armhf(self):
        self._test_arch('armhf')

    def test_arm64(self):
        self._test_arch('arm64')

    def test_mips(self):
        self._test_arch('mips')

    def test_s390x(self):
        self._test_arch('s390x')

    def test_ppc64el(self):
        self._test_arch('ppc64el')

    def test_amd64(self):
        self._test_arch('amd64')


if __name__ == '__main__':
    unittest.main()
