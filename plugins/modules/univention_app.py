#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020-2023, Univention GmbH
# Written by Lukas Zumvorde <zumvorde@univention.de>,
#  Jan-Luca Kiok <kiok@univention.de>, Melf Clausen <melf.clausen.extern@univention.de>,
#  Tim Breidenbach <breidenbach@univention.de>
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
  - Allows ansible to control installation, removal, update and configuration of ucs-apps
notes:
  - none
requirements: [ ]
author: Stefan Ahrens, Melf Clausen
options:
  name:
    description:
    - 'The name of the app'
    required: true
  state:
    description:
    - 'The desired state of the app / present, absent, started, stopped'
    required: true
  version:
    description:
    - 'The desired version of the app / number or "latest" if not specified,
       current version is preserved if app present, latest installed if app absent / downgrade will throw error'
  auth_username:
    description:
    - 'The name of the user with witch to install apps (usually domain-admin)'
    required: true
  auth_password:
    description:
    - 'The password needed to install apps (usually domain-admin)'
    required: true
  config:
    - 'The given configuration the App should have'
    required: false
  stall:
    - 'Whether an App should be stalled or unstalled'
    required: false
  update_app_lists:
    description:
    - 'Updates the list of apps and their versions - Only runs when app is installed or updated'
    required: false
    default: True

'''

EXAMPLES = '''
- name: Install ox-connector
  univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: secret

- name: remove ox-connector
  univention_app:
    name: ox-connector
    state: absent
    auth_username: Administrator
    auth_password: secret

- name: stop ox-connector
  univention_app:
    name: ox-connector
    state: stopped
    auth_username: Administrator
    auth_password: secret

- name: upgrade ox-connector or install in specified version
  univention_app:
    name: ox-connector
    state: present
    version: 2.1.1
    auth_username: Administrator
    auth_password: secret

- name: configure ox-connector
    univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    config:
      EXAMPLE_PARAMETER: 'ExampleValue'

- name: stall ox-connector
    univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    stall: "stalled"
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


