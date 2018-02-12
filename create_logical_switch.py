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
# Import getpass for masked password prompt
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

# Set Variables for API Calls.
nsx_username = input('NSX Manager Username: ')
nsx_password = getpass.getpass(prompt='NSX Manager Password: ')
tenant_name = 'USAA'
zone_name = 'zone1'
data_center = 'mn011' # Accepts mn011, mn013 or tx777
headers = {'Content-Type': 'application/xml'} # Headers required for HTTP POSTs
ls_name = 'vls' + data_center + tenant_name + zone_name

if data_center == 'mn011':
    nsx_manager = '10.92.64.241' # Update with prod NSX Manager IPs or FQDNs
    switches = ('Spline-1', 'Spline-2') # ('mlsmn011ofe01', 'mlsmn011ofe02')
elif data_center == 'mn013':
    nsx_manager = '10.92.64.241'
    switches = ('mlsmn013ofe01', 'mlsmn013ofe02')
elif data_center == 'tx777':
    nsx_manager = '10.92.64.241'
    switches = ('mlstx777ofe01', 'mlstx777ofe02')
else:
    print('Incorrect Data Center Selection.  Valid choices are mn011, mn013 or tx777')
    sys.exit()

# GET NSX Manager Transport Zone info to pull out Scope ID
tz_dict = nsx_get('scopes')
# Parse out Transport Zone Scope ID for later use
tz_scope_id = tz_dict['vdnScopes']['vdnScope']['objectId']

# GET Hardware Binding ID for CVX
hw_dict = nsx_get('hardwaregateways')
# Parse out Hardware Binfing ID for later use
hw_id = hw_dict['list']['hardwareGateway']['objectId']

# POST to create new Logical Switch
# Generate Dictionary for Request Body and feed into POST Function
ls_dict = {'name': ls_name, 'tenantId': tenant_name}
ls_response = nsx_post('scopes/' + tz_scope_id + '/virtualwires', ls_dict, 'virtualWireCreateSpec')
ls_id = ls_response.content.decode('utf-8')
if ls_response.status_code == 201:
    print('Logical Switch ' + ls_name + ' created.')
else:
    print('Error Creating Logical Switch.')

# GET the details of the new Logical Switch to pull out the VNI ID and map to a VLAN ID
ls_config_dict = nsx_get('virtualwires/' + ls_id)
ls_vni_id = ls_config_dict['virtualWire']['vdnId']
vlan_id = ls_vni_id[0] + ls_vni_id[2:]

# POST to add Hardware Bindings to new Logical Switch
# So far as I can tell, these can only be done one switch per request
hw_bind_uri = 'virtualwires/' + ls_id + '/hardwaregateways'
# Loop to Generate Request Body from Dictionary for all switch bindings (Firewall and F5 ports)
appl_num = 0
for switch in switches:
    appl_num = appl_num + 1
    fw_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': vlan_id, 'switchName': switch, 'portName': 'Ethernet10'} # Replace with Po1500
    fw_bind_response = nsx_post(hw_bind_uri, fw_bind_dict, 'hardwareGatewayBinding')
    if fw_bind_response.status_code == 200:
        print('Hardware binding complete for firewall uplink #' + str(appl_num))
    else:
        print('Error binding logical switch to hardware VTEP for firewall uplink #' + str(appl_num))
    f5_bind_dict = {'hardwareGatewayId': hw_id, 'vlan': vlan_id, 'switchName': switch, 'portName': 'Ethernet20'} # Replace with F5 Port
    f5_bind_response = nsx_post(hw_bind_uri, f5_bind_dict, 'hardwareGatewayBinding')
    if f5_bind_response.status_code == 200:
        print('Hardware binding complete for F5 uplink #' + str(appl_num))
    else:
        print('Error binding logical switch to hardware VTEP for F5 uplink #' + str(appl_num))