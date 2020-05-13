import os
import subprocess
from typing import Set
from urllib.request import urlretrieve

DEB2GNU = {
    'amd64': 'x86_64',
    'armhf': 'arm',
    'arm64': 'aarch64',
}
DEB2QEMU = {
    'amd64': 'x86_64',
    'armhf': 'arm',
    'arm64': 'aarch64',
    'ppc64el': 'ppc64le',
}
# Queryable via /sys/class/tty/console/active, but it's better to support
# kernels without CONFIG_SYSFS.
DEB2CONSOLE = {
    'amd64': '/dev/ttyS0',
    'armhf': '/dev/ttyAMA0',
    'arm64': '/dev/ttyAMA0',
    'mips': '/dev/ttyS0',
    'ppc64el': '/dev/hvc0',
    's390x': '/dev/ttysclp0',
}
DEB2KERNEL = {
    'amd64': 'http://ftp.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/debian-installer/amd64/linux',  # noqa: E501
    'armhf': 'http://ftp.debian.org/debian/dists/stable/main/installer-armhf/current/images/netboot/vmlinuz',  # noqa: E501
    'arm64': 'http://ftp.debian.org/debian/dists/stable/main/installer-arm64/current/images/netboot/debian-installer/arm64/linux',  # noqa: E501
    'mips': 'http://ftp.debian.org/debian/dists/stable/main/installer-mips/current/images/malta/netboot/vmlinux-4.19.0-9-4kc-malta',  # noqa: E501
    'ppc64el': 'http://ftp.debian.org/debian/dists/stable/main/installer-ppc64el/current/images/netboot/debian-installer/ppc64el/vmlinux',  # noqa: E501
    's390x': 'http://ftp.debian.org/debian/dists/stable/main/installer-s390x/current/images/generic/kernel.debian',  # noqa: E501
}


def default_cache_dir():
    return os.getenv(
        'INITRAMFS_WRAP_CACHE_DIR',
        os.path.expanduser('~/.cache/initramfs-wrap'),
    )


def fetch_vmlinux(arch, cache_dir):
    path = os.path.join(cache_dir, f'vmlinux-{arch}')
    if not os.path.exists(path):
        urlretrieve(DEB2KERNEL[arch], path)
    return path


def debootstrap_stage1(chroot, arch, suite, cache_dir, extra_packages):
    cache = os.path.join(cache_dir, 'debootstrap')
    os.makedirs(cache, exist_ok=True)
    include_packages = extra_packages + [
        'gdb',
        'gdbserver',
        'iproute2',
        'less',
        'nano',
        'procps',
        'socat',
        'strace',
        'tmux',
    ]
    include_packages = ','.join(include_packages)
    exclude_packages = ','.join((
        'binutils',
        'binutils-common',
        f'binutils-{DEB2GNU.get(arch, arch)}-linux-gnu',
        'iptables',
        'libbinutils',
        'login',
        'rsyslog',
        'tzdata',
    ))
    subprocess.check_call([
        'fakeroot',
        '-s', os.path.join(chroot, 'fakeroot-state'),
        'debootstrap',
        f'--cache-dir={cache}',
        '--foreign',
        f'--arch={arch}',
        '--variant=minbase',
        f'--include={include_packages}',
        f'--exclude={exclude_packages}',
        suite,
        chroot,
    ])


def iter_dt_needed(chroot, arch, path):
    from elftools.elf.elffile import ELFFile, InterpSegment
    from elftools.elf.dynamic import DynamicSegment
    libdir = os.path.join(
        chroot, 'lib', f'{DEB2GNU.get(arch, arch)}-linux-gnu')
    with open(os.path.join(chroot, path), 'rb') as fp:
        elf = ELFFile(fp)
        for segment in elf.iter_segments():
            if isinstance(segment, InterpSegment):
                yield segment.get_interp_name()
            if isinstance(segment, DynamicSegment):
                for tag in segment.iter_tags('DT_NEEDED'):
                    needed_path = os.path.join(libdir, tag.needed)
                    if not os.path.exists(needed_path):
                        raise Exception(f'{needed_path} does not exist')
                    yield needed_path


def add_minichroot_files(chroot: str, arch: str, path: str, paths: Set[str]):
    while True:
        if path in paths:
            return
        paths.add(path)
        try:
            next_path = os.readlink(os.path.join(chroot, path))
        except OSError:
            break
        if not os.path.isabs(next_path):
            next_path = os.path.join(os.path.dirname(path), next_path)
        path = next_path
    for needed_path in iter_dt_needed(chroot, arch, path):
        add_minichroot_files(chroot, arch, needed_path, paths)
