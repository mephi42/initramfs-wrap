from errno import EINVAL
from glob import glob
import os
import subprocess
from typing import List, Set, Optional
from urllib.request import urlretrieve

DEB2GNU = {
    "amd64": "x86_64",
    "armhf": "arm",
    "arm64": "aarch64",
}
DEB2QEMU = {
    "amd64": "x86_64",
    "armhf": "arm",
    "arm64": "aarch64",
    "ppc64el": "ppc64le",
}
# Queryable via /sys/class/tty/console/active, but it's better to support
# kernels without CONFIG_SYSFS.
DEB2CONSOLE = {
    "amd64": "/dev/ttyS0",
    "armhf": "/dev/ttyAMA0",
    "arm64": "/dev/ttyAMA0",
    "mips": "/dev/ttyS0",
    "ppc64el": "/dev/hvc0",
    "s390x": "/dev/ttysclp0",
}
DEB2KERNEL = {
    "amd64": "http://ftp.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/debian-installer/amd64/linux",  # noqa: E501
    "armhf": "http://ftp.debian.org/debian/dists/stable/main/installer-armhf/current/images/netboot/vmlinuz",  # noqa: E501
    "arm64": "http://ftp.debian.org/debian/dists/stable/main/installer-arm64/current/images/netboot/debian-installer/arm64/linux",  # noqa: E501
    "mips": "http://ftp.debian.org/debian/dists/stable/main/installer-mips/current/images/malta/netboot/vmlinux-4.19.0-16-4kc-malta",  # noqa: E501
    "ppc64el": "http://ftp.debian.org/debian/dists/stable/main/installer-ppc64el/current/images/netboot/debian-installer/ppc64el/vmlinux",  # noqa: E501
    "s390x": "http://ftp.debian.org/debian/dists/stable/main/installer-s390x/current/images/generic/kernel.debian",  # noqa: E501
}


def default_cache_dir():
    return os.getenv(
        "INITRAMFS_WRAP_CACHE_DIR",
        os.path.expanduser("~/.cache/initramfs-wrap"),
    )


def fetch_vmlinux(arch, cache_dir):
    path = os.path.join(cache_dir, f"vmlinux-{arch}")
    if not os.path.exists(path):
        urlretrieve(DEB2KERNEL[arch], path)
    return path


def debootstrap_stage1(
    chroot: str,
    arch: str,
    suite: str,
    cache_dir: str,
    extra_packages: Optional[List[str]],
):
    cache = os.path.join(cache_dir, "debootstrap")
    os.makedirs(cache, exist_ok=True)
    if extra_packages is None:
        extra_packages = []
    include_packages = extra_packages + [
        "gdb",
        "gdbserver",
        "iproute2",
        "less",
        "nano",
        "procps",
        "socat",
        "strace",
        "tmux",
    ]
    include_packages = ",".join(include_packages)
    exclude_packages = ",".join(
        (
            "binutils",
            "binutils-common",
            f"binutils-{DEB2GNU.get(arch, arch)}-linux-gnu",
            "iptables",
            "libbinutils",
            "login",
            "rsyslog",
            "tzdata",
        )
    )
    subprocess.check_call(
        [
            "fakeroot",
            "-s",
            os.path.join(chroot, "fakeroot-state"),
            "debootstrap",
            f"--cache-dir={cache}",
            "--foreign",
            f"--arch={arch}",
            "--variant=minbase",
            f"--include={include_packages}",
            f"--exclude={exclude_packages}",
            suite,
            chroot,
        ]
    )


def host_fakeroot_command(chroot, args):
    result = [
        "fakeroot",
        "-i",
        os.path.join(chroot, "fakeroot-state"),
        "-s",
        os.path.join(chroot, "fakeroot-state"),
    ]
    result.extend(args)
    return result


def split_parts(path: str, parts: List[str]):
    while path not in ("", "/"):
        path, part = os.path.split(path)
        parts.append(part)
    return path


