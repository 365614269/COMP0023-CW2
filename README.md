# Overview

The UCL COMP0023 Networked Systems Coursework 2: Routing.

In this coursework, we will focus on the design and implementation of a simplified and partially modified version
of BGP, which we refer to as EGP (for Exterior Gateway Protocol). Such a version models the basics of inter-
domain routing, ignoring many advanced features of actual BGP implementations. It also relies on minimalistic
message syntax and router configurations.

# Getting Started
To get started, download and unpack the coursework archive (i.e., tarball) for your coursework. If you are using
Unix as OS, you can for example do so from the command line by executing the following commands:

To run the simulator, you need to have the networkx library installed. You can easily install networkx
with pip. For more detailed information and additional documentation about this library, please refer to
https://networkx.org. Once the library is installed, you can run the simulator from the CLI as follows.


```bash
$ python3 simulator.py -c <configuration-file>
```

where <configuration-file> is a JSON file describing the simulation to be run, such as any file in
tests-configs/. You can additionally use options -v and -i to print more information about the simula-
tion, including revenues calculations and message exchanges.
We believe that the interaction with the simulator and the format of the provided configuration files is quite
intuitive, so we skip all the gory and boring details. Feel free however to contact us if you have any issue in
running the simulator or questions on the configuration files.

# Result
The coursework is finally awarded 49.6/100.