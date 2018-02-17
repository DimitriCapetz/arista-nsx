'''
This is a quick and dirty script (again again) that will configure any bare-metal ports
on the OFE switches and map those as hardware bindings in NSX.

Per this script, it will be important to configure the VTEP switchport FIRST
and from there hop into NSX and map the ports to logical switches.  Currently,
it is written to only configure bindings for one logical switch at a
time.

This script will leverage the CVP REST API to push the switchport configuration
into a pre-existing configlet.  I have assumed the configlets for the device
specific ports will be called '<switchname> Switchports' but this can be changed to
whatever naming standard you like.

Please note that all SSL verification is disabled.  If you have signed certs
in place for NSX Manager, you can remove the urllib3 section and verify option
in the requests.

Created by Dimitri Capetz - dcapetz@arista.com
'''

# Import requests for API Calls to NSX Manager
# Import xmltodict and dicttoxml for working with XML
# Import getpass for password prompt
# Import argparse for pulling in file input via command line
# Import json for working with json objects
# Import CVP REST API Client for configuration of Arista Switches through CVP
# Import re for parsing and sorting configs
# Import time for waiting to ensure tasks complete
# Import sys for various error handling
import requests
import xmltodict
from dicttoxml import dicttoxml
import getpass
import argparse
import json
from cvprac.cvp_client import CvpClient
from cvprac.cvp_client_errors import CvpApiError
import re
import time
import sys

# Disable Cert Warnings for Test Environment
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def nsx_get(uri):
    ''' Make generic HTTP GET to NSX Manager
        
        Args:
            uri (str): The uri to call
        
        Returns:
            response (dict): The response body of the HTTP GET
    '''
    nsx_url = 'https://' + nsx_manager + '/api/2.0/vdn/' # All calls will be to this base URL
    try:
        get_response = requests.get(nsx_url + uri, auth=(nsx_username, nsx_password), verify=False, timeout=5)
        if get_response.status_code == 403:
            print('Unable to login to NSX Manager. Verify username and password.')
            sys.exit()
        if get_response.status_code == 404:
            print('URI not found. Verify NSX Manager IP and JSON input file. If NSX was recently upgraded, verify any API changes in release notes.')
            sys.exit()
        else:
            get_dict = xmltodict.parse(get_response.content, dict_constructor=dict)
            return get_dict
    except requests.ConnectionError:
        print('Failed to connect to NSX Manager. Verify reachability.')
        sys.exit()

def nsx_post(uri, body_dict, xml_root):
    ''' Make generic HTTP POST to NSX Manager
        
        Args:
            uri (str): The uri to call
            body_dict (dict): A dictionary containing the body of the request to be sent
            xml_root (str): The custom XML Root need to place the body in the correct structure
        
        Returns:
            response (str): The response of the HTTP POST
    '''
    nsx_url = 'https://' + nsx_manager + '/api/2.0/vdn/' # All calls will be to this base URL
    headers = {'Content-Type': 'application/xml'} # Headers required for HTTP POSTs
    try:
        post_xml = dicttoxml(body_dict, custom_root=xml_root, attr_type=False)
        post_response = requests.post(nsx_url + uri, auth=(nsx_username, nsx_password), headers=headers, data=post_xml, verify=False, timeout=5)
        return post_response
    except requests.ConnectionError:
        print('Failed to connect to NSX Manager. Verify reachability.')
        sys.exit()

