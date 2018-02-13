# arista-nsx

These scripts are meant to automate the steps a typical network admin would take during a steady state VMware NSX deployment with Arista Networks hardware VTEP integration.  For more on this type of integration, see the links at the bottom of this file.

These scripts will evolve over time.  For now, they assume the user has already setup the Arista - NSX integration via CloudVision eXchange and vCenter using the standard process.  The scripts individually perform the following functions.

- Create an NSX Logical Switch and bind it to a pre-defined set of ports on an Arista switch pair.  This port could be something that is bound to every logical switch, like a NAS device, external layer 7 firewall or application load balancer.
- Configure additional switchports via Arista eAPI and perform the hardware bindings in NSX for those ports.
- Configure additional switchports via Arista CloudVision Portal REST API and perform the hardware bindings in NSX for those ports.

One other key thing to note is that things like switchport VLAN ID and logical switch name are programmatically derived.  For example by taking the first, then last two digits of the auto-assigned VNI from NSX, we create the vlan_id variable.  This is just an example so the vlan_id and ls_name variable in each script can be set by any number of methods depending on your needs.

# Usage

The scripts all take their input from an external JSON file that is populated with the data you want to configure.  I have included an example JSON file here for formatting purposes.  Call the scripts like so:

```
python create_logical_switch.py -j input_example.json
```

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

The scripts should work using DNS names or IPs in the input JSON file EXCEPT for the eapi script.  This one requires the use of DNS for the switches today.  If that is an issue, it can be worked around in a number of ways.  Contact me if you help in that area.

Please also note that today, this script will only work for two switches at a time.  It also does not support hardware binding to MLAG ports today.  This will be added in the future.

It should also be noted that I have disabled SSL certificate checking in the scripts.  If you have signed certificates in your environment, you can remove the sections detailed in the script comments to re-enable it.

# Links for more information

[Arista - NSX Integration Overview](https://www.arista.com/en/solutions/arista-cloudvision-vmware-nsx)

[Arista CloudVision Overview](https://www.arista.com/en/products/eos/eos-cloudvision)
