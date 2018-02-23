#!/usr/bin/env python

# BSD 3-Clause License
#
# Copyright (c) 2018, Arista Networks EOS+
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name Arista nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
'''
This is a quick and dirty script to quickly create an NSX Logical Switch
and map that into the Arista hardware VTEPs.  It uses the NSX Managere API
and as such requires you to have admin access there.  I'm sure there's some
RBAC stuff documented by VMware for the minimum necessary access, but I did
my testing with the admin account itself.

Please note that all SSL verification is disabled.  If you have signed certs
in place for NSX Manager, you can remove the urllib3 section and verify option
in the requests calls.

Created by Dimitri Capetz - dcapetz@arista.com
'''

# Import requests for API Calls to NSX Manager
# Import xmltodict and dicttoxml for working with XML
# Import pyEAPI for retrieval of switch attributes
# Import getpass for masked password prompt
# Import argparse for pulling in file input via command line
# Import json for working with json objects
# Import sys for various error handling
import requests
import xmltodict
from dicttoxml import dicttoxml
import pyeapi
import getpass
import argparse
import json
import sys

#Disable Cert Warnings for Test Environment
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

def eapi_connect(switch):
    ''' Connect to eAPI interface of Arista Switch
    
    Args:
        switch (str): The IP address or FQDN of the Arista switch
    
    Returns:
        switch_node (class): The connected node of the function call that can be used for show or config commands.
    '''
    switch_conn = pyeapi.client.connect(transport='https', host=switch, username=switch_username, password=switch_password)
    switch_node = pyeapi.client.Node(switch_conn)
    return switch_node

def eapi_mlag_config_check(switch):
    ''' Connect and check mlag domain ID for use with NSX bindings
    
    Args:
        switch (str): The IP address or FQDN of the Arista switch
    
    Returns:
        mlag_domain (str): The mlag domain ID of the switch
    '''
    switch_node = eapi_connect(switch)
    # Check mlag configuration and parse out mlag domain ID.
    show_mlag_output = switch_node.enable('show mlag')
    mlag_domain = show_mlag_output[0]['result']['domainId']
    return mlag_domain

def nsx_binding_check(switch, port):
    ''' Checks existing NSX hardware bindings for any conflict
    
    Args:
        switch (str): The name of the Arista switch or mlag_domain
        port (str): The name of the port to check for
    '''
    bind_check_dict = nsx_get('virtualwires/' + ls_id + '/hardwaregateways')
    if bool(bind_check_dict['list']) == True:
        try:
            for i in range(len(bind_check_dict['list']['hardwareGatewayBinding'])):
                if bind_check_dict['list']['hardwareGatewayBinding'][i]['switchName'] == switch:
                    if bind_check_dict['list']['hardwareGatewayBinding'][i]['portName'] == port:
                        print(switch + ' ' + port + ' was already bound to ' + ls_name)
                        print('This is expected if the port is the second Mlag port in a switch pair')
                        print('If it is not, please verify input file and switch config')
        except KeyError:
            if bind_check_dict['list']['hardwareGatewayBinding']['switchName'] == switch:
                if bind_check_dict['list']['hardwareGatewayBinding']['portName'] == port:
                    print(switch + ' ' + port + ' was already bound to ' + ls_name)
                    print('This is expected if the port is the second Mlag port in a switch pair')
                    print('If it is not, please verify input file and switch config')
    

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
        # Check if port to bind is an MLAG interface.  If yes, rewrite switch and port variables to match what NSX expects.
        if port.startswith('Port'):
            if config['is_mlag'] == True:
                mlag_port = 'Mlag' + (port.split('l'))[1]
                mlag_switch = 'mlag-' + eapi_mlag_config_check(switch)
        # Check existing hardware bindings to see if there is a duplicate. Notify user but continue.
        if port.startswith('Port'):
            if config['is_mlag'] == True:
                nsx_binding_check(mlag_switch, mlag_port)
            else:
                nsx_binding_check(switch, port)
        else:
            nsx_binding_check(switch, port)
        # Set vlan ID for binding and apply
        if config['mode'] == 'access':
            port_vlan_id = '0'
        else:
            port_vlan_id = vlan
        # Perform harware bindings. Check if mlag is present to ensure names are correct when sent to NSX.
        if port.startswith('Port'):
            if config['is_mlag'] == True:
                hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': port_vlan_id, 'switchName': mlag_switch, 'portName': mlag_port}
                hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            else:
                hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': port_vlan_id, 'switchName': switch, 'portName': port}
                hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
        else:
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': port_vlan_id, 'switchName': switch, 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
        if hw_bind_response.status_code == 200:
            print('NSX hardware binding complete for ' + switch + ' ' + port)
        else:
            print('Error binding NSX logical switch to ' + switch + ' ' + port)

