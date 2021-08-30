#!/usr/bin/python
import datetime
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
---
module: univention_config_registry

short_description: Accessing the Univention Config Registry

description:
    - "You can set and unset keys in the Univention Config Registry."

options:
    keys:
        description:
            - A dict of keys to set or unset. In case of unsetting, the values
              are ignored.
            - Either this, 'kvlist' or 'commit' must be given.
        type: str
        required: false
    kvlist:
        description:
            - You pass in a list of dicts with this parameter instead of using
              a dict via 'keys'. Each of the dicts passed via 'kvlist' must
              contain the keys 'key' and 'value'. This allows the use of Jinja
              in the UCR keys to set/unset.
            - Either this, 'keys' or 'commit' must be given.
        required: false
    state:
        description:
            - Either 'present' for setting the key/value pairs given with
              'keys' or 'absent' for unsetting the keys from the 'keys'
              dict. Default is 'present'.
        type: str
        choices: [ absent, present ]
        default: present
    commit:
        description:
            - A list of destination filenames as strings to be commited.
            - Either this, 'keys' or 'kvlist' must be given.
        type: list
        required: false

author:
    - Moritz Bunkus (@MoritzBunkus)
    - Jan-Luca Kiok (@jlkDE)
'''

EXAMPLES = '''
# Set various keys
- name: Set proxy configuration
  univention_config_registry:
    keys:
      proxy/http: http://myproxy.mydomain:3128
      proxy/https: http://myproxy.mydomain:3128

# Alternative syntax with use of Jinja.
- name: Set /etc/hosts entries
  univention_config_registry:
    kvlist:
      - key: "hosts/static/{{ item }}"
        value: myhost.fqdn
    loop: [ '192.168.0.1', '192.168.1.1' ]

# Clear proxy configuration
- name: Do not use a proxy
  univention_config_registry:
    keys:
      proxy/http:
      proxy/https:
    state: absent

# Commit templates
- name: Commit resolv.conf and aliases
    univention_config_registry:
    commit:
      - /etc/resolv.conf
      - /etc/aliases
'''

RETURN = '''
meta['changed_keys']:
    description: A list of all key names that were changed
    type: array
meta['commited_templates']:
    description: A list of all templates that were changed
    type: array
message:
    description: A human-readable information about which keys where changed
'''

try:
    from univention.config_registry.backend import ConfigRegistry
    from univention.config_registry import configHandlers

    have_config_registry = True
except ImportError:
    have_config_registry = False


def _commit_files(files, result, module):
    result['changed'] = len(files) > 0

    if not result['changed']:
        result['message'] = "No files need to be unset"

    if module.check_mode:
        if len(files) > 0:
            result['message'] = "These files will be commited: {}".format(" ".join(files))
        return

    if not result['changed']:
        return

    startd = datetime.datetime.now()

    ucr = ConfigRegistry()
    ucr.load()

    ucr_handlers = configHandlers()
    ucr_handlers.load()
    ucr_handlers.update()

    ucr_handlers.commit(ucr, files)

    endd = datetime.datetime.now()
    result['start'] = str(startd)
    result['end'] = str(endd)
    result['delta'] = str(endd - startd)
    result['meta']['commited_templates'] = files
    result['message'] = "These files were be commited: {}".format(" ".join(files))
    result['failed'] = 0

    # FIXME: Currently the function cannot fail
    # if error != 0:
    #     module.fail_json(msg='non-zero return code', **result)


def _set_keys(keys, result, module):
    ucr = ConfigRegistry()
    ucr.load()

    def needs_change(key):
        if key not in ucr:
            return True
        if isinstance(keys[key], bool):
            if keys[key] and not ucr.is_true(key):
                return True
            elif not keys[key] and not ucr.is_false(key):
                return True
        elif ucr[key] != keys[key]:
            return True
        return False

    to_set = list(filter(needs_change, keys))

    result['changed'] = len(to_set) > 0
    if not result['changed']:
        result['message'] = "No keys need to be set"

    if module.check_mode:
        if len(to_set) > 0:
            result['message'] = "These keys need to be set: {}".format(" ".join(to_set))
        return

    if not result['changed']:
        return

    args = ["/usr/sbin/univention-config-registry", "set"] + ["{0}={1}".format(key, keys[key]) for key in to_set]
    startd = datetime.datetime.now()

    rc, out, err = module.run_command(args)

    endd = datetime.datetime.now()
    result['start'] = str(startd)
    result['end'] = str(endd)
    result['delta'] = str(endd - startd)
    result['out'] = out.rstrip("\r\n")
    result['err'] = err.rstrip("\r\n")
    result['rc'] = rc
    result['message'] = "These keys were set: {}".format(" ".join(to_set))
    result['meta']['changed_keys'] = to_set
    result['failed'] = rc != 0 or len(err) > 0

    if rc != 0:
        module.fail_json(msg='non-zero return code', **result)


def _unset_keys(keys, result, module):
    ucr = ConfigRegistry()
    ucr.load()

    to_unset = [key for key in keys if key in ucr]
    result['changed'] = len(to_unset) > 0

    if not result['changed']:
        result['message'] = "No keys need to be unset"

    if module.check_mode:
        if len(to_unset) > 0:
            result['message'] = "These keys need to be unset: {}".format(" ".join(to_unset))
        return

    if not result['changed']:
        return

    args = ["/usr/sbin/univention-config-registry", "unset"] + to_unset
    startd = datetime.datetime.now()

    rc, out, err = module.run_command(args)

    endd = datetime.datetime.now()
    result['start'] = str(startd)
    result['end'] = str(endd)
    result['delta'] = str(endd - startd)
    result['out'] = out.rstrip("\r\n")
    result['err'] = err.rstrip("\r\n")
    result['rc'] = rc
    result['message'] = "These keys were unset: {}".format(" ".join(to_unset))
    result['meta']['changed_keys'] = to_unset
    result['failed'] = rc != 0

    if rc != 0:
        module.fail_json(msg='non-zero return code', **result)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        keys=dict(type='dict', aliases=['name', 'key']),
        kvlist=dict(type='list'),
        state=dict(type='str', default='present', choices=['present', 'absent']),
        commit=dict(type='list')
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
        meta=dict(changed_keys=[], commited_templates=[]),
        message=''
    )

    if not have_config_registry:
        module.fail_json(msg='The Python "univention.config_registry.backend" is not available', **result)

    if not (('keys' in module.params and module.params['keys'])
            or ('kvlist' in module.params and module.params['kvlist'])
            or ('commit' in module.params and module.params['commit'])):
        module.fail_json(msg='Either "keys", "kvlist" or "commit" is required.', **result)

    state = module.params['state']
    keys = module.params['keys'] if 'keys' in module.params and module.params['keys'] else dict()
    commit = module.params['commit'] if 'commit' in module.params and module.params['commit'] else list()

    if 'kvlist' in module.params and module.params['kvlist']:
        for entry in module.params['kvlist']:
            keys[entry['key']] = entry['value']

    if (state != 'present') and (state != 'absent'):
        module.fail_json(msg='The state "{0}" is invalid'.format(state), **result)

    if len(keys) != 0:
        if state == 'present':
            _set_keys(keys, result, module)
        else:
            _unset_keys(keys, result, module)
    elif len(commit) != 0:
        _commit_files(commit, result, module)
    else:
        module.fail_json(msg='Missing keys or files', **result)

    module.exit_json(**result)


if __name__ == '__main__':
    run_module()

# Local Variables:
# indent-tabs-mode: nil
# End:
