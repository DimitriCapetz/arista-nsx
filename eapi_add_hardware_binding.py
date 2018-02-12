'''
This is a quick and dirty script (again) that will configure any bare-metal ports
on the OFE switches and map those as hardware bindings in NSX.

Per this script, it will be important to configure the VTEP switchport FIRST
and from there hop into NSX and map the ports to logical switches.  Currently,
it is written to only configure bindings for one tenant's logical switch at a
time.

This script assumes DNS resolution is in place for all switches.

As of now, this script is setup to use the eAPI of each VTEP switch directly.
Once we have CVP formatted correctly and configlets implemented, we can transition
this script to instead use the CVP API so as to avoid any reconciliation issues.

Please note that all SSL verification is disabled.  If you have signed certs
in place for NSX Manager, you can remove the urllib3 section and verify option
in the requests.

Created by Dimitri Capetz - dcapetz@arista.com

1/30 - Need to add error handling
'''

# Import requests for API Calls to NSX Manager
# Import xmltodict and dicttoxml for working with XML
# Import getpass for password prompt
# Import pyEAPI for configuration of Arista Switches
# Import sys for various error handling
# Use PIP to install these if they aren't already present
import requests
import xmltodict
from dicttoxml import dicttoxml
import getpass
import pyeapi
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
            print('URI not found. Verify NSX Manager IP. If NSX was recently upgraded, verify any API changes in release notes.')
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
    try:
        post_xml = dicttoxml(body_dict, custom_root=xml_root, attr_type=False)
        post_response = requests.post(nsx_url + uri, auth=(nsx_username, nsx_password), headers=headers, data=post_xml, verify=False, timeout=5)
        return post_response
    except requests.ConnectionError:
        print('Failed to connect to NSX Manager. Verify reachability.')
        sys.exit()

# Define a function to connection to the switches eAPI for configuration.
def eapi_connect(switch_ip):
    switch_conn = pyeapi.client.connect(transport='https', host=switch_ip, username=switch_username, password=switch_password)
    switch_node = pyeapi.client.Node(switch_conn)
    return switch_node

# Set Variables for API Calls.
nsx_username = input('NSX Manager Username: ')
nsx_password = getpass.getpass(prompt='NSX Manager Password: ')
switch_username = input('Switch Username: ')
switch_password = getpass.getpass(prompt='Switch Password: ')
tenant_name = 'USAA'
zone_name = 'zone1'
data_center = 'mn011' # Accepts mn011, mn013 or tx777
headers = {'Content-Type': 'application/xml'} # Headers required for HTTP POSTs
ls_name = 'vls' + data_center + tenant_name + zone_name

# Set Variables for switchport configurations.  Ports must be spelled out fully
switch01_ports = {
    'Ethernet17': {
        'description': 'Port Description',
        'mode': 'access',
        'speed': '1000full'
    },
    'Ethernet18': {
        'description': 'Port Description',
        'mode': 'trunk native',
        'speed': '10gfull'
    }
}
switch02_ports = {
    'Ethernet16': {
        'description': 'Port Description',
        'mode': 'trunk',
        'speed': '10gfull'
    },
} # Leave empty if no ports on that switch need to be configured.  Would need to look like this {}

if data_center == 'mn011':
    nsx_manager = '10.92.64.241'
    switches = ('Spline-1', 'Spline-2') # ('mlsmn011ofe01', 'mlsmn011ofe02')
    switch_ips = ('10.92.64.204', '10.92.64.205') # Remove this line later.  Not needed for prod.
elif data_center == 'mn013':
    nsx_manager = '10.92.64.241'
    switches = ('mlsmn013ofe01', 'mlsmn013ofe02')
elif data_center == 'tx777':
    nsx_manager = '10.92.64.241'
    switches = ('mlstx777ofe01', 'mlstx777ofe02')
else:
    print('Incorrect Data Center Selection.  Valid choices are mn011, mn013 or tx777')
    sys.exit()

# GET Hardware Binding ID for CVX
hw_dict = nsx_get(h'hardwaregateways')
# Parse out Hardware Binfing ID for later use.
hw_id = hw_dict['list']['hardwareGateway']['objectId']


