pydpxapi
========

This Module enables you to get data from the Catalogic DPX Backup Software Database
using the method of the Command line interface 'syncui' for accessing different modules.
At the moment this is limited to readonly access only of the modules ssdatmgr & sssched

Dependancy:

    Python 2.7
    subprocess, re, os, time, logging < all standard modules
    asciitable < https://github.com/taldcroft/asciitable
                

Examples:

    Example 1: Print the results from "node list"
    
    import pydpxapi
    
    SSPRODIR = 'c:/DPX'
    dpx_User = 'sysadmin'
    dpx_Pass = 'sysadmin'
    dpx_Master = '192.168.74.20' # IP Address or DNS Name of the Master Server
    
    x = pydpxapi.api.DPX_syncui(SSPRODIR, dpx_Master, dpx_User, dpx_Pass)
    x.dpx_node_list()
    print x.node_list


    Example 2: For each "job list" output the destinations 
    
    x = pydpxapi.api.DPX_syncui(SSPRODIR, dpx_Master, dpx_User, dpx_Pass)
    x.dpx_job_list()
    x.all_jobdest = []
    for job in x.job_list:
        if re.match('BACKUP', job['type']):
            joblist = job['job']
            backuptype = job['type']
            x.dpx_job_getdest(joblist, backuptype)
            x.all_jobdest.append(dict(job=joblist, type=backuptype, destinations=x.jobdestinations))
    
    print x.all_jobdest # Print returned Dictionary
    
    # to show you how to printout from the dictionary
    for job in x.all_jobdest:
        print "Job:", job['job'], "\tType:", job['type']
        for dest in job['destinations']:
            print 'Nodename:', dest['nodeName'], \
                '\tSource:', dest['source'], \
                '\tDestination Devicecluster:', dest['destination_devicecluster'], \
                '\tDestination Device:', dest['destination_device']
        print "----------------------------------------------"
