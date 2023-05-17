#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Univention GmbH
# Written by Lukas Zumvorde <zumvorde@univention.de>, Jan-Luca Kiok <kiok@univention.de>
# Based on univention_apps module written by Alexander Ulpts <ulpts@univention.de>

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import re
import os
import json
import tempfile
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = '''
---
module: univention_app
version_added: "0.1.3"
short_description: "Installs and removes apps on Univention Corporate Server"
extends_documentation_fragment: ''
description:
  - Allows ansible to control installation, removal and update of ucs-apps
notes:
  - none
requirements: [ ]
author: Stefan Ahrens
options:
  name:
    description:
    - 'The name of the app'
    required: true
  state:
    description:
    - 'The desired state of the app / present, or absent'
    required: true
  version:
    description:
    - 'The desired version of the app / number or "latest" / if not specified, latest version is used'
  auth_username:
    description:
    - 'The name of the user with witch to install apps (usually domain-admin)'
    required: true
  auth_password:
    description:
    - 'The password needed to install apps (usually domain-admin)'
    required: true
'''

EXAMPLES = '''
- name: Install nagios
  univention_app:
    name: nagios
    state: present
    auth_username: Administrator
    auth_password: secret

- name: remove nagios
  univention_app:
    name: nagios
    state: absent
    auth_username: Administrator
    auth_password: secret

- name: upgrade nagios
  univention_app:
    name: nagios
    state: present
    version: 2.1.0
    auth_username: Administrator
    auth_password: secret

- name: Install nagios in specific version
  univention_app:
    name: nagios
    state: present
    version: 2.1.0
    auth_username: Administrator
    auth_password: secret
'''

RETURN = '''
msg:
    description: a return message
    returned: success, failure
    type: str
    sample: Non-UCS-system detected. Nothing to do here.
changed:
    description: if any changes were performed
    returned: success
    type: bool
    sample: True
'''


def check_ucs():
    ''' Check if system is actually UCS, return bool '''
    return os.system("dpkg -s univention-appcenter") == 0


def check_ucs_erratum():
    '''Check if UCS Version is at least 5.0'''
    # Need to run command ucr get version


def ansible_exec(action, appname=None, keyfile=None, username=None, desired_update=None):
    ''' runs ansible's run_command(), choose from actions install, remove, upgrade '''
    univention_app_cmd = {
        'list': "univention-app list --ids-only",
        'list-app': "univention-app list {}".format(appname),
        'info': "univention-app info --as-json",
        'install': ("univention-app {} --noninteractive --username {} --pwdfile {} {}={}"
                    .format(action, username, keyfile, appname, desired_update)),
        'remove': ("univention-app {} --noninteractive --username {} --pwdfile {} {}"
                   .format(action, username, keyfile, appname)),
        'upgrade': ("univention-app {} --noninteractive --username {} --pwdfile {} {}={}"
                    .format(action, username, keyfile, appname, desired_update)),
        'stall': "univention-app {} {}".format(action, appname),
        'undo_stall': "univention-app {} {} --undo".format(action, appname),
    }
    return module.run_command(univention_app_cmd[action])


def get_apps_status():
    ''' Get the status of available, installed and upgradable apps and return lists'''
    def get_app_list():
        ''' exec to get list of all available apps on this system '''
        return ansible_exec(action='list')[1]

    def get_app_info():
        ''' exec to get lists of installed and upgradable apps on this system '''
        app_info = ansible_exec(action='info')
        try:
            app_infos = json.loads(app_info[1])
        except Exception as e:
            module.fail_json(msg="unable to parse json: {}".format(e))
        return app_infos['installed'], app_infos['upgradable']

    global available_apps_list
    global installed_apps_list
    global upgradable_apps_list
    available_apps_list = get_app_list()
    installed_apps_list, upgradable_apps_list = get_app_info()


def get_app_info():
    ''' exec to get lists of installed and upgradable apps on this system '''
    app_info = ansible_exec(action='info')
    try:
        app_infos = json.loads(app_info[1])
    except Exception as e:
        module.fail_json(msg="unable to parse json: {}".format(e))
    return app_infos['installed'], app_infos['upgradable']