def add_to_initramfs(chroot: str, path: str, results: Set[str]):
    assert os.path.isabs(path)
    parts = []
    path = split_parts(path, parts)
    while len(parts) > 0:
        print((path, parts))
        part = parts.pop()
        if part == ".":
            continue
        if part == "..":
            path = os.path.dirname(path)
            continue
        path = os.path.join(path, part)
        results.add(path)
        try:
            next_path = os.readlink(f"{chroot}{path}")
        except OSError as ex:
            if ex.errno == EINVAL:
                continue
            raise
        if os.path.isabs(next_path):
            path = split_parts(next_path, parts)
        else:
            split_parts(next_path, parts)
            path = os.path.dirname(path)


def find_in_lib_paths(chroot: str, lib_paths: List[str], path: str):
    for libpath in lib_paths:
        lib = os.path.join(f"{chroot}{libpath}", path)
        if os.path.exists(lib):
            return os.path.join(libpath, path)
    raise RuntimeError(f"Could not find {path} in {os.pathsep.join(lib_paths)}")


def iter_dt_needed(chroot: str, path: str, lib_paths: List[str]):
    from elftools.elf.elffile import ELFFile, InterpSegment
    from elftools.elf.dynamic import DynamicSegment

    assert os.path.isabs(path)
    with open(f"{chroot}{path}", "rb") as fp:
        elf = ELFFile(fp)
        for segment in elf.iter_segments():
            if isinstance(segment, InterpSegment):
                yield segment.get_interp_name()
            if isinstance(segment, DynamicSegment):
                for tag in segment.iter_tags("DT_NEEDED"):
                    yield find_in_lib_paths(chroot, lib_paths, tag.needed)


def __add_elf_to_initramfs(
    chroot: str, path: str, lib_paths: List[str], results: Set[str]
):
    add_to_initramfs(chroot, path, results)
    for needed_path in iter_dt_needed(chroot, path, lib_paths):
        __add_elf_to_initramfs(chroot, needed_path, lib_paths, results)


def parse_ld_so_conf(chroot: str, results: List[str], ld_so_conf: Optional[str] = None):
    # See elf/ldconfig.c: parse_conf_include() and posix/glob.c.
    if ld_so_conf is None:
        ld_so_conf = f"{chroot}/etc/ld.so.conf"
    with open(ld_so_conf) as fp:
        for line in fp:
            idx = line.find("#")
            if idx != -1:
                line = line[:idx]
            line = line.strip()
            if line == "":
                continue
            if len(line) >= 8 and line.startswith("include") and line[7].isspace():
                for path in sorted(glob(f"{chroot}{line[8:]}")):
                    parse_ld_so_conf(chroot, results, path)
            else:
                results.append(line)


def add_elf_to_initramfs(chroot: str, path: str, results: Set[str]):
    lib_paths = []
    parse_ld_so_conf(chroot, lib_paths)
    print(lib_paths)
    __add_elf_to_initramfs(chroot, path, lib_paths, results)


def get_chroot_path(cache_dir, arch, suite):
    return os.path.join(cache_dir, f"{arch}-{suite}.tar.gz")


def get_initramfs_path(cache_dir, arch, suite):
    return os.path.join(cache_dir, f"{arch}-{suite}-mini.cpio")


def create_initramfs(initramfs, chroot):
    paths = {"/"}
    for path in (
        "/bin/base64",
        "/bin/sh",
        "/bin/tar",
    ):
        add_elf_to_initramfs(chroot, path, paths)
    with open(initramfs, "wb") as fp:
        p = subprocess.Popen(
            host_fakeroot_command(chroot, ["cpio", "-o", "-H", "newc", "-R", "+0:+0"]),
            stdin=subprocess.PIPE,
            stdout=fp,
            cwd=chroot,
        )
        try:
            for path in sorted(paths):
                p.stdin.write(f".{path}\n".encode())
        finally:
            p.stdin.close()
            returncode = p.wait()
            if returncode != 0:
                raise subprocess.CalledProcessError(returncode, p.args)


def add_cache_dir_parser(parser):
    parser.add_argument(
        "--cache-dir",
        help="Cache directory",
        default=default_cache_dir(),
    )