def switch_configlet_update(switch, switch_ports):
    ''' Generate switch config if ports are present, convert to configlet
        Extends config if preexisting, creates new configlet if not
        
        Args:
            switch (str): The name of the switch to be configured
            switch_ports (dict): A dictionary containing configuration attributes
    '''
    switch_eth_config_to_add = []
    switch_pc_config_to_add = []
    if bool(switch_ports) == True:
        # Generate Switch Configurations as list items.
        for port, config in switch_ports.items():
            if port.startswith('Port'):
                port_channel_id = (port.split('l'))[1]
                for index in range(len(config['local_members'])):
                    switch_eth_config_to_add.extend(['interface ' + config['local_members'][index] + '\n   description ' + config['description'] + '\n   channel-group ' + port_channel_id + ' mode active\n   speed forced ' + config['speed'] + '\n   no shutdown'])
                if config['mode'] == 'trunk':
                    switch_pc_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   switchport trunk allowed vlan ' + vlan_id + '\n   switchport mode trunk' + '\n   no shutdown'])
                elif config['mode'] == 'trunk native':
                    switch_pc_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   switchport trunk native vlan ' + vlan_id + '\n   switchport mode trunk' + '\n   no shutdown'])
                elif config['mode'] == 'access':
                    switch_pc_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   switchport access vlan ' + vlan_id + '\n   switchport mode access' + '\n   no shutdown'])
                else:
                    print('Incorrect Port Mode Selection for ' + switch +
                    '.  Please verify port configurations.  Valid options are trunk, trunk native and access.')
                    sys.exit()
            else:
                if config['mode'] == 'trunk':
                    switch_eth_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   speed forced ' +     config['speed'] + '\n   switchport trunk allowed vlan ' + vlan_id + '\n   switchport mode trunk' + '\n   no shutdown'])
                elif config['mode'] == 'trunk native':
                    switch_eth_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   speed forced ' +     config['speed'] + '\n   switchport trunk native vlan ' + vlan_id + '\n   switchport mode trunk' + '\n   no shutdown'])
                elif config['mode'] == 'access':
                    switch_eth_config_to_add.extend(['interface ' + port + '\n   description ' + config['description'] + '\n   speed forced ' +     config['speed'] + '\n   switchport access vlan ' + vlan_id + '\n   switchport mode access' + '\n   no shutdown'])
                else:
                    print('Incorrect Port Mode Selection for ' + switch + '.  Please verify port configurations.  Valid options are trunk, trunk native and access.')
                    sys.exit()
        try:
            switch_configlet_data = cvp.api.get_configlet_by_name(switch + ' Switchports')
            # Check if configlet has existing data.  If so, append new config.
            if bool(switch_configlet_data['config']) == True:
                # Check if any ports already exist in configlet.  If so, skip loop iteration.
                for port, config in switch_ports.items():
                    if port.startswith('Port'):
                        for index in range(len(config['local_members'])):
                            if config['local_members'][index] in switch_configlet_data['config']:
                                print(switch + ' ' + config['local_members'][index] + ' already exists in ' + switch + ' Switchports configlet.  Verify config.')
                                print('Skipping edits for ' + switch + ' Switchports configlet.')
                                port_config_exception = 1
                                return port_config_exception
                    if port in switch_configlet_data['config']:
                        print(switch + ' ' + port + ' already exists in ' + switch + ' Switchports configlet.  Verify config.')
                        print('Skipping edits for ' + switch + ' Switchports configlet.')
                        port_config_exception = 1
                        return port_config_exception
                # Take existing configlet data and split into list for sorting.
                # Separate Eths and PCs into separate list for desired placement in configlet.
                switch_configlet = switch_configlet_data['config'].split('\n\n')
                switch_eth_configlet = []
                switch_pc_configlet = []
                for index in range(len(switch_configlet)):
                    if switch_configlet[index].startswith('interface Eth'):
                        switch_eth_configlet.extend([switch_configlet[index]])
                    elif switch_configlet[index].startswith('interface Port'):
                        switch_pc_configlet.extend([switch_configlet[index]])
                switch_eth_configlet.extend(switch_eth_config_to_add)
                if (bool(switch_pc_configlet) == True) or (bool(switch_pc_config_to_add) == True):
                    switch_pc_configlet.extend(switch_pc_config_to_add)
                # Sort configlet data so interfaces show up in proper order.
                switch_eth_configlet = sorted(switch_eth_configlet, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
                switch_eth_configlet = '\n\n'.join(switch_eth_configlet)
                if bool(switch_pc_configlet) == True:
                    switch_pc_configlet = sorted(switch_pc_configlet, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
                    switch_pc_configlet = '\n\n'.join(switch_pc_configlet)
                    switch_configlet = switch_pc_configlet + '\n\n' + switch_eth_configlet
                else:
                    switch_configlet = switch_eth_configlet
            else:
                # Sort configlet data so interfaces show up in proper order.
                switch_eth_configlet = sorted(switch_eth_config_to_add, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
                switch_eth_configlet = '\n\n'.join(switch_eth_configlet)
                if bool(switch_pc_config_to_add) == True:
                    print('PC Config Exists')
                    switch_pc_configlet = sorted(switch_pc_config_to_add, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
                    switch_pc_configlet = '\n\n'.join(switch_pc_configlet)
                    switch_configlet = switch_pc_configlet + '\n\n' + switch_eth_configlet
                else:
                    switch_configlet = switch_eth_configlet
            cvp.api.update_configlet(switch_configlet, switch_configlet_data['key'], switch + ' Switchports')
            print('Adding config to ' + switch + ' Switchports configlet...')
            return
        # Exception to create configlet and apply to switch if it doesn't yet exist.
        except CvpApiError:
            print(switch + ' Switchports configlet doesn\'t exist.  Creating and applying to ' + switch)
            switch_configlet_name = switch + ' Switchports'
            # Sort new configlet data so interfaces show up in proper order
            switch_eth_configlet = sorted(switch_eth_config_to_add, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
            switch_eth_configlet = '\n\n'.join(switch_eth_configlet)
            if bool(switch_pc_config_to_add) == True:
                switch_pc_configlet = sorted(switch_pc_config_to_add, key=lambda x:list(map(int, re.findall('[0-9/]+(?=\n\s\s\s)', x)[0].split('/'))))
                switch_pc_configlet = '\n\n'.join(switch_pc_configlet)
                switch_configlet = switch_pc_configlet + '\n\n' + switch_eth_configlet
            else:
                switch_configlet = switch_eth_configlet
            switch_configlet_push = cvp.api.add_configlet(switch_configlet_name, switch_configlet)
            switch_configlet_data = cvp.api.get_configlet_by_name(switch + ' Switchports')
            # Pull down switch info to attach new configlet.
            switch_info = cvp.api.get_device_by_name(switch)
            switch_response = cvp.api.apply_configlets_to_device('NSX Binding Script', switch_info, [switch_configlet_data], create_task=True)
            return

def execute_pending_tasks():
    ''' Executes pending tasks in CVP.  Use carefully in active environment.
        It will provide some checking to make sure the pending tasks are on the switches
        from the input file and created by the same user running the script, etc.
        It could still execute tasks that were previously created from the same user.
        Waits inserted to ensure logs are complete and push complete before moving on.
    
    Returns:
    
    '''
    pending_tasks = cvp.api.get_tasks_by_status('Pending')
    for index in range(len(pending_tasks)):
        if pending_tasks[index]['description'].startswith('Configlet Assign'):
            if pending_tasks[index]['workOrderDetails']['netElementHostName'] in data['data_center'][data_center]['switches']:
                if pending_tasks[index]['createdBy'] == cvp_username:
                    task_id = pending_tasks[index]['workOrderId']
                    push_task = cvp.api.execute_task(task_id)
                    # Wait to ensure task push is complete so full logs are available.
                    print('Waiting for task execution to complete...')
                    time.sleep(15)
                    task_logs = cvp.api.get_logs_by_id(task_id)
                    for index in range(len(task_logs['data'])):
                        if task_logs['data'][index]['logDetails'].startswith('Configlet push response') == True:
                            print('Task '+ task_id + ' - ' + task_logs['data'][index]['logDetails'] + ' - ' + task_logs['data'][index]['objectName'])

def nsx_hardware_binding(switch, switch_ports, vlan):
    ''' Generate body and POST to NSX Manager if ports are present
    
    Args:
        switch (str): The name of the switch to perform bindings for
        switch_ports (dict): A dictionary containing configuration attributes
        vlan (str): The vlan ID to bind the logical switch to
    '''
    # Loop to Generate Request Body from Dictionary for all switch bindings and POST
    # So far as I can tell, these can only be done one switch per request and must be looped through.
    hw_bind_uri = 'virtualwires/' + ls_id + '/hardwaregateways'
    for port, config in switch_ports.items():
        # Check existing hardware bindings to see if there is a duplicate. Notify user but continue.
        bind_check_dict = nsx_get('virtualwires/' + ls_id + '/hardwaregateways')
        for index in range(len(bind_check_dict['list']['hardwareGatewayBinding'])):
            if bind_check_dict['list']['hardwareGatewayBinding'][index]['switchName'] == switch:
                if bind_check_dict['list']['hardwareGatewayBinding'][index]['portName'] == port:
                    print(switch + ' ' + port + ' was already bound to ' + ls_name + '. Please verify config.')
        if config['mode'] == 'access':
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': '0', 'switchName': switch, 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('NSX hardware binding complete for ' + switch + ' ' + port)
            else:
                print('Error binding NSX logical switch to ' + switch + ' ' + port)
        else:
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': vlan, 'switchName': switch, 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('NSX hardware binding complete for ' + switch + ' ' + port)
            else:
                print('Error binding NSX logical switch to ' + switch + ' ' + port)

# Pull in JSON file from command line argument
parser = argparse.ArgumentParser(description='Configure Arista switchports via CVP and bind to existing NSX logical switch')
required_arg = parser.add_argument_group('Required Arguments')
required_arg.add_argument('-j', '--json', dest='json', required=True, help='Input JSON file with data for configuration', type=open)
args = parser.parse_args()
data = json.load(args.json)

# Set Variables for Login.
nsx_username = input('NSX Manager Username: ')
nsx_password = getpass.getpass(prompt='NSX Manager Password: ')
cvp_username = input('CVP Username: ')
cvp_password = getpass.getpass(prompt='CVP Password: ')

# Set Variables from JSON object for switchport configurations and API Calls.  Ports must be spelled out fully
# Leave JSON object empty if no ports on that switch need to be configured.  Would need to look like this {}
tenant_name = data['tenant_name']
zone_name = data['zone_name']
data_center = list(data['data_center'].keys())[0]
nsx_manager = data['data_center'][data_center]['nsx_manager']
switches = data['data_center'][data_center]['switches']
cvps = data['data_center'][data_center]['cvps']
switch01_ports = data['switch01_ports']
switch02_ports = data['switch02_ports']
ls_name = 'vls' + data_center + tenant_name + zone_name

# GET Hardware Binding ID for CVX
hw_dict = nsx_get('hardwaregateways')
# Parse out Hardware Binfing ID for later use
hw_id = hw_dict['list']['hardwareGateway']['objectId']

# GET the list of logical switches to parse out the ID and VNI of the tenant switch
ls_dict = nsx_get('virtualwires')
# Find objectId of tenant's logical switch by name
for item in ls_dict['virtualWires']['dataPage']['virtualWire']:
    if item['name'] == ls_name:
        ls_id = item['objectId']
        ls_vni_id = item['vdnId']
        vlan_id = ls_vni_id[0] + ls_vni_id[-2:]

# Connect to CVP for configlet push. Loging for the connection is setup to the same dir as the script
cvp = CvpClient(syslog=True, filename='cvprac_log')
cvp.connect(cvps, cvp_username, cvp_password)

# Check if switch01 has ports, then generate config and apply via CVP Configlet for each switch.
if bool(switch01_ports) == True:
    switch01_push = switch_configlet_update(switches[0], switch01_ports)
    if switch01_push == 1:
        print('Exiting script to prevent misconfiguration. Verify switch01_ports config data.')
        sys.exit()
# Check if switch02 has ports, then generate config and apply via CVP Configlet for each switch.
if bool(switch02_ports) == True:
    switch02_push = switch_configlet_update(switches[1], switch02_ports)
    if switch02_push == 1:
        print('Exiting script to prevent misconfiguration. Verify switch02_ports config data.')
        sys.exit()

# Execute pending tasks in CVP to push updated configlets to switches
# Add wait time before to ensure configlet changes are registered as tasks
print('All configlets updated.  Pushing Tasks via CVP...')
time.sleep(5)
execute_pending_tasks()

# Check if switch01 has ports for binding, then call function to bind ports
if bool(switch01_ports) == True:
    nsx_hardware_binding(switches[0], switch01_ports, vlan_id)
# Check if switch02 has ports for binding, then call function to bind ports
if bool(switch02_ports) == True:
    nsx_hardware_binding(switches[1], switch02_ports, vlan_id)