# checks what version of app is currently installed
def check_app_version(_appname):
    app_version = None
    installed_apps_version, _ = get_app_info()
    for app_info in installed_apps_version:
        if _appname in app_info:
            app_version = app_info.split('=')[-1]
            break
    return app_version


# get all available app versions
def get_available_app_versions(_appname):
    get_versions = ansible_exec(
        action='list-app', appname=_appname)[1]
    available_app_versions = re.findall(
        r'\b(\d+\.\d+\.\d+(-\d+)?)\b', get_versions)
    return available_app_versions


# checks if "Latest" is selected and retrieves latest app version
def check_target_app_version(_appname, _version):
    available_app_versions = get_available_app_versions(_appname)
    if _version == 'latest':
        # For the sort operation, hyphens are replaced to allow sorting as int
        available_app_versions.sort(
            key=lambda s: list(map(int, s[0].replace('-', '.').split('.'))))
        latest_version = available_app_versions[-1][0]
        return latest_version
    else:
        return _version


# change from bool to list
def check_app_present(_appname):
    ''' check if a given app is in installed_apps_list, return bool '''
    return _appname in available_apps_list and list(filter(lambda x: _appname in x, installed_apps_list))


def check_app_absent(_appname):
    ''' check if a given app is NOT in installed_apps_list, return bool '''
    return _appname in available_apps_list and not list(filter(lambda x: _appname in x, installed_apps_list))


def check_app_upgradeable(_appname):
    ''' check if a given app is in upgradable_apps_list, return bool '''
    return _appname in available_apps_list and bool(filter(lambda x: _appname in x, upgradable_apps_list))


def generate_tmp_auth_file(_data):
    ''' generate a temporaty auth-file and return path, MUST BE DELETED '''
    fileTemp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    fileTemp.write(_data)
    fileTemp.close()
    return fileTemp.name


def install_app(_appname, _authfile, _desired_version, _auth_username):
    ''' installs an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout '''
    return ansible_exec(action='install', appname=_appname, keyfile=_authfile, username=_auth_username, desired_update=_desired_version)


def remove_app(_appname, _authfile, _auth_username):
    ''' removes an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout'''
    return ansible_exec(action='remove', appname=_appname, keyfile=_authfile, username=_auth_username)


def upgrade_app(_appname, _authfile, _desired_version, _auth_username):
    ''' upgrades an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout'''
    return ansible_exec(action='upgrade', appname=_appname, keyfile=_authfile, username=_auth_username, desired_update=_desired_version)


def stall_app(_appname, _authfile):
    ''' stalls an app with given name and path to auth-file, uses ansible_exec()
        and return tuple of exit-code and stdout. '''
    return ansible_exec(action='stall', appname=_appname, keyfile=_authfile)


def undo_stall_app(_appname, _authfile):
    ''' undos the stalling of an app with given name and path to auth-file, uses ansible_exec()
        and return tuple of exit-code and stdout. '''
    return ansible_exec(action='undo_stall', appname=_appname, keyfile=_authfile)