# GET the list of logical switches to parse out the ID of the tenant switch.
ls_dict = nsx_get('virtualwires')
# Find objectId of tenant's logical switch by name
for item in ls_dict['virtualWires']['dataPage']['virtualWire']:
    if item['name'] == ls_name:
        ls_id = item['objectId']
        ls_vni_id = item['vdnId']
        vlan_id = ls_vni_id[0] + ls_vni_id[2:]

# Check if switch01 has ports that require configuration and do them up.
if bool(switch01_ports) != False:
    switch01 = eapi_connect(switch_ips[0])
    # Add Error Handling to check for pre-existing port config, add vlan to trunk, etc.
    for port, config in switch01_ports.items():
        if config['mode'] == 'trunk':
            switch01.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk allowed vlan ' + vlan_id,
                    'switchport mode trunk',
                    'no shutdown'
                ]
            )
            print(switches[0] + ' ' + port + ' configured')
        elif config['mode'] == 'trunk native':
            switch01.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk native vlan ' + vlan_id,
                    'switchport mode trunk',
                    'no shutdown'
                ]
            )
            print(switches[0] + ' ' + port + ' configured')
        elif config['mode'] == 'access':
            switch01.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport access vlan ' + vlan_id,
                    'switchport mode access',
                    'no shutdown'
                ]
            )
            print(switches[0] + ' ' + port + ' configured')
        else:
            print('Incorrect Port Mode Selection.  Please verify port configurations.  Valid options are trunk, trunk native and access.')
            sys.exit()
    switch01.enable('write')
# Check if switch02 has ports that require configuration and do them up.
if bool(switch02_ports) != False:
    switch02 = eapi_connect(switch_ips[0])
    # Add Error Handling to check for pre-existing port config, add vlan to trunk, etc.
    for port, config in switch02_ports.items():
        if config['mode'] == 'trunk':
            switch02.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk allowed vlan ' + vlan_id,
                    'switchport mode trunk',
                    'no shutdown'
                ]
            )
            print(switches[1] + ' ' + port + ' configured')
        elif config['mode'] == 'trunk native':
            switch02.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk native vlan ' + vlan_id,
                    'switchport mode trunk',
                    'no shutdown'
                ]
            )
            print(switches[1] + ' ' + port + ' configured')
        elif config['mode'] == 'access':
            switch02.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport access vlan ' + vlan_id,
                    'switchport mode access',
                    'no shutdown'
                ]
            )
            print(switches[1] + ' ' + port + ' configured')
        else:
            print('Incorrect Port Mode Selection.  Please verify port configurations.  Valid options are trunk, trunk native and access.')
            sys.exit()
    switch02.enable('write')

# POST to add Hardware Bindings to NSX Logical Switch.
# So far as I can tell, these can only be done one switch per request and must be looped through.
hw_bind_uri = 'virtualwires/' + ls_id + '/hardwaregateways'
# Loop to Generate Request Body from Dictionary for all switch bindings.
# Check if switch01 has ports for binding, then process.
if bool(switch01_ports) != False:
    for port, config in switch01_ports.items():
        if config['mode'] == 'access':
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': '0', 'switchName': switches[0], 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('Hardware binding complete for ' + switches[0] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[0] + ' ' + port)
        else:
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': vlan_id, 'switchName': switches[0], 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('Hardware binding complete for ' + switches[0] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[0] + ' ' + port)
# Check if switch02 has ports for binding, then process.
if bool(switch02_ports) != False:
    for port, config in switch02_ports.items():
        if config['mode'] == 'access':
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': '0', 'switchName': switches[1], 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('Hardware binding complete for ' + switches[1] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[1] + ' ' + port)
        else:
            hw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': vlan_id, 'switchName': switches[1], 'portName': port}
            hw_bind_response = nsx_post(hw_bind_uri, hw_bind_dict, 'hardwareGatewayBinding')
            if hw_bind_response.status_code == 200:
                print('Hardware binding complete for ' + switches[1] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[1] + ' ' + port)