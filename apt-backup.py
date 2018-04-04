#!/usr/bin/env python3

import sys
import logging
import argparse
import os
import errno
import re
import stat
import subprocess


# global vars
verbose = False
packagesToInstall = ""
aptgetOptions = ""
dpkgDest = ""
runRepack = True
aptgetOper = ""

#
# Process parameters
#


def getParms(argv):
    global verbose
    global packagesToInstall
    global aptgetOptions
    global dpkgDest
    global runRepack
    global aptgetOper

    parser = argparse.ArgumentParser(description='Backs up the packages that \
    will be modified by an apt-get install')
    parser.add_argument('-v', dest='verbose', action='store_true',
                        default=False, help='Verbose mode')
    parser.add_argument('-a', dest='aptgetOptions', default="", help='LONG \
    apt-get options (options separated by comma without dashes)')
    parser.add_argument('-d', dest='dpkgDest', default="", help='Directory where\
     dpkg packages will be saved. Default /var/tmp')
    parser.add_argument('-n', dest='runRepack', action='store_false',
                        default=True, help='Do not run all the dpkg-repack \
                commands (Default: true)')
    parser.add_argument('aptgetOper', metavar='operation',
                        help='apt-get operation')
    parser.add_argument('packages', metavar='package', nargs='*',
                        help='List of packages')

    args = parser.parse_args()
    verbose = args.verbose
    aptgetOptions = args.aptgetOptions
    dpkgDest = args.dpkgDest
    aptgetOper = args.aptgetOper
    runRepack = args.runRepack

    # check if we have a list of packages if it is not an upgrade
    # check that we have an operation.
    if (("upgrade" not in aptgetOper) and len(args.packages) == 0) or not aptgetOper:
        parser.print_help()
        exit
    else:
        packagesToInstall = args.packages
    print ("Verbose mode is " + str(verbose) + "\n" if verbose else '', end='')
    print ("aptgetOptions are " + aptgetOptions + "\n" if verbose else '', end='')
    print ("dpkgDest is " + dpkgDest + "\n" if verbose else '', end='')
    print ("runRepack is " + str(runRepack) + "\n" if verbose else '', end='')
    print ("aptgetOper is " + aptgetOper + "\n" if verbose else '', end='')
    print ("packagesToInstall are " + ' '.join(packagesToInstall) + "\n" if verbose else '', end='')

# Function to make sure a commands is available


def which(program):
    import os

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

#
# checks
# Do some sanity checks