def main():
    ''' main() is an entry-point for ansible which checks app-status and installs,
        upgrades, or removes the app based on ansible state and name-parameters '''
    global module  # declare ansible-module and parameters globally
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(
                type='str',
                required=True,
                aliases=['app']
            ),
            state=dict(
                type='str',
                default='present',
                choices=['present', 'absent']
            ),
            stall=dict(
                type='str',
                required=False,
                choices=['yes', 'no']
            ),
            auth_password=dict(
                type="str",
                required=True,
                no_log=True
            ),
            auth_username=dict(
                type="str",
                required=True
            ),
            version=dict(
                type='str',
                required=False,
                default='latest'
            )
        ),
        # mutually_exclusive=[[]],
        # required_one_of=[[]],
        supports_check_mode=False,  # this has to be changed. Use -dry-run were necessary
    )

    # This module should only run on UCS-systems
    if not check_ucs():
        changed = False
        return module.exit_json(
            changed=changed,
            msg='Non-UCS-system detected. Nothing to do here.'
        )

    # gather infos and vars
    get_apps_status()
    app_status_target = module.params.get('state')  # desired state of the app
    app_name = module.params.get('name')  # name of the app
    auth_password = module.params.get(
        'auth_password')  # password for domain-adimin
    # check states and explicitly check for presence and absence of app
    auth_username = module.params.get(
        'auth_username')
    app_present = check_app_present(app_name)
    app_absent = check_app_absent(app_name)
    # desired stalling state of the app
    app_stall_target = module.params.get('stall')
    app_target_version = check_target_app_version(
        app_name, module.params.get('version'))
    app_version = check_app_version(app_name)  # check App version

    # some basic logic-checks
    if not app_absent and not app_present:  # this means the app does not exist
        module.fail_json(msg=("app {} does not exist. Please choose from following options:\n{}"
                              .format(app_name, str(available_apps_list))))
    if app_absent and app_present:  # schroedinger's app-status
        module.fail_json(
            msg="an error occured while getting the status of {}".format(app_name))
    if app_status_target == 'present' and not app_present:
        # install_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _install_app = install_app(
                app_name, auth_file, app_target_version, auth_username)
            if _install_app[0] == 0:
                module.exit_json(
                    changed=True, msg="App {} successfully installed.".format(app_name))
            else:
                module.fail_json(
                    msg="an error occured while installing {}".format(app_target_version))
        finally:
            os.remove(auth_file)

    # logic to check App version and mheck if matched with desired version
    if app_status_target == 'present' and app_target_version == app_version:
        module.exit_json(
            changed=False, msg="App {} is present in desired version. ".format(app_name))
    # HERE MAKE SURE VERSIONS GET SORTED NUMERICALLY
    if app_status_target == 'present' and app_target_version < app_version:
        module.fail_json(
            msg="The current version of {} is higher than the desired version. The version currently installed is: {}".format(app_name, app_version))

    # If Desired version higher than current version = Enter update function

    if app_status_target == 'present' and app_target_version > app_version:
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            # update app & check if desired version exists
            available_app_versions = get_available_app_versions(app_name)
            available_app_versions.sort(
                key=lambda s: list(map(int, s.split('.'))))
            # check if version exists & how many versions between current and target
            versions_to_update = available_app_versions[available_app_versions.index(
                app_version)+1:available_app_versions.index(app_target_version)+1]
            for version in versions_to_update:
                # Update App & check if Update successfull
                _upgrade_app = upgrade_app(
                    app_name, auth_file, version, auth_username)
                if _upgrade_app[0] == 0:
                    continue
                else:
                    module.fail_json(
                        msg="an error occured while upgrading {}".format(app_name))
            _app_version = check_app_version(app_name)
            module.exit_json(
                changed=True, msg="App {} successfully upgraded to version {}.".format(app_name, _app_version))

        finally:
            os.remove(auth_file)

    elif app_status_target == 'absent' and app_present:
        # remove_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _remove_app = remove_app(app_name, auth_file, auth_username)
            if _remove_app[0] == 0:
                module.exit_json(
                    changed=True, msg="App {} successfully removed.".format(app_name))
            else:
                module.fail_json(
                    msg="an error occured while uninstalling {}".format(app_name))
        finally:
            os.remove(auth_file)

    elif app_status_target == 'absent' and app_absent:
        module.exit_json(
            changed=False, msg="App {} not installed. No change.".format(app_name))

    if app_present and app_stall_target == 'yes':
        # stall_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _stall_app = stall_app(app_name, auth_file)
            if _stall_app[0] == 0:
                module.exit_json(
                    changed=True, msg="App {} successfully stalled.".format(app_name))
            else:
                module.fail_json(
                    msg="an error occured while stalling {}".format(app_name))
        finally:
            os.remove(auth_file)
    elif app_present and app_stall_target == 'no':
        # undo_stall_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _undo_stall_app = undo_stall_app(app_name, auth_file)
            if _undo_stall_app[0] == 0:
                module.exit_json(
                    changed=True, msg="App {} successfully unstalled.".format(app_name))
            else:
                module.fail_json(
                    msg="an error occured while undoing the stall {}".format(app_name))
        finally:
            os.remove(auth_file)
    elif app_present and app_stall_target and app_stall_target not in ['yes', 'no']:
        module.fail_json(
            changed=False, msg="Unrecognised target state for option stall")

    else:  # just in case ...
        module.fail_json(
            msg="an unknown error occured while handling {}".format(app_name))


if __name__ == '__main__':
    main()
