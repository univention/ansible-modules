# univention.ucs_modules.univention_config_registry

**Manage Univention Config Registry (UCR) variables.**

Version added: 0.0.1

## Synopsis

- Create new variables in UCR.
- Modify existing variables in UCR.
- Delete exisiting variables in UCR.
- `commit` UCR templates to files.

## Requirements

The below requirements are needed on the host that executes this module.

- Python `>= 2.7` or `>= 3.9`

## Parameters

Parameter | Defaults | Comments
--- | --- | ---
keys (dictionary) | | A dict of keys to set or unset. In case of unsetting, the values are ignored. Either this, 'kvlist' or 'commit' must be given. |
kvlist (list) | | You pass in a list of dicts with this parameter instead of using a dict via 'keys'. Each of the dicts passed via 'kvlist' must contain the keys 'key' and 'value'. This allows the use of Jinja in the UCR keys to set/unset. Either this, 'keys' or 'commit' must be given. |
commit (list) | | A list of destination filenames as strings to be commited. Either this, 'keys' or 'kvlist' must be given."
state (string) | "present" | Either 'present' for setting the key/value pairs given with 'keys' or 'absent' for unsetting the keys from the 'keys' dict. |

## Notes

## Examples

```yaml
# Use kvlist to use variable in key
- name: "Allow user to log in (UCR)"
  vars:
    add_local_user_user:
      name: "testuser"
      state: "present"
  univention.ucs_modules.univention_config_registry:
    kvlist:
      - key: "auth/sshd/user/{{ add_local_user_user['name'] }}"
        value: "yes"
    state: "{{ add_local_user_user['state']|default('present') }}"
  tags:
    - "add_local_user"

# Use keys method
- name: "Disable HTTP"
  univention.ucs_modules.univention_config_registry:
    keys:
      apache2/force_https: "yes"
  tags:
    - "hardening_disable_http"
    - "hardening"

# Use commit method
- name: "Commit resolv.conf and aliases"
  univention.ucs_modules.univention_config_registry:
    commit:
      - "/etc/resolv.conf"
      - "/etc/aliases"
 ```

## Return Values
Key | Returned | Description
--- | --- | ---
`meta['changed_keys']`(list) | always | A list of all key names that were changed. |
`meta['commited_templates']`(list) | always | A list of all templates that were changed. |
`message`(string) | always | A human-readable information about which keys where changed. |