# Pull in JSON file from command line argument
parser = argparse.ArgumentParser(description='Create NSX logical switch and bind to pre-configured switchports')
required_arg = parser.add_argument_group('Required Arguments')
required_arg.add_argument('-j', '--json', dest='json', required=True, help='Input JSON file with data for configuration', type=open)
args = parser.parse_args()
data = json.load(args.json)

# Set Variables for Login.
nsx_username = input('NSX Manager Username: ')
nsx_password = getpass.getpass(prompt='NSX Manager Password: ')

# Set Variables from JSON object for switchport configurations and API Calls.  Ports must be spelled out fully
# Leave JSON object empty if no ports on that switch need to be configured.  Would need to look like this {}
tenant_name = data['tenant_name']
zone_name = data['zone_name']
data_center = list(data['data_center'].keys())[0]
nsx_manager = data['data_center'][data_center]['nsx_manager']
switches = data['data_center'][data_center]['switches']
switch_ports = data['port_configs']
ls_name = 'vls' + data_center + tenant_name + zone_name

# Check if any ports designated for binding are Mlag interfaces.
# If so, have user specify login info for switch to pull Mlag Domain ID.
for index in range(len(switches)):
    switch_ports_mlag_check = switch_ports[(switches[index])]
    for port, config in switch_ports_mlag_check.items():
        if port.startswith('Port'):
            if config['is_mlag'] == True:
                try:
                    switch_username
                except NameError:
                    print('Mlag port identified for binding. Please enter switch login info for Mlag ID retrieval')
                    switch_username = input('Switch Username: ')
                    switch_password = getpass.getpass(prompt='Switch Password: ')

# GET NSX Manager Transport Zone info to pull out Scope ID
tz_dict = nsx_get('scopes')
# Parse out Transport Zone Scope ID for later use
tz_scope_id = tz_dict['vdnScopes']['vdnScope']['objectId']

# GET Hardware Binding ID for CVX
hw_dict = nsx_get('hardwaregateways')
# Parse out Hardware Binfing ID for later use
hw_id = hw_dict['list']['hardwareGateway']['objectId']

# GET all logical switches to check for duplicate by name.
# Note that NSX will let you create logical switches with the same name.
all_ls_dict = nsx_get('scopes/' + tz_scope_id + '/virtualwires')
for index in range(len(all_ls_dict['virtualWires']['dataPage']['virtualWire'])):
    if all_ls_dict['virtualWires']['dataPage']['virtualWire'][index]['name'] == ls_name:
        print('Logical Switch already exists in NSX.  Please verify naming and input file.')
        sys.exit()

# POST to create new Logical Switch
# Generate Dictionary for Request Body and feed into POST Function
ls_dict = {'name': ls_name, 'tenantId': tenant_name}
ls_response = nsx_post('scopes/' + tz_scope_id + '/virtualwires', ls_dict, 'virtualWireCreateSpec')
if ls_response.status_code == 201:
    print('Logical Switch ' + ls_name + ' created.')
    ls_id = ls_response.content.decode('utf-8')
else:
    print('Error Creating Logical Switch.')

# GET the details of the new Logical Switch to pull out the VNI ID and map to a VLAN ID
ls_config_dict = nsx_get('virtualwires/' + ls_id)
ls_vni_id = ls_config_dict['virtualWire']['vdnId']
vlan_id = ls_vni_id[0] + ls_vni_id[-2:]

# Call function to add Hardware Bindings to new Logical Switch
for index in range(len(switches)):
    nsx_hardware_binding(switches[index], switch_ports[(switches[index])], vlan_id)