# apt-backup

## Why we need this? (or problem description)

While RHEL provides an easy way to undo software installation (https://access.redhat.com/solutions/64069), Ubuntu distributions don't provide that facility out of the box. While it is possible to parse the dpkg.log and apt/history.log and find out exactly what packages were installed/updated/remove, there is one other challenge with backing off an installation. *Ubuntu repositories by default only contain the base version and the latest version of a package.* That means that you would not be able to reinstall an intermediary version, if that version was the one that was upgraded. To illustrate with an example, one of my machines have this package:

```
pchiquit@csdudg-sectest:~$ dpkg --list | grep libsss-sudo
ii  libsss-sudo                       1.13.4-1ubuntu1.1                 amd64        Communicator library for sudo
```
If we upgrade this package to the latest version, we will not be able to restore the previously installed version as this is an intermediary version:
```
pchiquit@csdudg-sectest:~$ apt-cache policy libsss-sudo
libsss-sudo:
  Installed: 1.13.4-1ubuntu1.1
  Candidate: 1.13.4-1ubuntu1.2
  Version table:
     1.13.4-1ubuntu1.2 500              <<<< latest version
        500 http://mirrors.service.networklayer.com/ubuntu xenial-updates/main amd64 Packages
 *** 1.13.4-1ubuntu1.1 100              <<<< installed version
        100 /var/lib/dpkg/status
     1.13.4-1ubuntu1 500                <<< latest version
        500 http://mirrors.service.networklayer.com/ubuntu xenial/main amd64 Packages
```
If we upgraded this package we would not be able to undo the install:
```
pchiquit@csdudg-sectest:~$ sudo apt-get install libsss-sudo
Reading package lists... Done
Building dependency tree       
Reading state information... Done
The following packages will be upgraded:
  libsss-sudo
1 upgraded, 0 newly installed, 0 to remove and 27 not upgraded.
Need to get 0 B/13.1 kB of archives.
After this operation, 1,024 B of additional disk space will be used.
(Reading database ... 119296 files and directories currently installed.)
Preparing to unpack .../libsss-sudo_1.13.4-1ubuntu1.2_amd64.deb ...
Unpacking libsss-sudo (1.13.4-1ubuntu1.2) over (1.13.4-1ubuntu1.1) ...
Setting up libsss-sudo (1.13.4-1ubuntu1.2) ...
Checking NSS setup...
Processing triggers for libc-bin (2.23-0ubuntu7) ...
pchiquit@csdudg-sectest:~$ sudo apt-get install libsss-sudo=1.13.4-1ubuntu1.1
Reading package lists... Done
Building dependency tree       
Reading state information... Done
E: Version '1.13.4-1ubuntu1.1' for 'libsss-sudo' was not found
```

## The Solution
Thanks to [Dylan Taylor](mailto:dylantaylor@us.ibm.com) research, we found a package called `dpkg-repack` that has the capability of creating a `.deb` package out of an installed package. The idea of the script is to run the `apt-get` command in simulation mode to collect all packages that will be installed/removed/upgraded. With that information the script will backup all packages that will be removed and upgraded, so you are able to reinstall them back if for some reason you need to undo the installation.

Notice that `dpkg-repack` comes with an warning:
```
BUGS
       There is a tricky situation that can occur if you dpkg-repack a package
       that  has modified conffiles. The modified conffiles are packed up. Now
       if you install the package, dpkg(1) does not realize that the conffiles
       in  it  are  modified.  So if you later upgrade to a new version of the
       package, dpkg(1) will believe that the old (repacked) package has older
       conffiles than the new version, and will silently replace the conffiles
       with those in the package you are upgrading to.

       While dpkg-repack can be run under fakeroot(1) and will  work  most  of
       the  time,  fakeroot -u must be used if any of the files to be repacked
       are owned by non-root users. Otherwise the package will have them owned
       by root.  dpkg-repack will warn if you run it under fakeroot(1) without
       the -u flag.
```
So special care should be taken with package that contain customized config files, as they may be overwritten by future versions.

##Usage

The script usage and options are:
```
usage: apt-backup.py [-h] [-v] [-a APTGETOPTIONS] [-d DPKGDEST] [-n]
                     operation [package [package ...]]

Backs up the packages that will be modified by an package install

positional arguments:
  operation         apt-get operation
  package           List of packages

optional arguments:
  -h, --help        show this help message and exit
  -v                Verbose mode
  -a APTGETOPTIONS  LONG apt-get options (options separated by comma without
                    dashes)
  -d DPKGDEST       Directory where dpkg packages will be saved. Default
                    /var/tmp
  -n                Do not run all the dpkg-repack commands (Default: true)
```
The scripts supports any `apt-get` operations that accepts the `--simulate` option. Notice that any additional `apt-get` options can be passed using the `-a` option. The options should be long format and without the dashes and separated by `,`. So for example, if you want to pass the options `--ignore-missing` and `--only-upgrade` you would use `ignore-missing,only-upgrade`.

If a temp directory is not specified the packages and scripts will be saved to `/var/tmp` in a directory that will start with 
`apt-backup`. It will contain a subdirectory called `packages` and the scripts `dpkg-repack.sh` and `undo.sh`. By default (unless `-n` is specified) the script `dpkg-repack.sh` will be automatically executed to save the packages that needs to be saved. If you need to undo a package installation/upgrade/removal, you just need to run the `undo.sh` script.

Notice that the temporary directory is not automatically deleted, so this will have to be done manually.

## Examples:

###Save all packages that will be upgraded in verbose mode
```
pchiquit@csdudg-sectest:~$ sudo ./apt-backup.py -v upgrade
Verbose mode is True
aptgetOptions are 
dpkgDest is 
runRepack is True
aptgetOper is upgrade
packagesToInstall are 
Checking prerequisites
Running /usr/bin/apt-get --simulate upgrade
The command apt-get upgrade  will install/upgrade/remove:
   apt-get: upgrade init-system-helpers from 1.29ubuntu3 to 1.29ubuntu4
   apt-get: upgrade init from 1.29ubuntu3 to 1.29ubuntu4
   apt-get: upgrade snapd from 2.22.3 to 2.22.6
   apt-get: upgrade ubuntu-core-launcher from 2.22.3 to 2.22.6
   apt-get: upgrade snap-confine from 2.22.3 to 2.22.6
   apt-get: upgrade resolvconf from 1.78ubuntu2 to 1.78ubuntu4
   apt-get: upgrade grub-common from 2.02~beta2-36ubuntu3.7 to 2.02~beta2-36ubuntu3.8
   apt-get: upgrade libxenstore3.0 from 4.6.0-1ubuntu4.3 to 4.6.5-0ubuntu1
   apt-get: upgrade mdadm from 3.3-2ubuntu7.1 to 3.3-2ubuntu7.2
   apt-get: upgrade xenstore-utils from 4.6.0-1ubuntu4.3 to 4.6.5-0ubuntu1
   apt-get: upgrade cloud-init from 0.7.9-0ubuntu1~16.04.2 to 0.7.9-48-g1c795b9-0ubuntu1~16.04.1
   apt-get: upgrade sssd-ad from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-proxy from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-krb5 from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-ipa from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-ad-common from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-tools from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-common from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-krb5-common from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade sssd-ldap from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade libsss-idmap0 from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade python-sss from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade libsss-nss-idmap0 from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade libipa-hbac0 from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade libnss-sss from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
   apt-get: upgrade libpam-sss from 1.13.4-1ubuntu1.1 to 1.13.4-1ubuntu1.2
Creating dpkg-repack commands at /var/tmp/apt-backupy_v0zy50/dpkg-repack.sh
   Repack: init-system-helpers
   Repack: init
   Repack: snapd
   Repack: ubuntu-core-launcher
   Repack: snap-confine
   Repack: resolvconf
   Repack: grub-common
   Repack: libxenstore3.0
   Repack: mdadm
   Repack: xenstore-utils
   Repack: cloud-init
   Repack: sssd-ad
   Repack: sssd-proxy
   Repack: sssd-krb5
   Repack: sssd-ipa
   Repack: sssd-ad-common
   Repack: sssd-tools
   Repack: sssd-common
   Repack: sssd-krb5-common
   Repack: sssd
   Repack: sssd-ldap
   Repack: libsss-idmap0
   Repack: python-sss
   Repack: libsss-nss-idmap0
   Repack: libipa-hbac0
   Repack: libnss-sss
   Repack: libpam-sss
dpkg-repack command script created at /var/tmp/apt-backupy_v0zy50/dpkg-repack.sh
Creating undo commands at /var/tmp/dpkg-repacky_v0zy50/undo.sh
   Undo: dpkg --install  *
Undo command script created at /var/tmp/apt-backupy_v0zy50/undo.sh
Running /var/tmp/dpkg-repacky_v0zy50/dpkg-repack.sh
dpkg-deb: building package 'init-system-helpers' in './init-system-helpers_1.29ubuntu3_all.deb'.
dpkg-deb: building package 'init' in './init_1.29ubuntu3_amd64.deb'.
dpkg-deb: building package 'snapd' in './snapd_2.22.3_amd64.deb'.
dpkg-deb: building package 'ubuntu-core-launcher' in './ubuntu-core-launcher_2.22.3_amd64.deb'.
dpkg-deb: building package 'snap-confine' in './snap-confine_2.22.3_amd64.deb'.
dpkg-deb: building package 'resolvconf' in './resolvconf_1.78ubuntu2_all.deb'.
dpkg-deb: building package 'grub-common' in './grub-common_2.02~beta2-36ubuntu3.7_amd64.deb'.
dpkg-deb: building package 'libxenstore3.0' in './libxenstore3.0_4.6.0-1ubuntu4.3_amd64.deb'.
dpkg-deb: building package 'mdadm' in './mdadm_3.3-2ubuntu7.1_amd64.deb'.
dpkg-deb: building package 'xenstore-utils' in './xenstore-utils_4.6.0-1ubuntu4.3_amd64.deb'.
dpkg-repack: Skipping obsolete conffile /etc/profile.d/Z99-cloudinit-warnings.sh
dpkg-deb: building package 'cloud-init' in './cloud-init_0.7.9-0ubuntu1~16.04.2_all.deb'.
dpkg-deb: building package 'sssd-ad' in './sssd-ad_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-proxy' in './sssd-proxy_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-krb5' in './sssd-krb5_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-ipa' in './sssd-ipa_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-ad-common' in './sssd-ad-common_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-tools' in './sssd-tools_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-common' in './sssd-common_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-krb5-common' in './sssd-krb5-common_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd' in './sssd_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'sssd-ldap' in './sssd-ldap_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'libsss-idmap0' in './libsss-idmap0_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'python-sss' in './python-sss_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'libsss-nss-idmap0' in './libsss-nss-idmap0_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'libipa-hbac0' in './libipa-hbac0_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'libnss-sss' in './libnss-sss_1.13.4-1ubuntu1.1_amd64.deb'.
dpkg-deb: building package 'libpam-sss' in './libpam-sss_1.13.4-1ubuntu1.1_amd64.deb'.
```




