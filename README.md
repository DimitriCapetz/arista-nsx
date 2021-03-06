# arista-nsx

These scripts are meant to automate the steps a typical network admin would take during a steady state VMware NSX deployment with Arista Networks hardware VTEP integration.  For more on this type of integration, see the links at the bottom of this file.

These scripts will evolve over time.  For now, they assume the user has already setup the Arista - NSX integration via CloudVision eXchange and vCenter using the standard process.  The scripts individually perform the following functions.

- Create an NSX Logical Switch and bind it to a pre-configured set of ports on an Arista switch pair.  This port could be something that is bound to every logical switch, like a NAS device, external layer 7 firewall or application load balancer.
- Configure additional switchports via Arista eAPI and perform the hardware bindings in NSX for those ports.
- Configure additional switchports via Arista CloudVision Portal REST API and perform the hardware bindings in NSX for those ports.

One other key thing to note is that things like switchport VLAN ID, switchport configurations and logical switch name are programmatically derived.  For example by taking the first, then last two digits of the auto-assigned VNI from NSX, we create the vlan_id variable.  This is just an example so the vlan_id and ls_name variable in each script can be set by any number of methods depending on your needs.

# Usage

The scripts all take their input from an external JSON file that is populated with the data you want to configure.  I have included an example JSON file here for formatting purposes.  Call the scripts like so:

```
python create_logical_switch.py -j path/to/input_example.json
```

The format of the input file must be based on the template file provided.  A few notes on it...

- Any number of switches can be added to the JSON array.
- The name of the switch must match exactly to its corresponding "port_configs" entry in the file.
- The order of switches and port entries doesn't matter.
- All interface names must be properly capitalized and fully spelled out.
- Port-channel interfaces require the additional fields for "local members" and "is_mlag"

If you edit the file and are having issues getting the script to function, verify that the input is a valid JSON file using an online tool like...

[JSON Validator](https://jsonformatter.curiousconcept.com/)

# Version and Dependency Notes

These scripts are written in python 3 (3.6 to be exact) and I haven't done any checking for backwards compatibility.  They are designed to be ran off-box and not directly on the Arista switches.

Install python dependencies by running...

```
pip install -r /path/to/requirements.txt
```

These scripts are fairly generalized so should be backwards and forwards compatible with various version of NSX, EOS and CVP.  But for the record, I used...

- NSX-v version 6.3.5
- Arista EOS version 4.20.2.1F
- Arista CVP version 2017.2.3

The scripts are built assuming you have DNS functioning for each switch in your environment  If that is an issue, it can be worked around in a number of ways.  Contact me if you help in that area and you want to use IP addesses for the switches.

It should also be noted that I have disabled SSL certificate checking in the scripts.  If you have signed certificates in your environment, you can remove the sections detailed in the script comments to re-enable it.

# Links for more information

[Arista - NSX Integration Overview](https://www.arista.com/en/solutions/arista-cloudvision-vmware-nsx)

[Arista CloudVision Overview](https://www.arista.com/en/products/eos/eos-cloudvision)
