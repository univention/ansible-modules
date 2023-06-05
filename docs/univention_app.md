# univention.ucs_modules.univention_app

**Manage Apps on UCS.**

Version added: 1.1.0

## Synopsis

- Install & Upgrade Apps
- Configure Apps
- Delete Apps

## Requirements

The below requirements are needed on the host that executes this module.

- Python `>= 2.7` or `>= 3.9`

## Parameters

| Parameter              | Defaults  | Comments                                                                                                                                                   |
| ---------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| name (string)          |           | The name of the App that is managed.                                                                                                                       |
| state (string)         | "present" | The desired state of the App (present/absent/started/stopped).                                                                                             |
| version (string)       |           | The desired version of the app (cannot be lower than currently installed) or latest (Default Is latest is not installed and current version if installed). |
| auth_username (string) |           | The Administrator Username on the UCS system.                                                                                                              |
| auth_password (string) |           | The Admin Password for the system.                                                                                                                         |
| config (dict)          |           | A dict of configuration properties for the selceted Application (case-insentitive).                                                                        |
| stall (bool)           |           | Whether App should be stalled or unstalled.                                                                                                                |

## Notes

## Examples

```yaml
# Install with specific version and config parameter
- name: install & configure ox-connector
  univention_app:
    name: ox-connector
    state: present
    version: 2.1.0
    auth_username: Administrator
    auth_password: univention
    config:
      ox_SOAP_SERVER: "Test"

# Upgrade to specific version
- name: upgrade ox-connector
  univention_app:
    name: ox-connector
    state: present
    version: 2.1.3
    auth_username: Administrator
    auth_password: univention

# change config Params
- name: configure ox-connector
  univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    config:
      ox_SOAP_SERVER: "TestTest"

# No changes when Config Params are identical
- name: configure ox-connector no changes
  univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    config:
      ox_SOAP_SERVER: "TestTest"

# Stop App
- name: stop ox-connector
  univention_app:
    name: ox-connector
    state: stopped
    auth_username: Administrator
    auth_password: univention

# Stall App
- name: stall ox-connector
  univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    stall: "yes"

# unstall App
- name: stall ox-connector
  univention_app:
    name: ox-connector
    state: present
    auth_username: Administrator
    auth_password: univention
    stall: "no"

# Deinstall App
- name: uninstall ox-connector
  univention_app:
    name: ox-connector
    state: absent
    auth_username: Administrator
    auth_password: univention
```

## Return Values

| Key               | Returned | Description                                                                                                  |
| ----------------- | -------- | ------------------------------------------------------------------------------------------------------------ |
| `changed`(list)   | always   | Whether any changed were made.                                                                               |
| `message`(string) | always   | A human-readable information about which App was changed with information such as state, version and config. |