def checks():
    global verbose
    global dpkgDest
    import errno

    # check OS version.
    print ("Checking prerequisites\n" if verbose else '', end='')
    try:
        import platform
        linuxDist = platform.linux_distribution()
        if not (linuxDist[0] == "Ubuntu" and (linuxDist[1] == "16.04" or linuxDist[1] == "14.04")):
            exit("Distribution " + linuxDist[0] + " " + linuxDist[1] + " is not supported")
    except EnvironmentError:
        sys.stderr.write("Got exception using 'platform'. Exception follows\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()

    # make sure we have python.apt installed
    try:
        import apt
    except ImportError:
        exit("Missing python.apt package")

    # make sure we have the required packages
    cache = apt.Cache()
    for package in ['dpkg-repack']:
        if not cache[package].is_installed:
            exit("Missing the package "+package)

    # make sure required commands are available
    for command in ['dpkg-repack']:
        if which(command) is None:
            exit("Command " + command + " not available. Please install it")
    # make sure we are root
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

#   # create temp dir to hold packages
    if not dpkgDest:
        import datetime
        dpkgDest = "/var/tmp/apt-backup."+datetime.datetime.now().isoformat()

    # if it exists, need to make sure it is a directorys = getPackag
    if os.path.exists(dpkgDest):
        if not os.path.isdir(dpkgDest):
            exit(dpkgdest + " is not a directory")
    else:
        # create the directory
        try:
            os.makedirs(dpkgDest)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
    # create subdir for packages
    try:
        os.makedirs(dpkgDest + "/packages")
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    # link dpkg-repack-latest to temp dir
    try:
        os.symlink(dpkgDest, os.path.dirname(dpkgDest) + "/apt-backup-latest")
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            os.remove(os.path.dirname(dpkgDest) + "/apt-backup-latest")
            try:
                os.symlink(dpkgDest, os.path.dirname(dpkgDest) + "/apt-backup-latest")
            except OSError as exception:
                raise

# getPackageList
# get the list of packages that will be upgraded, deleted and installed


def getPackageList(aptgetOptions, aptgetOper, packages):

    global verbose
    operations = []

    # run apt-get in simulate to get all operations that will be done to packages
    # assemble command and parameters
    command = ['/usr/bin/apt-get', '--simulate']
    # add options
    if aptgetOptions:
        for option in aptgetOptions.split(','):
            command.append("--"+option)
    # add operation
    command.append(aptgetOper)
    # and packages
    command.extend(packages)

    print ('Running ' + ' '.join(command) + "\n" if verbose else '', end='')

    # run it
    try:
        out = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
    except subprocess.CalledProcessError as err:
        exit('apt-get failed with error:' + err.output)
    else:
        if verbose:
            print ("The command apt-get " + aptgetOper + " " + ' '.join(packagesToInstall) +
                   " will install/upgrade/remove:")
        # for each line pick the ones that tell about the operations.
        outLines = None
        regex = re.compile('(^Remv|^Inst)')
        for line in out.split("\n"):
            if re.match(regex, line):
                currVersion = None
                newVersion = None
                arch = None

                # now it gets trick. If the package is already installed it looks like this (current version is third element:
                #     Inst libsss-sudo [1.13.4-1ubuntu1.1] (1.13.4-1ubuntu1.2 Ubuntu:16.04/xenial-updates [amd64])
                # if is a new install it looks like this (no old version):
                #     Inst keepass2 (2.32+dfsg-1 Ubuntu:16.04/xenial [all])
                # Remove looks like:
                #     Remv libsss-sudo [1.13.4-1ubuntu1.1]
                #
                splitLine = line.split(" ")
                oper = splitLine[0]
                package = splitLine[1]
                third = splitLine[2]

                if oper == "Inst":
                    if third.startswith('['):

                        # We have an old version of the package
                        currVersion = third[1:third.find("]")]
                    # now looks for the section between parentheses
                    parLine = line[line.index('(')+1:line.index(')')]
                    # get the first element
                    newVersion = parLine.split(' ')[0]
                    # get the last element
                    arch = parLine.split(' ')[-1]
                elif oper == "Remv":
                    currVersion = third[1:third.find("]")]
                operations.append({"pkgName": package, "operation": oper,
                                   "currentVersion": currVersion,
                                   'newVersion': newVersion,
                                   'arch': arch.strip('[])')})
                if verbose:
                    if currVersion:
                        print ("   apt-get: upgrade " + package + " from " +
                               currVersion + " to "+newVersion)
                    else:
                        print ("   apt-get: " + oper + " " + package +
                               "at version " + newVersion)

        return operations
#
# genDpkgRepackCommands
# generate the commands to repack all the packages that will be changed.
#


def genDpkgRepackCommands(operations, dpkgDest):
    # file that will hold the commandapt
    fileName = dpkgDest+"/dpkg-repack.sh"
    print ('Creating dpkg-repack commands at ' + fileName + "\n" if verbose else '', end='')

    file = open(fileName, "w")
    file.write("#!/bin/bash\n")
    file.write("cd " + dpkgDest + "/packages\n")

    # for each operation that apt-get will execute, we will decide if we need to backup the package.
    # We need to backup upgrades and package removals
    for operation in operations:
        # if the package will be removed we need to back it up.
        # if the package will be upgraded we need to back it up. We can ignore installation of new package.
        if operation['operation'] == "Remv" or (operation['operation'] == "Inst" and operation['currentVersion']):
            file.write('/usr/bin/dpkg-repack '+operation['pkgName']+"\n")
            print ('   Repack: ' + operation['pkgName'] + "\n" if verbose else '', end='')
    file.close()
    os.chmod(fileName, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP |
             stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    print ("dpkg-repack command script created at "+fileName)
#
# genUndoCommands
# generate the commands to undo the install .
#


def genUndoCommands(operations, dpkgDest):
    # file that will hold the command
    fileName = dpkgDest+"/undo.sh"
    print ('Creating undo commands at ' + fileName + "\n" if verbose else '', end='')

    file = open(fileName, "w")
    file.write("#!/bin/bash\n")
    file.write("cd "+dpkgDest+"/packages\n")
    # install list
    toBeInstalled = []
    toBeRemoved = []
    # for each operation that apt-get will execute, we will decide if we need to install  the package.
    # We need to undo  upgrades and package removals
    for operation in operations:
        # if the package will be removed we need to install it
        if operation['operation'] == "Remv":
            toBeInstalled.append(operation['pkgName'] + "_" +
                                 operation['currentVersion'] + "_"+operation['arch']+".deb")
        if operation['operation'] == "Inst":
            # if the package will be upgraded we need to install the old version it up
            if operation['currentVersion']:
                toBeInstalled.append(
                    operation['pkgName'] + "_" + operation['currentVersion'] + "_"+operation['arch']+".deb")
            else:
                toBeRemoved.append(operation['pkgName'])
    # Now process the list of install and removes
    # They need to be one command so dependencies are taken care of.
    if len(toBeInstalled):
        # i couldn't figure out how to recreate the file name, so just install all packages on that directory.
        file.write('/usr/bin/dpkg --install *\n')
        print ('   Undo: dpkg --install  *\n' if verbose else '', end='')
    if len(toBeRemoved):
        file.write('/usr/bin/dpkg --remove ' + ' '.join(toBeRemoved) + "\n")
        print ('   Undo: dpkg --remove  ' + ' '.join(toBeRemoved) + "\n" if verbose else '', end='')
    file.close()
    os.chmod(fileName, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP |
             stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    print ("Undo command script created at "+fileName)


# main
#
# process parameters
getParms(sys.argv[1:])
# check to see if we have all the tools we need
checks()
# get the list of packages that will be upgraded
operations = getPackageList(aptgetOptions, aptgetOper, packagesToInstall)
# generate commands
genDpkgRepackCommands(operations, dpkgDest)
# generate the undo commands
genUndoCommands(operations, dpkgDest)
# run the repack commands
print ("Running " + dpkgDest + "/dpkg-repack.sh\n" if verbose else '', end='')
if runRepack:
    # run it
    try:
        subprocess.call(dpkgDest + "/dpkg-repack.sh")
    except subprocess.CalledProcessError as err:
        exit(dpkgDest+"/dpkg-repack.sh failed with error:", err)
else:
    print ("Warning: this script has not backed up any package. Make sure you run the dpkg-repack script before you upgrade the packages.")
#
