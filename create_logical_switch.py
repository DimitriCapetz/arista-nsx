'''
This is a quick and dirty script to quickly create an NSX Logical Switch
and map that into the Arista hardware VTEPs.  It uses the NSX Managere API
and as such requires you to have admin access there.  I'm sure there's some
RBAC stuff that can be worked out via the Security team.

Please note that all SSL verification is disabled.  If you have signed certs
in place for NSX Manager, you can remove the urllib3 section and verify option
in the requests.

Created by Dimitri Capetz - dcapetz@arista.com

1/30 - Need to add error handling
'''

# Import requests for API Calls to NSX Manager
# Import xmltodict and dicttoxml for working with XML
# Import getpass for password prompt
# Import sys for various error handling
# Use PIP to install these if they aren't already present.
import requests
import xmltodict
from dicttoxml import dicttoxml
import getpass
import sys

#Disable Cert Warnings for Test Environment
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

# Set Variables for API Calls.
nsxUsername = input('NSX Manager Username: ')
nsxPassword = getpass.getpass(prompt='NSX Manager Password: ')
tenantName = 'USAA'
zoneName = 'zone1'
dataCenter = 'mn011' # Accepts mn011, mn013 or tx777
headers = {'Content-Type': 'application/xml'} # Headers required for HTTP POSTs
lsName = 'vls' + dataCenter + tenantName + zoneName

if dataCenter == 'mn011':
    nsxManager = '10.92.64.241' # Update with prod NSX Manager IPs or FQDNs
    switches = ('Spline-1', 'Spline-2') # ('mlsmn011ofe01', 'mlsmn011ofe02')
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

# GET NSX Manager Transport Zone info to pull out Scope ID.
tzURI = 'scopes'
tzDict = nsxGet(tzURI)
# Parse out Transport Zone Scope ID for later use.
tzScopeId = tzDict['vdnScopes']['vdnScope']['objectId']

# GET Hardware Binding ID for CVX
hwURI = 'hardwaregateways'
hwDict = nsxGet(hwURI)
# Parse out Hardware Binfing ID for later use.
hwId = hwDict['list']['hardwareGateway']['objectId']

# POST to create new Logical Switch
lsURI = 'scopes/' + tzScopeId + '/virtualwires'
# Generate Dictionary for Request Body and feed into POST Function.
lsDict = {'name': lsName, 'tenantId': tenantName}
lsResponse = nsxPost(lsURI, lsDict, 'virtualWireCreateSpec')
lsId = lsResponse.content.decode('utf-8')
if lsResponse.status_code == 201:
    print('Logical Switch ' + lsName + ' created.')
else:
    print('Error Creating Logical Switch.')

# GET the details of the new Logical Switch to pull out the VNI ID and map to a VLAN ID.
lsConfigURI = 'virtualwires/' + lsId
lsConfigDict = nsxGet(lsConfigURI)
lsVniId = lsConfigDict['virtualWire']['vdnId']
vlanId = lsVniId[0] + lsVniId[2:]

# POST to add Hardware Bindings to new Logical Switch.
# So far as I can tell, these can only be done one switch per request.
hwBindURI = 'virtualwires/' + lsId + '/hardwaregateways'
# Loop to Generate Request Body from Dictionary for all switch bindings (Firewall and F5 ports)
applNum = 0
for switch in switches:
    applNum = applNum + 1
    fwBindDict = {'hardwareGatewayId': hwId, 'vlan': vlanId, 'switchName': switch, 'portName': 'Ethernet10'} # Replace with Po1500
    fwBindResponse = nsxPost(hwBindURI, fwBindDict, 'hardwareGatewayBinding')
    if fwBindResponse.status_code == 200:
        print('Hardware binding complete for firewall uplink #' + str(applNum))
    else:
        print('Error binding logical switch to hardware VTEP for firewall uplink #' + str(applNum))
    f5BindDict = {'hardwareGatewayId': hwId, 'vlan': vlanId, 'switchName': switch, 'portName': 'Ethernet20'} # Replace with F5 Port
    f5BindResponse = nsxPost(hwBindURI, f5BindDict, 'hardwareGatewayBinding')
    if f5BindResponse.status_code == 200:
        print('Hardware binding complete for F5 uplink #' + str(applNum))
    else:
        print('Error binding logical switch to hardware VTEP for F5 uplink #' + str(applNum))