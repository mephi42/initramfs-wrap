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
initramfs-wrap -a armhf -o armhf.cpio.gz
qemu-system-arm -M virt -m 256 -kernel $(fetch-vmlinux armhf) -initrd armhf.cpio.gz -nographic
```

* [arm64](https://wiki.debian.org/Arm64Port)

```
initramfs-wrap -a arm64 -o arm64.cpio
xz -9 --check=crc32 arm64.cpio
qemu-system-aarch64 -M virt -cpu cortex-a57 -m 256 -kernel $(fetch-vmlinux arm64) -initrd arm64.cpio.xz -nographic -append 'cma=4M'
```

* [mips](https://wiki.debian.org/MIPSPort)

```
initramfs-wrap -a mips -o mips.cpio.gz
qemu-system-mips -M malta -m 256 -kernel $(fetch-vmlinux mips) -initrd mips.cpio.gz -nographic
```

* [s390x](https://www.debian.org/ports/s390/)

```
initramfs-wrap -a s390x -o s390x.cpio.gz
qemu-system-s390x -m 256 -kernel $(fetch-vmlinux s390x) -initrd s390x.cpio.gz -nographic
```

* [ppc64el](https://wiki.debian.org/ppc64el)

```
initramfs-wrap -a ppc64el -o ppc64el.cpio.gz
qemu-system-ppc64le -m 768 -kernel $(fetch-vmlinux ppc64el) -initrd ppc64el.cpio.gz -nographic -vga none
```

* [amd64](https://www.debian.org/ports/amd64/)

```
initramfs-wrap -a amd64 -o amd64.cpio.gz
qemu-system-x86_64 -m 256 -kernel $(fetch-vmlinux amd64) -initrd amd64.cpio.gz -nographic -append 'console=ttyS0'
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
