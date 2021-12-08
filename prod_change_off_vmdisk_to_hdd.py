#!/usr/bin/env python3

import os
import sys
import json
from azure.mgmt.compute import ComputeManagementClient
import azure.mgmt.resource
import automationassets

rg_name = ""

print(sys.argv)

if len(sys.argv) > 1 :
    print(sys.argv[1])

# Get credential using run as account
def get_automation_runas_credential(runas_connection):
    from OpenSSL import crypto
    import binascii
    from msrestazure import azure_active_directory
    import adal

    # Get the Azure Automation RunAs service principal certificate
    cert = automationassets.get_automation_certificate("AzureRunAsCertificate")
    pks12_cert = crypto.load_pkcs12(cert)
    pem_pkey = crypto.dump_privatekey(crypto.FILETYPE_PEM,pks12_cert.get_privatekey())

    # Get run as connection information for the Azure Automation service principal
    application_id = runas_connection["ApplicationId"]
    thumbprint = runas_connection["CertificateThumbprint"]
    tenant_id = runas_connection["TenantId"]

    # Authenticate with service principal certificate
    resource ="https://management.core.windows.net/"
    authority_url = ("https://login.microsoftonline.com/"+tenant_id)
    context = adal.AuthenticationContext(authority_url)
    return azure_active_directory.AdalAuthentication(
    lambda: context.acquire_token_with_client_certificate(
            resource,
            application_id,
            pem_pkey,
            thumbprint)
    )

# Authenticate to Azure using the Azure Automation RunAs service principal
runas_connection = automationassets.get_automation_connection("AzureRunAsConnection")
azure_credential = get_automation_runas_credential(runas_connection)

# Set Subscription
subscription_id = str(runas_connection.get("SubscriptionId"))

compute_client = ComputeManagementClient(azure_credential, subscription_id)

# get all vm objects
vm_list = []
for vm in compute_client.virtual_machines.list(rg_name):
    vm_list.append(vm)
    print(vm.name)

# change all shutdown VM's OS Disk to HDD 
deallocated_vm_list = []
for vm in vm_list:
    view = compute_client.virtual_machines.instance_view(rg_name, vm.name)
    for status in view.statuses:
        status_splitted = status.code.split("/") 
        if status_splitted[0] == "PowerState" and status_splitted[1] == "deallocated":
            deallocated_vm_list.append(vm)

# update each off vm's os disk to HDD
for off_vm in deallocated_vm_list:
    disk_name = off_vm.storage_profile.os_disk.name
    new_disk = compute_client.disks.get(rg_name, disk_name)
    new_disk.sku.name = "Standard_LRS"
    async_update = compute_client.disks.create_or_update(rg_name, disk_name, new_disk)
    async_update.wait()