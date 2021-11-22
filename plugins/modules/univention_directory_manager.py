#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020-2021, Univention GmbH
# Written by Lukas Zumvorde <zumvorde@univention.de>, Jan-Luca Kiok <kiok@univention.de>
# Based on univention_apps module written by Alexander Ulpts <ulpts@univention.de>

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'comunity'
}

DOCUMENTATION = '''
---
module: univention_directory_manager

short_description: Accessing the Univention Directory Manager

description:
    - "You can create and modify Objects in the LDAP with Univention Directory Manager."

options:
    module:
        description:
            - The udm module for witch objects are to be modified
        type: str
        required: True
    position:
        description:
            - The position in the tree
        type: str
        required: False
    dn:
        description:
            - The distinguished name of the LDAP object.
        type: str
        required: false
    filter:
        description:
            - A LDAP search filter to select objects.
        required: false
    state:
        description:
            - Either 'present' for creating or modifying the objects given with
              'dn' and 'filter' or 'absent' for deleting the objects from the LDAP.
              Default is 'present'.
        type: str
        choices: [ absent, present ]
        default: present
    set_properties:
        description:
            - A list of dictionaries with the keys property and value.
            - Properties of the objects are to be set to the given values.
        type: list
        required: False
    unset_properties:
        description:
            - A list of dictionaries with the key property.
            - The listed properties of the objects are to be unset.
        type: list
        required: False

author:
    - Lukas Zumvorde
    - Jan-Luca Kiok
'''

EXAMPLES = '''
# create a new user object
- name: create a user
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    set_properties:
      - property: 'username'
        value: 'testuser1'
      - property: 'lastname'
        value: 'testuser1'
      - property: 'password'
        value: 'univention'

# delete one or more objects
- name: delete a user with a search filter
  univention_directory_manager:
    module: 'users/user'
    state: 'absent'
    filter: '(uid=testuser1)'

# use position to place the object in the directory tree
- name: create a user with position
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    position: 'cn=users,ou=DEMOSCHOOL,dc=t1,dc=intranet'
    set_properties:
      - property: 'username'
        value: 'testuser2'
      - property: 'lastname'
        value: 'testuser2'
      - property: 'password'
        value: 'univention'

# delete on very specific object
- name: delete the user with position
  univention_directory_manager:
    module: 'users/user'
    state: 'absent'
    dn: 'uid=testuser2,cn=users,ou=DEMOSCHOOL,dc=t1,dc=intranet'

# add or change specific properties
- name: modify testuser3 - add or change a property
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    set_properties:
      - property: 'firstname'
        value: 'max'

# remove specific properties
- name: modify testuser3 - remove property
  univention_directory_manager:
    module: 'users/user'
    state: 'present'
    filter: '(uid=testuser3)'
    unset_properties:
      - property: 'firstname'
        value: 'does not matter'
'''

RETURN = '''
meta['changed_objects']:
    description: A list of all objects that were changed.
message:
    description: A human-readable information about which objects were changed.
'''

from ansible.module_utils.basic import AnsibleModule  # noqa F401

try:
    from univention.udm import UDM

    have_udm = True
except ModuleNotFoundError:
    have_udm = False


class Stats:
    changed_objects = []


def _set_property(obj, prop, value):
    setattr(obj.props, prop, value)


def _create_or_modify_object(udm_mod, module, stats):
    try:
        obj = udm_mod.get(module.params['dn'])
    except Exception:
        obj = None
    if obj:
        _modify_object(udm_mod, module, obj, stats)
    else:
        _create_object(udm_mod, module, stats)


def _create_object(udm_mod, module, stats):
    params = module.params
    obj = udm_mod.new()
    if module.params['dn']:
        pass  # read position and name from dn
    else:
        if params['position']:
            obj.position = params['position']
    # TODO add policies and options
    # if params['policies']:
    # 	obj.policies = params['policies']
    # if params['options']:
    # 	obj.options.append(params['options'])
    for attr in params['set_properties']:
        prop_name = attr['property']
        prop_value = attr['value']
        _set_property(obj, prop_name, prop_value)
    if not module.check_mode:
        obj.save()
        stats.changed_objects.append(obj.dn)


def _modify_object(udm_mod, module, obj, stats):
    params = module.params
    # TODO add policies and options
    # if params['policies']:
    # 	obj.policies = params['policies']
    # if params['options']:
    # 	obj.options.append(params['options'])
    if params['unset_properties']:
        for attr in params['unset_properties']:
            prop_name = attr['property']
            _set_property(obj, prop_name, None)
    if params['set_properties']:
        for attr in params['set_properties']:
            prop_name = attr['property']
            prop_value = attr['value']
            _set_property(obj, prop_name, prop_value)
    if not module.check_mode:
        obj.save()
        stats.changed_objects.append(obj.dn)


def _remove_objects(udm_mod, module, stats):
    params = module.params
    if module.check_mode:
        return
    if not params['dn'] and not params['filter']:
        module.fail_json(msg='need dn or filter to delete an object', **result)  # noqa F821
    if params['dn']:
        obj = udm_mod.get(params['dn'])
        if not module.check_mode:
            obj.delete()
            stats.changed_objects.append(obj.dn)
    if params['filter']:
        for baseobject in udm_mod.search(params['filter']):
            obj = udm_mod.get(baseobject.dn)
            if not module.check_mode:
                obj.delete()
                stats.changed_objects.append(obj.dn)


def run_module():
    module_args = dict(
        module=dict(
            type='str',
            required=True
        ),
        position=dict(
            type='str',
            required=False
        ),
        set_properties=dict(
            type='list',
            required=False
        ),
        unset_properties=dict(
            type='list',
            required=False
        ),
        dn=dict(
            type='str',
            required=False
        ),
        filter=dict(
            type='str',
            required=False
        ),
        state=dict(
            type='str',
            default='present',
            coices=['present', 'absent'],
            required=False
        ),
        options=dict(
            type='list',
            required=False
        ),
        policies=dict(
            type='list',
            required=False
        ),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        meta=dict(changed_objects=[]),
        message=''
    )

    if not have_udm:
        module.fail_json(msg='The Python "univention.udm" is not available', **result)

    params = module.params
    udm_con = UDM.admin()  # connection to UDM
    udm_con.version(1)
    udm_mod = udm_con.get(module.params['module'])
    stats = Stats()

    if params['state'] == 'present':
        if params['dn']:
            _create_or_modify_object(udm_mod, module, stats)
        if params['filter']:
            for obj in udm_mod.search(params['filter']):
                _modify_object(udm_mod, module, obj, stats)
        if not params['dn'] and not params['filter']:
            _create_object(udm_mod, module, stats)
    elif params['state'] == 'absent':
        _remove_objects(udm_mod, module, stats)
    result['meta']['changed_objects'] = stats.changed_objects
    result['meta']['message'] = 'changed objects: %s' " ".join(stats.changed_objects)

    module.exit_json(**result)


if __name__ == '__main__':
    run_module()
