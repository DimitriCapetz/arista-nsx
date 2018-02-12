# nsx-eapi-hardwarebinding

These scripts are meant to automate the steps a typical network admin would take during a steady state VMware NSX deployment with Arista Networks hardware VTEP integration.  For more on this type of integration, see the links at the bottom of this file.

These scripts will evolve over time

- Create an NSX Logical Switch and bind it to a pre-defined port (in this case, firewalls and F5s) on an Arista switch pair.
- Configure additional switchports and hardware bindings in Arista switches and NSX respectively.


# Notes

These scripts are fairly generalized so should be backwards and forwards compatible with various version of NSX, EOS and CVP.  But for the record, I used...

- NSX-v version 6.3.5
- Arista EOS version 4.20.2.1F
- Arista CVP version 2017.2.3

# Links for more information

(https://www.arista.com/en/solutions/arista-cloudvision-vmware-nsx "Arista - NSX Integration Overview")
(https://www.arista.com/en/products/eos/eos-cloudvision "Arista CloudVision Overview")