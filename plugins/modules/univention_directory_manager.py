#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020-2021, Univention GmbH
# Written by Lukas Zumvorde <zumvorde@univention.de>, Jan-Luca Kiok <kiok@univention.de>
# Based on univention_apps module written by Alexander Ulpts <ulpts@univention.de>

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.2',
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
            - The udm module for which objects are to be modified
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
        type: str
        required: false
    state:
        description:
            - Either 'present' for creating or modifying the objects given with
              'dn' and 'filter' or 'absent' for deleting the objects from the LDAP.
              Default is 'present'.
        type: str
        choices: [ absent, present ]
        default: present
    superordinate:
        description:
            - When creating a new object, set its superordinate to this DN.
            - Only affects newly created LDAP objects, this option is ingored for
              modifications and removals of existing entries.
        type: str
        required: False
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
        value: 'mypassword'

# create a DNS record object
- name: create a dns record
  univention_directory_manager:
    module: 'dns/host_record'
    state: 'present'
    superordinate: 'zoneName=example.org,cn=dns,dc=example,dc=org'
    set_properties:
      - property: 'name'
        value: 'test'
      - property: 'a'
        value: '192.0.2.42'
      - property: 'a'
        value: '2001:db8::42'

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
        value: 'mypassword'

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
    import univention.udm

    have_udm = True
except ModuleNotFoundError:
    have_udm = False


class Stats:
    changed_objects = []


def _set_property(obj, prop, value):
    setattr(obj.props, prop, value)


def _create_or_modify_object(dn, udm_mod, module, stats):
    try:
        obj = udm_mod.get(dn)
    except Exception:
        obj = None
    if obj:
        _modify_object(udm_mod, module, obj, stats)
    else:
        _create_object(udm_mod, module, stats)


def apply_policies(obj, module):
    params = module.params
    if params['policies']:
        obj.policies = params['policies']


def apply_options(obj, module):
    params = module.params
    if params['options']:
        obj.options = []
        for opt in params['options']:
            obj.options.append(opt)


def _create_object(udm_mod, module, stats):
    params = module.params
    obj = udm_mod.new(superordinate=params.get('superordinate'))
    if params['position']:
        obj.position = params['position']
    apply_options(obj, module)
    apply_policies(obj, module)
    if params['set_properties']:
        for attr in params['set_properties']:
            prop_name = attr['property']
            prop_value = attr['value']
            _set_property(obj, prop_name, prop_value)
    if not module.check_mode:
        obj.save()
        stats.changed_objects.append(obj.dn)


def _modify_object(udm_mod, module, obj, stats):
    params = module.params
    apply_options(obj, module)
    apply_policies(obj, module)
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


def _get_object_by_property(udm_mod, module):
    try:
        for prop in module.params['set_properties']:
            if prop['property'] == udm_mod.meta.identifying_property:
                return udm_mod.get_by_id(prop['value'])
        else:
            return None
    except univention.udm.exceptions.NoObject:
        return None
    except univention.udm.exceptions.MultipleObjects:
        return None
    except TypeError:
        return None


def _get_object_by_dn(udm_mod, module):
    try:
        if module.params['dn']:
            return udm_mod.get(module.params['dn'])
    except univention.udm.exceptions.NoObject:
        pass
    except univention.udm.exceptions.MultipleObjects:
        pass
    return None


def _extract_properties_from_dn(udm_mod, module, result):
    if not module.params['dn']:
        return
    try:
        name, position = module.params['dn'].split(',', 1)
        name = name.split('=', 1)[1]
        if not module.params['set_properties']:
            module.params['set_properties'] = []
        module.params['set_properties'].append({'property': udm_mod.meta.identifying_property, 'value': name})
        module.params['position'] = position
    except IndexError:
        result['meta']['message'] = 'Invalid parameter dn'
        module.exit_json(**result)


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
        superordinate=dict(
            type='str',
            default=None,
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

    udm_con = UDM.admin()  # connection to UDM
    udm_con.version(1)
    udm_mod = udm_con.get(module.params['module'])
    stats = Stats()

    _extract_properties_from_dn(udm_mod, module, result)
    params = module.params

    obj_by_filter = []
    if params['filter']:
        for obj in udm_mod.search(params['filter']):
            obj_by_filter.append(obj)

    obj_by_property = []
    obj = _get_object_by_property(udm_mod, module)
    if obj:
        obj_by_property.append(obj)

    if params['state'] == 'present':
        for obj in obj_by_filter + obj_by_property:
            _modify_object(udm_mod, module, obj, stats)
        if len(obj_by_filter) == 0 and len(obj_by_property) == 0:
            _create_object(udm_mod, module, stats)

    elif params['state'] == 'absent':
        for obj in obj_by_filter + obj_by_property:
            _remove_objects(udm_mod, module, stats)
    result['meta']['changed_objects'] = stats.changed_objects
    result['meta']['message'] = 'changed objects: %s' " ".join(stats.changed_objects)

    module.exit_json(**result)


if __name__ == '__main__':
    run_module()
