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

# Define a function for GET requests to NSX Manager and return the response body as dictionry.
def nsxGet(uri):
    try:
        getResponse = requests.get(nsxURL + uri, auth=(nsxUsername, nsxPassword), verify=False, timeout=5)
        if getResponse.status_code == 403:
            print('Unable to login to NSX Manager. Verify username and password.')
            sys.exit()
        if getResponse.status_code == 404:
            print('URI not found. Verify NSX Manager IP. If NSX was recently upgraded, verify any API changes in release notes.')
            sys.exit()
        else:
            getDict = xmltodict.parse(getResponse.content, dict_constructor=dict)
            return getDict
    except requests.ConnectionError:
        print('Failed to connect to NSX Manager. Verify reachability.')
        sys.exit()

# Define a function for POST requests to NSX Manager and return message on success.
def nsxPost(uri, bodyDict, XMLRoot):
    try:
        postXML = dicttoxml(bodyDict, custom_root=XMLRoot, attr_type=False)
        postResponse = requests.post(nsxURL + uri, auth=(nsxUsername, nsxPassword), headers=headers, data=postXML, verify=False, timeout=5)
        return postResponse
    except requests.ConnectionError:
        print('Failed to connect to NSX Manager. Verify reachability.')
        sys.exit()

# Define a function to connection to the switches eAPI for configuration.
def eapiConnect(switchIp):
    switchConn = pyeapi.client.connect(transport='https', host=switchIp, username=switchUsername, password=switchPassword)
    switchNode = pyeapi.client.Node(switchConn)
    return switchNode

# Set Variables for API Calls.
nsxUsername = input('NSX Manager Username: ')
nsxPassword = getpass.getpass(prompt='NSX Manager Password: ')
switchUsername = input('Switch Username: ')
switchPassword = getpass.getpass(prompt='Switch Password: ')
tenantName = 'USAA'
zoneName = 'zone1'
dataCenter = 'mn011' # Accepts mn011, mn013 or tx777
headers = {'Content-Type': 'application/xml'} # Headers required for HTTP POSTs
lsName = 'vls' + dataCenter + tenantName + zoneName

# Set Variables for switchport configurations.  Ports must be spelled out fully
switch01Ports = {
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
switch02Ports = {
    'Ethernet16': {
        'description': 'Port Description',
        'mode': 'trunk',
        'speed': '10gfull'
    },
} # Leave empty if no ports on that switch need to be configured.  Would need to look like this {}


if dataCenter == 'mn011':
    nsxManager = '10.92.64.241'
    switches = ('Spline-1', 'Spline-2') # ('mlsmn011ofe01', 'mlsmn011ofe02')
    switchIps = ('10.92.64.204', '10.92.64.205') # Remove this line later.  Not needed for prod.
elif dataCenter == 'mn013':
    nsxManager = '10.92.64.241'
    switches = ('mlsmn013ofe01', 'mlsmn013ofe02')
elif dataCenter == 'tx777':
    nsxManager = '10.92.64.241'
    switches = ('mlstx777ofe01', 'mlstx777ofe02')
else:
    print('Incorrect Data Center Selection.  Valid choices are mn011, mn013 or tx777')
    sys.exit()

nsxURL = 'https://' + nsxManager + '/api/2.0/vdn/' # All calls will be to this base URL

# GET Hardware Binding ID for CVX
hwURI = 'hardwaregateways'
hwDict = nsxGet(hwURI)
# Parse out Hardware Binfing ID for later use.
hwId = hwDict['list']['hardwareGateway']['objectId']


# GET the list of logical switches to parse out the ID of the tenant switch.
lsURI = 'virtualwires'
lsDict = nsxGet(lsURI)
# Find objectId of tenant's logical switch by name
for item in lsDict['virtualWires']['dataPage']['virtualWire']:
    if item['name'] == lsName:
        lsId = item['objectId']
        lsVniId = item['vdnId']
        vlanId = lsVniId[0] + lsVniId[2:]

# Check if switch01 has ports that require configuration and do them up.
if bool(switch01Ports) != False:
    switch01 = eapiConnect(switchIps[0])
    # Add Error Handling to check for pre-existing port config, add vlan to trunk, etc.
    for port, config in switch01Ports.items():
        if config['mode'] == 'trunk':
            switch01.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk allowed vlan ' + vlanId,
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
                    'switchport trunk native vlan ' + vlanId,
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
                    'switchport access vlan ' + vlanId,
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
if bool(switch02Ports) != False:
    switch02 = eapiConnect(switchIps[0])
    # Add Error Handling to check for pre-existing port config, add vlan to trunk, etc.
    for port, config in switch02Ports.items():
        if config['mode'] == 'trunk':
            switch02.config(
                [
                    'interface ' + port,
                    'description ' + config['description'],
                    'speed forced ' + config['speed'],
                    'switchport trunk allowed vlan ' + vlanId,
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
                    'switchport trunk native vlan ' + vlanId,
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
                    'switchport access vlan ' + vlanId,
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
hwBindURI = 'virtualwires/' + lsId + '/hardwaregateways'
# Loop to Generate Request Body from Dictionary for all switch bindings.
# Check if switch01 has ports for binding, then process.
if bool(switch01Ports) != False:
    for port, config in switch01Ports.items():
        if config['mode'] == 'access':
            hwBindDict = {'hardwareGatewayId': hwId, 'vlan': '0', 'switchName': switches[0], 'portName': port}
            hwBindResponse = nsxPost(hwBindURI, hwBindDict, 'hardwareGatewayBinding')
            if hwBindResponse.status_code == 200:
                print('Hardware binding complete for ' + switches[0] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[0] + ' ' + port)
        else:
            hwBindDict = {'hardwareGatewayId': hwId, 'vlan': vlanId, 'switchName': switches[0], 'portName': port}
            hwBindResponse = nsxPost(hwBindURI, hwBindDict, 'hardwareGatewayBinding')
            if hwBindResponse.status_code == 200:
                print('Hardware binding complete for ' + switches[0] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[0] + ' ' + port)
# Check if switch02 has ports for binding, then process.
if bool(switch02Ports) != False:
    for port, config in switch02Ports.items():
        if config['mode'] == 'access':
            hwBindDict = {'hardwareGatewayId': hwId, 'vlan': '0', 'switchName': switches[1], 'portName': port}
            hwBindResponse = nsxPost(hwBindURI, hwBindDict, 'hardwareGatewayBinding')
            if hwBindResponse.status_code == 200:
                print('Hardware binding complete for ' + switches[1] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[1] + ' ' + port)
        else:
            hwBindDict = {'hardwareGatewayId': hwId, 'vlan': vlanId, 'switchName': switches[1], 'portName': port}
            hwBindResponse = nsxPost(hwBindURI, hwBindDict, 'hardwareGatewayBinding')
            if hwBindResponse.status_code == 200:
                print('Hardware binding complete for ' + switches[1] + ' ' + port)
            else:
                print('Error binding logical switch to ' + switches[1] + ' ' + port)