def ansible_exec(action, appname=None, keyfile=None, username=None,
                 desired_update=None, configuration=None):
    ''' runs ansible's run_command(), choose from actions install, remove, upgrade '''
    univention_app_cmd = {
        'list': "univention-app list --ids-only",
        'update_app_lists': "univention-app update",
        'list-app': "univention-app list {}".format(appname),
        'info': "univention-app info --as-json",
        'install': ("univention-app {} --noninteractive --username {} --pwdfile {} {}='{}' {}"
                    .format(action, username, keyfile, appname, desired_update, configuration)),
        'remove': ("univention-app {} --noninteractive --username {} --pwdfile {} {}"
                   .format(action, username, keyfile, appname)),
        'upgrade': ("univention-app {} --noninteractive --username {} --pwdfile {} {}='{}'"
                    .format(action, username, keyfile, appname, desired_update)),
        'status': ("univention-app {} {}"
                   .format(action, appname)),
        'start': ("univention-app start {}"
                  .format(appname)),
        'stop': ("univention-app stop {}"
                 .format(appname)),
        'get_configuration': "univention-app configure {} --list".format(appname),
        'configure': "univention-app {} {} {}".format(action, appname, configuration),
        'stall': "univention-app {} {}".format(action, appname),
        'undo_stall': "univention-app stall {} --undo".format(appname),
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

    global AVAILABLE_APPS_LIST
    global INSTALLED_APPS_LIST
    global UPGRADABLE_APPS_LIST
    AVAILABLE_APPS_LIST = get_app_list()
    INSTALLED_APPS_LIST, UPGRADABLE_APPS_LIST = get_app_info()


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
    get_versions = ansible_exec(action='list-app', appname=_appname)[1]
    available_app_versions = re.findall(
        r'\b(\d+\.\d+(?:\.\d+)*(?:-\d+)?(?:-\D+\d+)?(?:\s*v\d+)?)\b', get_versions)

    available_app_versions.sort(
        key=lambda s: list(map(int, re.split(r'\D+', s))))
    return available_app_versions


def check_target_app_version(_appname, _version):
    if _version == 'current':
        if check_app_present(_appname):
            return check_app_version(_appname)
        elif check_app_absent(_appname):
            _version = 'latest'

    if _version == 'latest':
        available_app_versions = get_and_sort_versions(_appname)
        latest_version = available_app_versions[-1]
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


def parse_current_configuration(_config):
    config_lines = _config.split('\n')
    config_dict = {}
    for line in config_lines:
        key_value_pair = line.split(": ", 1)
        if len(key_value_pair) == 2:
            key, value = key_value_pair
            config_dict[key] = value.split(' ')[0].strip("'")
    return config_dict


def format_new_conf(_configuration):
    _conf_str = ""
    if len(_configuration) > 0:
        _conf_str = "--set "
        for setting, value in _configuration.items():
            if value == "" or ' ' in value:
                _conf_str += '{}="{}" '.format(setting, value)
            else:
                _conf_str += '{}={} '.format(setting, value)
    return _conf_str


def check_app_present(_appname):
    ''' check if a given app is in INSTALLED_APPS_LIST, return bool '''
    return _appname in AVAILABLE_APPS_LIST and list(filter(lambda x: _appname in x, INSTALLED_APPS_LIST))


def check_app_absent(_appname):
    ''' check if a given app is NOT in INSTALLED_APPS_LIST, return bool '''
    return _appname in AVAILABLE_APPS_LIST and not list(filter(lambda x: _appname in x, INSTALLED_APPS_LIST))


def check_app_upgradeable(_appname):
    ''' check if a given app is in UPGRADABLE_APPS_LIST, return bool '''
    return _appname in AVAILABLE_APPS_LIST and bool(filter(lambda x: _appname in x, UPGRADABLE_APPS_LIST))


def generate_tmp_auth_file(_data):
    ''' generate a temporary auth-file and return path, MUST BE DELETED '''
    fileTemp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    fileTemp.write(_data)
    fileTemp.close()
    return fileTemp.name


def update_app_lists():
    return ansible_exec(action='update_app_lists')


def start_app(_appname):
    ansible_exec(action='start', appname=_appname)


def stop_app(_appname):
    ansible_exec(action='stop', appname=_appname)


def install_app(_appname, _authfile, _desired_version, _auth_username, _configuration):
    ''' installs an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout '''
    return ansible_exec(action='install', appname=_appname, keyfile=_authfile, username=_auth_username,
                        desired_update=_desired_version, configuration=format_new_conf(_configuration))


def remove_app(_appname, _authfile, _auth_username):
    ''' removes an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout'''
    return ansible_exec(action='remove', appname=_appname, keyfile=_authfile, username=_auth_username)


def upgrade_app(_appname, _authfile, _desired_version, _auth_username):
    ''' upgrades an app with given name and path to auth-file, uses ansible_exec()
        and returns tuple of exit-code and stdout'''
    return ansible_exec(action='upgrade', appname=_appname, keyfile=_authfile,
                        username=_auth_username, desired_update=_desired_version)


def stall_app(_appname, _authfile):
    ''' stalls an app with given name and path to auth-file, uses ansible_exec()
        and return tuple of exit-code and stdout. '''
    return ansible_exec(action='stall', appname=_appname, keyfile=_authfile)


def undo_stall_app(_appname, _authfile):
    ''' undos the stalling of an app with given name and path to auth-file, uses ansible_exec()
        and return tuple of exit-code and stdout. '''
    return ansible_exec(action='undo_stall', appname=_appname, keyfile=_authfile)


def get_app_configuration(_appname):
    ''' get current app configuration, uses ansible_exec()
        and return a dictionary with configuration parameters. '''
    config_output = ansible_exec(
        action='get_configuration', appname=_appname)[1]
    current_app_configuration = parse_current_configuration(config_output)
    return current_app_configuration


def check_config_and_return_differences(_current_config, _app_target_config):
    # Create case-insensitive versions of both configs
    current_config_lower = {k.lower(): v for k, v in _current_config.items()}
    target_config_lower = {k.lower(): v for k, v in _app_target_config.items()}
    # Check if input parameters exist in the app and if params changed
    new_params = {}
    for param in _app_target_config:
        lower_param = param.lower()
        if lower_param not in current_config_lower:
            raise ValueError(
                "The parameter {} does not exist in the app".format(param))
        if current_config_lower[lower_param] != target_config_lower[lower_param]:
            # Get the original key from the current_config
            original_key = [
                key for key in _current_config if key.lower() == lower_param][0]
            new_params[original_key] = _app_target_config[param]

    return new_params


def configure_app(_appname, _configuration):
    ''' set app configuration, uses ansible_exec()
        and return tuple of exit-code and stdout. '''
    return ansible_exec(action='configure', appname=_appname, configuration=format_new_conf(_configuration))


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
                choices=["stalled", "unstalled"]
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
            ),
            config=dict(
                type='dict',
                required=False
            ),
            update_app_lists=dict(
                type='bool',
                default=True,
                required=False
            )
        ),
        # mutually_exclusive=[[]],
        # required_one_of=[[]],
        supports_check_mode=False,  # this has to be changed. Use -dry-run were necessary
    )

    # This module should only run on UCS-systems
    if not check_ucs():
        return module.exit_json(
            changed=True,
            msg='Non-UCS-system detected. Nothing to do here.'
        )

    # update app lists
    def update_lists():
        if module.params.get('update_app_lists'):
            _update_lists = update_app_lists()
            if _update_lists[0] != 0:
                return module.fail_json(
                        msg='''
                        An Error occured running univention-app update.
                        To disable updating app lists set "update_app_lists" to False
                        '''
                        )
    # gather infos and vars
    get_apps_status()
    app_status_target = module.params.get('state')  # desired state of the app
    app_name = module.params.get('name')  # name of the app
    auth_password = module.params.get(
        'auth_password')  # password for domain-admin
    auth_username = module.params.get(
        'auth_username')
    app_present = check_app_present(app_name)
    app_absent = check_app_absent(app_name)
    app_stall_target = module.params.get('stall')
    app_target_version = check_target_app_version(
        app_name, module.params.get('version'))
    app_status = check_app_status(app_name)
    app_target_config = module.params.get('config')
    module_changed = False
    config_changed = False
    # User info if config settings are changed
    new_config_msg = None

    # some basic logic-checks
    if not app_absent and not app_present:  # this means the app does not exist
        module.fail_json(msg=("app {} does not exist. Please choose from following options:\n{}"
                              .format(app_name, str(AVAILABLE_APPS_LIST))))
    if app_absent and app_present:  # schroedinger's app-status
        module.fail_json(
            msg="an error occured while getting the status of {}".format(app_name))

    if app_status_target != 'absent' and not app_present:
        auth_file = generate_tmp_auth_file(auth_password)
        update_lists()
        config = {}
        if app_target_config:
            default_config = get_app_configuration(app_name)
            try:
                config = check_config_and_return_differences(
                    default_config, app_target_config)
            except ValueError as e:
                module.fail_json(
                    module_changed=True, msg="The parameter '{}' does not exist on app {}".format(e, app_name))

        try:
            _install_app = install_app(
                app_name, auth_file, app_target_version, auth_username, config)
            if _install_app[0] == 0:
                module_changed = True
                if len(config) > 0:
                    new_config_msg = '. The following configuration options were changed: {}'.format(
                        config)
                    config_changed = True
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
        update_lists()
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

    if app_status_target != 'absent' and not config_changed and app_target_config:
        current_config = get_app_configuration(app_name)
        # check if keys exist and params changed
        try:
            new_params = check_config_and_return_differences(
                current_config, app_target_config)
        except ValueError as e:
            module.fail_json(
                module_changed=True, msg="The parameter '{}' does not exist on app {}".format(e, app_name))
        if len(new_params) > 0:
            _configure_app = configure_app(app_name, new_params)
            if not _configure_app[0] == 0:
                module.fail_json(msg="An error occured while configuring {} with configuration:{}".format(
                    app_name, new_params))
            else:
                module_changed = True
                new_config_msg = '. The following configuration options were changed: {}'.format(
                    new_params)

    elif app_status_target != 'absent' and app_target_version < app_version:
        module.fail_json(
            msg="""The current version of {} is higher than the desired version.
              The version currently installed is: {}""".format(app_name, app_version))

    if app_status_target in ['started', 'stopped']:
        if app_status_target == 'started' and app_status != 'started':
            start_app(app_name)
            module_changed = True
        elif app_status_target == 'stopped' and app_status != 'stopped':
            stop_app(app_name)
            module_changed = True

    if app_present and app_stall_target == 'stalled':
        # stall_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _stall_app = stall_app(app_name, auth_file)
            if _stall_app[0] == 0:
                module_changed = True
            else:
                module.fail_json(
                    msg="an error occurred while stalling {}".format(app_name))
        finally:
            os.remove(auth_file)
    elif app_present and app_stall_target == 'unstalled':
        # undo_stall_app(app_name)
        auth_file = generate_tmp_auth_file(auth_password)
        try:
            _undo_stall_app = undo_stall_app(app_name, auth_file)
            if _undo_stall_app[0] == 0:
                module_changed = True
            else:
                module.fail_json(
                    msg="an error occurred while undoing the stall {}".format(app_name))
        finally:
            os.remove(auth_file)

    if module_changed:
        module.exit_json(changed=module_changed, msg="{} is {} in version {} {}".format(
            app_name, app_status_target, check_app_version(app_name), new_config_msg))
    else:
        module.exit_json(changed=module_changed, msg="No changes for {}".format(
            app_name))


if __name__ == '__main__':
    main()
