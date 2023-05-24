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

- name: stop nagios
  univention_app:
    name: nagios
    state: stopped
    auth_username: Administrator
    auth_password: secret

- name: upgrade nagios
  univention_app:
    name: nagios
    state: present
    version: 2.1.1
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
        'status': ("univention-app {} {}"
                   .format(action, appname)),
        'start': ("univention-app start {}"
                  .format(appname)),
        'stop': ("univention-app stop {}"
                 .format(appname)),
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


def get_and_sort_versions(_appname):
    def replace_multiple(_available_versions, _replacements):
        for k, v in _replacements.items():
            _available_versions = _available_versions.replace(k, v)
        return _available_versions

    get_versions = ansible_exec(action='list-app', appname=_appname)[1]
    available_app_versions = re.findall(
        r'\b(\d+\.\d+\.\d+(?:\.\d+)?(?:-\d+)?(?:-\D+\d+)?(?:\s*v\d+)?)\b', get_versions)

    replacements = {" ": ".", "v": ".", "-ucs": ".", "-": "."}
    available_app_versions.sort(
        key=lambda s: list(map(int, replace_multiple(s[0], replacements).split('.'))))
    return available_app_versions


def check_target_app_version(_appname, _version):
    if _version == 'current':
        if check_app_present(_appname):
            return check_app_version(_appname)
        elif check_app_absent(_appname):
            _version = 'latest'

    if _version == 'latest' or _version == 'current':
        available_app_versions = get_and_sort_versions(_appname)
        latest_version = available_app_versions[-1][0]
        return latest_version
    return _version


# check if app status is started or stopped
def check_app_status(_appname):
    app_status = ansible_exec(action='status', appname=_appname)[1]
    if 'Active: active' in app_status:
        return 'started'
    elif 'Active: inactive' in app_status:
        return 'stopped'
    else:
        return 'unknown'


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


def start_app(_appname):
    ansible_exec(action='start', appname=_appname)


def stop_app(_appname):
    ansible_exec(action='stop', appname=_appname)


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
                choices=['present', 'absent', 'started', 'stopped']
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
                default='current'
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
    auth_username = module.params.get(
        'auth_username')
    app_present = check_app_present(app_name)
    app_absent = check_app_absent(app_name)
    app_stall_target = module.params.get('stall')
    app_target_version = check_target_app_version(
        app_name, module.params.get('version'))
    app_status = check_app_status(app_name)
    module_changed = False

    # some basic logic-checks
    if not app_absent and not app_present:  # this means the app does not exist
        module.fail_json(msg=("app {} does not exist. Please choose from following options:\n{}"
                              .format(app_name, str(available_apps_list))))
    if app_absent and app_present:  # schroedinger's app-status
        module.fail_json(
            msg="an error occured while getting the status of {}".format(app_name))

    if app_status_target != 'absent' and not app_present:
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _install_app = install_app(
                app_name, auth_file, app_target_version, auth_username)
            if _install_app[0] == 0:
                module_changed = True
            else:
                module.fail_json(
                    msg="an error occured while installing {}".format(app_target_version))
        finally:
            os.remove(auth_file)

    elif app_status_target == 'absent' and app_present:
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _remove_app = remove_app(app_name, auth_file, auth_username)
            if _remove_app[0] == 0:
                module.exit_json(
                    changed=True, msg="App {} was successfully deinstalled.".format(app_name))
            else:
                module.fail_json(
                    msg="an error occured while uninstalling {}".format(app_name))
        finally:
            os.remove(auth_file)

    elif app_status_target == 'absent' and app_absent:
        module.exit_json(
            changed=False, msg="App {} not installed. No change.".format(app_name))

    app_version = check_app_version(app_name)  # check App version

    if app_status_target != 'absent' and app_target_version > app_version:
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            available_app_versions = get_and_sort_versions(app_name)
            # check how many versions between current and target
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
            module_changed = True
        finally:
            os.remove(auth_file)

    elif app_status_target != 'absent' and app_target_version < app_version:
        module.fail_json(
            msg="The current version of {} is higher than the desired version. The version currently installed is: {}".format(app_name, app_version))

    if app_status_target in ['started', 'stopped']:
        if app_status_target == 'started' and app_status != 'started':
            start_app(app_name)
            module_changed = True
        elif app_status_target == 'stopped' and app_status != 'stopped':
            stop_app(app_name)
            module_changed = True

    if app_present and app_stall_target == 'yes':
        # stall_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _stall_app = stall_app(app_name, auth_file)
            if _stall_app[0] == 0:
                module_changed = True
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
                module_changed = True
            else:
                module.fail_json(
                    msg="an error occured while undoing the stall {}".format(app_name))
        finally:
            os.remove(auth_file)
    elif app_present and app_stall_target and app_stall_target not in ['yes', 'no']:
        module.fail_json(
            changed=False, msg="Unrecognised target state for option stall")

    if module_changed:
        module.exit_json(changed=module_changed, msg="{} is {} in version {}".format(
            app_name, app_status_target, check_app_version(app_name)))
    else:
        module.exit_json(changed=module_changed, msg="No changes for {}".format(
            app_name))


if __name__ == '__main__':
    main()
