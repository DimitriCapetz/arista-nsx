# arista-nsx

These scripts are meant to automate the steps a typical network admin would take during a steady state VMware NSX deployment with Arista Networks hardware VTEP integration.  For more on this type of integration, see the links at the bottom of this file.

These scripts will evolve over time.  For now, they assume the user has already setup the Arista - NSX integration via CloudVision eXchange and vCenter using the standard process.  The scripts individually perform the following functions.

- Create an NSX Logical Switch and bind it to a pre-defined set of ports on an Arista switch pair.  This port could be something that is bound to every logical switch, like a NAS device, external layer 7 firewall or application load balancer.
- Configure additional switchports via Arista eAPI and perform the hardware bindings in NSX for those ports.
- Configure additional switchports via Arista CloudVision Portal REST API and perform the hardware bindings in NSX for those ports.

One other key thing to note is that the switchport VLAN ID is programmatically derived by taking the first, then last two digits of the auto-assigned VNI from NSX.  This is just an example so the vlan_id variable in each script can be set by any number of methods depending on your needs.

# Version and Dependency Notes

These scripts are written in python 3 (3.6 to be exact) and I haven't done any checking for backwards compatibility.  They are designed to be ran off-box and not directly on the Arista switches.

Install python dependencies by running 'pip install -r /path/to/requirements.txt'

These scripts are fairly generalized so should be backwards and forwards compatible with various version of NSX, EOS and CVP.  But for the record, I used...

- NSX-v version 6.3.5
- Arista EOS version 4.20.2.1F
- Arista CVP version 2017.2.3

# Links for more information

[Arista - NSX Integration Overview](https://www.arista.com/en/solutions/arista-cloudvision-vmware-nsx)

[Arista CloudVision Overview](https://www.arista.com/en/products/eos/eos-cloudvision)