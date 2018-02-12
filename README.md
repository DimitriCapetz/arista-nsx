# arista-nsx

These scripts are meant to automate the steps a typical network admin would take during a steady state VMware NSX deployment with Arista Networks hardware VTEP integration.  For more on this type of integration, see the links at the bottom of this file.

These scripts will evolve over time.  For now, they assume the user has already setup the Arista - NSX integration via CloudVision eXchange and vCenter using the standard process.  The scripts individually perform the following functions.

- Create an NSX Logical Switch and bind it to a pre-defined set of ports on an Arista switch pair.  This port could be something that is bound to every logical switch, like a NAS device, external layer 7 firewall or application load balancer.
- Configure additional switchports via Arista eAPI and perform the hardware bindings in NSX for those ports.
- Configure additional switchports via Arista CloudVision Portal REST API and perform the hardware bindings in NSX for those ports.

# Version and Dependency Notes

These scripts are written in python 3 (3.6 to be exact) and I haven't done any checking for backwards compatibility.  They are designed to be ran off-box and not directly on the Arista switches.  They also rely on the following modules that must be installed via pip.

- requests - Used for making API requests to NSX.
- xmltodict - Used for working with NSX API returns, which come in xml.
- dicttoxml - Used for the reverse.  NSX API expects xml.
- pyeapi - Used for working with Arista eAPI.
- cvprac - Used for working with Arista CVP REST API.

All other modules should be part of the base python installation.

These scripts are fairly generalized so should be backwards and forwards compatible with various version of NSX, EOS and CVP.  But for the record, I used...

- NSX-v version 6.3.5
- Arista EOS version 4.20.2.1F
- Arista CVP version 2017.2.3

# Links for more information

["Arista - NSX Integration Overview"](https://www.arista.com/en/solutions/arista-cloudvision-vmware-nsx)
["Arista CloudVision Overview"](https://www.arista.com/en/products/eos/eos-cloudvision)