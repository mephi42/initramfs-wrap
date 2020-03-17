# initramfs-wrap

This program lets you add debugging tools to an existing initramfs, even if it
is for a foreign architecture.

# Usage

```
$ initramfs-wrap \
        -a arm64 \
        -i initramfs.cpio.gz \
        -o initramfs-dbg.cpio.gz
```

The generated `initramfs-dbg.cpio.gz` will have roughly the following structure:

```
├── bin
├── init
└── orig
```

The contents of the original `initramfs.cpio.gz` will be placed under `orig`.
After booting into a shell, you can start using the debugging tools, or just do:

```
# exec chroot /orig /init
```

to resume the usual boot sequence.

# Using GDB

It is assumed that the kernel is stripped down as much as possible - in
particular, there might be no networking. This makes debugging interactive
applications challenging, since only one console is available. Fortunately, you
can use `tmux` to run an application in one tab, and GDB in the other:

```
# tmux
(tab1)# chroot /orig /init
^b c
(tab2)# gdb -ex 'set sysroot /orig' -p $(pidof ctftask)
```

# Using strace

Ditto strace:

```
# tmux
(tab1)# strace -f -o strace.out chroot /orig /init
^b c
(tab2)# less +F strace.out
```

# Using valgrind

Running valgrind in chroot is problematic. Still, some degree of isolation can
be achieved using environment variables:

```
# valgrind env LD_LIBRARY_PATH=/orig/lib:/orig/usr/lib /orig/lib/ld.so /orig/ctftask
```

# Prerequisites

* `debootstrap`
* `dpkg`
* `fakechroot`
* `fakeroot`
* `qemu-user-binfmt`
* `qemu-user-static >= 4.1.0`

`qemu-user-static` version `4.1.0` or newer is required for commit
[`f3a8bdc1d5b2`](https://git.qemu.org/?p=qemu.git;a=commit;h=f3a8bdc1d5b2) -
older versions will choke on symlink loops and get stuck with 100% CPU usage.
`4.1.0` is currently not in all distros, so install whatever is there (for
example, my Ubuntu 19.10 has `4.0.0`) and then build and install `4.1.0` on top:

```
make -f Makefile.qemu -j$(getconf _NPROCESSORS_ONLN)
sudo make -f Makefile.qemu install-$ARCH
```

# Cleanup

The intermediate results are cached in `~/.cache/initramfs-wrap`.

# Architectures

* [armhf](https://wiki.debian.org/ArmHardFloatPort)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-armhf/current/images/netboot/vmlinuz
initramfs-wrap -a armhf -o armhf.cpio.gz
qemu-system-arm -M virt -m 256 -kernel vmlinuz -initrd armhf.cpio.gz -nographic
```

* [arm64](https://wiki.debian.org/Arm64Port)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-arm64/current/images/netboot/debian-installer/arm64/linux
initramfs-wrap -a arm64 -o arm64.cpio
xz -9 --check=crc32 arm64.cpio
qemu-system-aarch64 -M virt -cpu cortex-a57 -m 256 -kernel linux -initrd arm64.cpio.xz -nographic -append 'cma=4M'
```

* [mips](https://wiki.debian.org/MIPSPort)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-mips/current/images/malta/netboot/vmlinux-4.19.0-8-4kc-malta
initramfs-wrap -a mips -o mips.cpio.gz
qemu-system-mips -M malta -m 256 -kernel vmlinux-4.19.0-8-4kc-malta -initrd mips.cpio.gz -nographic
```

* [s390x](https://www.debian.org/ports/s390/)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-s390x/current/images/generic/kernel.debian
initramfs-wrap -a s390x -o s390x.cpio.gz
qemu-system-s390x -m 256 -kernel kernel.debian -initrd s390x.cpio.gz -nographic
```

* [ppc64el](https://wiki.debian.org/ppc64el)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-ppc64el/current/images/netboot/debian-installer/ppc64el/vmlinux
initramfs-wrap -a ppc64el -o ppc64el.cpio.gz
qemu-system-ppc64le -m 768 -kernel vmlinux -initrd ppc64el.cpio.gz -nographic -vga none
```

* [amd64](https://www.debian.org/ports/amd64/)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/debian-installer/amd64/linux
initramfs-wrap -a amd64 -o amd64.cpio.gz
qemu-system-x86_64 -m 256 -kernel linux -initrd amd64.cpio.gz -nographic -append 'console=ttyS0'
```

* [i386](https://www.debian.org/ports/i386/)

```
wget http://ftp.debian.org/debian/dists/stable/main/installer-i386/current/images/netboot/debian-installer/i386/linux
initramfs-wrap -a i386 -o i386.cpio.gz
qemu-system-i386 -m 256 -kernel linux -initrd i386.cpio.gz -nographic -append 'console=ttyS0'
```

# Random advice

* Debugging with GDB requires Ctrl+C to be working, which in some setups might
  kill QEMU. [Here is the fix](https://stackoverflow.com/a/49751144).
* Some scripts in the original initramfs might access `/dev/console` directly,
  bypassing `tmux`. Such scripts need to be adjusted.
* Wrapped initramfs will consume some RAM. A total RAM size of 256MiB should be
  sufficient (since this is the upper bound for MIPS), however, if the system
  does not boot with `Initramfs unpacking failed: write error`, try increasing
  RAM size.

# Links

* [foreign debian bootstrapping without root priviliges with fakeroot,
   fakechroot and qemu user emulation](
https://blog.mister-muffin.de/2011/04/02/foreign-debian-bootstrapping-without-root-priviliges-with-fakeroot,-fakechroot-and-qemu-user-emulation/
)
* [QEMU_LD_PREFIX](
https://git.qemu.org/?p=qemu.git;a=blob;f=linux-user/main.c;h=560d053f7249d046107ae03bb101dd6ad7a69817#l417
)
