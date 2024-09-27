# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
##
# http://www.apache.org/licenses/LICENSE-2.0
##
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

#!/usr/bin/env python
import json
import subprocess
from celery_once import QueueOnce
from app import celery as celery_app
from app.routes import storage
from app.routes import storage
from fastapi.encoders import jsonable_encoder

from app.patch import make_path


def vm_info(virtual_machine_list, virtual_machine_id):
    selected_vm = None
    for vm in virtual_machine_list:
        if vm['uuid'] == virtual_machine_id:
            selected_vm = vm
            break
    if not selected_vm:
        raise ValueError('Virtual machine not found')
    else:
        return selected_vm


def borg_rc(cmd):
    print(cmd.returncode)
    if cmd.returncode != 0:
        error_msg = cmd.stderr
        error_msg = error_msg.replace(
            "Warning: Attempting to access a previously unknown unencrypted repository!\nDo you want to continue? [yN] yes (from BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK)", "")
        error_msg = error_msg.strip("\n")
        raise ValueError(error_msg)
    if not cmd.stdout:
        return None
    return json.loads(cmd.stdout.strip("\n"))


def get_backup(virtual_machine, backup_name):
    storage_repository = storage.retrieveStoragePathFromHostBackupPolicy(
        virtual_machine)
    borg_repository = make_path(
        storage_repository['path'], virtual_machine['name'])
    request = subprocess.run(
        ["borg", "info", "--json", f"{borg_repository}::{backup_name}"], text=True, capture_output=True)
    return borg_rc(request)


def delete_backup(virtual_machine, backup_name):
    storage_repository = storage.retrieveStoragePathFromHostBackupPolicy(
        virtual_machine)
    borg_repository = make_path(storage_repository['path'], virtual_machine['name'])
    get_backup(virtual_machine, backup_name)
    request = subprocess.run(
        ["borg", "delete", f"{borg_repository}::{backup_name}"], text=True, capture_output=True)
    return borg_rc(request)


@celery_app.task(name='Get VM archive info')
def get_archive_info(virtual_machine_list, virtual_machine_id, backup_name):
    virtual_machine = vm_info(virtual_machine_list, virtual_machine_id)
    return get_backup(virtual_machine, backup_name)


@celery_app.task(name='Delete VM archive', base=QueueOnce)
def remove_archive(virtual_machine_list, virtual_machine_id, backup_name):
    virtual_machine = vm_info(virtual_machine_list, virtual_machine_id)
    return delete_backup(virtual_machine, backup_name)
