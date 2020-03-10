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

The generated `initramfs-dbg.cpio.gz` will have the following structure:

```
├── bin
├── init -> /usr/lib/systemd/systemd
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
$ make -f Makefile.qemu -j$(getconf _NPROCESSORS_ONLN)
$ sudo update-binfmts --disable qemu-$ARCH
$ sudo rm /usr/bin/qemu-$ARCH-static
$ sudo cp qemu-4.1.0/bin/qemu-$ARCH-static /usr/bin/
$ sudo update-binfmts --enable qemu-$ARCH
```

# Cleanup

The intermediate results are cached in `~/.cache/initramfs-wrap`.

# Random advice

* Debugging with GDB requires Ctrl+C to be working, which in some setups might
  kill QEMU. [Here is the fix](https://stackoverflow.com/a/49751144).
* Some scripts in the original initramfs might access `/dev/console` directly,
  bypassing `tmux`. Such scripts need to be adjusted.
* Wrapped initramfs will consume ~256M extra RAM. If the system does not boot,
  try increasing QEMU RAM.

# Links

* [foreign debian bootstrapping without root priviliges with fakeroot,
   fakechroot and qemu user emulation](
https://blog.mister-muffin.de/2011/04/02/foreign-debian-bootstrapping-without-root-priviliges-with-fakeroot,-fakechroot-and-qemu-user-emulation/
)
* [QEMU_LD_PREFIX](
https://git.qemu.org/?p=qemu.git;a=blob;f=linux-user/main.c;h=560d053f7249d046107ae03bb101dd6ad7a69817#l417
)
