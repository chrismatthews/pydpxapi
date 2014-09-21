#!/usr/bin/python2

"""
This Module enables you to get data from the Catalogic DPX Backup Software Database
using the method of the Command line interface 'syncui' for accessing different modules.
At the moment this is limited to readonly access only of the modules ssdatmgr & sssched
"""

#-------------------------------------------------------------------------------
# Name:        api
# Purpose:     Python API to Syncui commands
# Author:      matthews@campusnet.de
# Version:     0.21
# Created:     23/02/2014
# Copyright:   Copyright (c) 2014 Christopher Matthews
# Licence:     MIT License
#-------------------------------------------------------------------------------

__version__ = '0.21'
__author__ = 'Christopher Matthews'

import subprocess
import re
import asciitable
import os
import time
import logging

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# create console handler and set level to info
ch = logging.FileHandler('output.log', mode='w')
ch.setLevel(logging.DEBUG)
# create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# add formatter to ch
ch.setFormatter(formatter)
# add ch to logger
logger.addHandler(ch)


class DPX_syncui_Connection():
    def run_syncui_command(self, command, SSPRODIR):
        dpx_Miscdir = SSPRODIR + "/misc"
        self.proc = subprocess.Popen(command, cwd=dpx_Miscdir, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

    def communicate(self, text):
        text = bytes(text)
        result = self.proc.communicate(input=text)
        self.check_for_exceptions(result[1])
        return (result)

    def check_for_exceptions(self, text):
        regexS = ['[A-Z]{6}[0-9]{4}E', 'Invalid subcommand', 'Error', 'db login failed']
        for regex in regexS:
            if re.search(regex, text):
                pulled_exception = self.get_communication_exception(regex, text)
                raise NameError(pulled_exception)

    def get_communication_exception(self, regex, text):
        exception_lines = []
        for line in text.split('\n'):
            print line
            if re.search(regex, line):
                exception_lines.append(line)
                print "+++" + line
        return (exception_lines)

    def __init__(self, SSPRODIR, DPX_Command):
        text = DPX_Command
        command = SSPRODIR + "/bin/syncui"
        self.run_syncui_command(command, SSPRODIR)
        self.result = self.communicate(text)
        logger.debug('syncui stderr...\n %s', self.result[0])
        logger.debug('syncui stdout...\n %s', self.result[1])

        # BEGIN -- Delete the *.uil file after running syncui - need because overwrite problems when already exists
        pat = re.compile('syncui log file is \([[\w\\:\/\.].+([0-9a-fA-F].......\.uil)\)')
        mo = pat.search(self.result[1])
        if mo:
            uil_file = SSPRODIR + '/logs/' + mo.group(1)

            try:
                os.remove(uil_file)
            except:  # If for any reason the file can't be deleted just continue
                logger.warn('I couldn\'t delete the file: %s', uil_file)
                time.sleep(1)
                pass
                # END -- Delete the *.uil file


class DPX_syncui():
    """
    This class reads from DPX DB module ssdatmgr or sssched
    via the command line interface called syncui
    this information is then pulled from stdout and put into dictionaries
    """

    def __init__(self, ssprodir, dpx_master, dpx_user, dpx_pass):
        self.ssprodir = ssprodir
        self.dpx_master = dpx_master
        self.dpx_user = dpx_user
        self.dpx_pass = dpx_pass

    def dpx_node_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\nnode list\nquit\n'
        logger.info('DPX_syncui_node_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])

        # Workaround 1 - Remove the node_feature
        node_feature = re.findall(r'\{[^)]*\}', result)  # Get contents of curly bracket under features
        result = re.sub(r'\{[^)]*\}', '', result)  # remove contents of above
        logger.debug('DPX syncui node list remove node feature curly brackets %s', result)
        # Workaround 2 - Add missing "server" entry for Node Type VSphere or Virtual Cluster Resources
        # if line has '---(N/A)' then between column 4 and 5 add server = <none>
        result = re.sub(r'([\w.]*)(\s*[\w]*\s*[\w]*\s*[\d]*\s*---\(N\/A\))', r'\1   <none>   \2', result)
        logger.debug('DPX syncui node workaround 2 add column 5 server=<node> %s', result)

        c = DPX_extra_cleanup_list_ouput(result, 'space')
        self.node_list = c.list_dict
        logger.debug('DPX syncui node returned Dictionary %s', self.node_list)

        # Workaround 1 - Re-Add the node_feature
        count_node_feature = 0
        for count in range(len(self.node_list)):
            if self.node_list[count]['feature'] > 0:
                node_feature[count_node_feature] = re.sub('\{node_feature=', '', node_feature[
                    count_node_feature])  # Cleanup node_feature beginning brackets
                node_feature[count_node_feature] = node_feature[count_node_feature][
                                                   :-1]  # Cleanup node_feature tailing brackets
                # TODO convert node_feature to a library
                self.node_list[count]['node_feature'] = node_feature[count_node_feature]
                count_node_feature += 1
                # Workaround 2 - Change server: from '<none>' to ''
            if self.node_list[count]['server'] in '<none>':
                self.node_list[count]['server'] = ''

        logger.info('DPX_syncui_node_list self.node_list: %s', self.node_list)

    def dpx_cat_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\n sep ,\ncat list, , , , , , , , , ,fulldisk\nquit\n'
        logger.info('DPX_syncui_cat_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        logger.debug('get_syncui_cat_list stdout\n %s', result)
        result = re.sub('\sflags', '', result)
        c = DPX_extra_cleanup_list_ouput(result, 'space')
        self.cat_list = c.list_dict
        logger.debug('get_syncui_cat_list self.cat_list: %s', self.cat_list)

    def dpx_job_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\njob list\nquit\n'
        logger.info('DPX_syncui_job_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])

        # This section expands (add 5 spaces) the type column because 'type=BACKUP_VIRTUALIZATION' is too long
        # -----------------------------------------------------------------------------------------
        result = re.sub(r'(type)', r'\1      ', result)
        result = re.sub(r'(BACKUP_\w*)', r'\1      ', result)
        result = re.sub(r'(RESTORE_\w*)', r'\1      ', result)
        result = re.sub(r'( RESTORE )', r'\1      ', result)
        result = re.sub(r'(RESTORE_SNAPVAULT )', r'RESTORE_SNAPVAULT', result)
        result = re.sub(r'(VMWARE_IV_RRP\w*)', r'\1      ', result)
        result = re.sub(r'(DUPLICATE\w*)', r'\1      ', result)
        result = re.sub(r'(BACKUP_VIRTUALIZATION     )', r'BACKUP_VIRTUALIZATION', result)
        result = re.sub(r'(RESTORE_VIRTUALIZATION      )', r'RESTORE_VIRTUALIZATION', result)
        # -----------------------------------------------------------------------------------------
        logger.debug('get_syncui_job_list after column redraw\n %s', result)

        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.job_list = c.list_dict
        logger.info('get_syncui_job_list self.job_list: %s', self.job_list)

    def dpx_job_getdest(self, jobname, jobtype):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\njob getdest ' + jobname + ' ' + jobtype + '\nquit\n'
        logger.info('DPX_syncui_job_getdest')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])

        regex = 'DESTINATION:.*'  # find the section starting with DESTINATION: until the end
        regexed_line = re.search(regex, result, re.DOTALL)
        # regexed_line.group(0) is the whole result of the regex

        regex = 'DESTINATION:  '
        all_destinations = re.sub(regex, r'', regexed_line.group(0).rstrip())  # Remove DESTINATION:
        all_destinations = re.split('\n', all_destinations)
        logger.debug('get_syncui_job_getdest all_Destinations %s... %s', jobname, all_destinations)
        self.jobdestinations = []
        for dest in all_destinations:
            array = re.split('\s+', dest)
            self.jobdestinations.append(dict(nodeName=array[0], source=array[1], destination_mediapool=array[2],
                                             destination_devicecluster=array[3], destination_device=array[4]))
        logger.info('get_syncui_job_getdest self.jobDestinations %s... %s', jobname, self.jobdestinations)

    def dpx_job_getglobal(self, jobname, jobtype):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\njob getglobal ' + jobname + ' ' + jobtype + '\nquit\n'
        logger.info('DPX_syncui_job_getglobal')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        regex = 'GLOBAL:.*'  # find the section starting with DESTINATION: until the end
        regexed_Line = re.search(regex, result, re.DOTALL)
        regex = 'GLOBAL: '
        all_globales = re.sub(regex, r'', regexed_Line.group(0).rstrip())  # Remove GLOBAL:
        all_globales = re.split('\n', all_globales)
        logger.debug('get_syncui_job_getglobal all_globales: %s', all_globales)
        self.jobglobales = dict()
        count = 0
        for each_global in all_globales:
            if re.search('\<', each_global):  ##### Now we need to find out how to get the values been the <blabla>
                global1 = re.split('\s', each_global)  # split into dict... key = global1[0] and value = global1[1]
                item_within_brackets = re.match(r"[^<]*\<([^]]*)\>", each_global).groups()[
                    0]  # get the value from between <>
                self.jobglobales[global1[0]] = item_within_brackets  # Add items to dictionary
            else:
                global1 = re.split('\s', each_global)
                value = global1[1].replace(';', '')  # Remove the extra ";"
                self.jobglobales[global1[0]] = value  # Add each global key and value to dictionary
        logger.info('get_syncui_job_getglobal self.jobglobales: %s', self.jobglobales)

    def dpx_jobdef_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\njobdef list\nquit\n'
        logger.info('DPX_syncui_jobdef_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.jobdef_list = c.list_dict
        logger.info('DPX_syncui_jobdef_list self.jobdef_list: %s', self.jobdef_list)

    def dpx_jobdef_get(self, jobdef):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_user + '\njobdef get ' + jobdef + '\nquit\n'
        logger.info('DPX_syncui_jobdef_get')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])

        regex = 'definition:.*'  # find the section starting with DESTINATION: until the end
        regexed_Line = re.search(regex, result, re.DOTALL)
        # regexed_Line.group(0) is the whole result of the regex

        regex = 'definition: '
        all_definitions = re.sub(regex, r'', regexed_Line.group(0).rstrip())  # Remove "definition":
        all_definitions = re.split('\n', all_definitions)
        logger.debug('DPX_syncui_jobdef_get all_definitions %s... %s', jobdef, all_definitions)
        self.jobdefinition = []
        result = all_definitions
        for defin in all_definitions:
            array = re.split('\s+', defin)
            self.jobdefinition.append(dict(nodeName=array[1], source=array[2], seldir=array[3]))
        logger.info('get_syncui_job_getdest self.jobdefinition %s... %s', jobdef, self.jobdefinition)

    def dpx_device_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\ndevice list\nquit\n'
        logger.info('DPX_syncui_device_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.device_list = c.list_dict
        logger.info('DPX_syncui_device_list self.device_list: %s', self.device_list)

    def dpx_devicepool_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\ndevicepool list\nquit\n'
        logger.info('DPX_syncui_devicepool_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.devicepool_list = c.list_dict
        logger.info('DPX_syncui_devicepool_list self.devicepool_list: %s', self.devicepool_list)

    def dpx_jukebox_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\njukebox list\nquit\n'
        logger.info('DPX_syncui_jukebox_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.jukebox_list = c.list_dict
        logger.info('DPX_syncui_jukebox_list self.jukebox_list: %s', self.jukebox_list)

    def dpx_pref_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\npref list\nquit\n'
        logger.info('DPX_syncui_pref_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.pref_list = c.list_dict
        logger.info('DPX_syncui_pref_list self.pref_list: %s', self.pref_list)

    def dpx_resource_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\nresource list\nquit\n'
        logger.info('DPX_syncui_resource_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.resource_list = c.list_dict
        logger.info('DPX_syncui_resource_list self.resource_list: %s', self.resource_list)

    def dpx_sched_list(self, date):
        dpx_command = 'c s ' + self.dpx_master + ' sssched\nsched list ' + date + '\nquit\n'
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        body_not_filtered = str(t.result[1])
        header_not_filtered = str(t.result[0])

        if re.search('Total records received = 0', header_not_filtered):
            self.sched_list = []
            return (self.sched_list)
        else:
            # Get the header part from stderr (bug in sssched)
            header = re.search('SID[\S\s]+RC', header_not_filtered) # cut the line that starts with SID and ends with RC
            head = re.sub(r'(SID\s+)(JOB NAME)(\s+)(MM\/DD HH:MM)(\s+RET\s+SUBTYPE\s+STATUS\s+)(MM\/DD HH:MM)',r'\1JOB_NAME\3STARTTIME  \5ENDTIME    ', header.group(0))
            head = re.sub('RC', ' RC', head)

            # Get the body part from stdout and add newlines (bug in sssched)
            body_filtered = re.search('(-{50}.+\n-{50}.+\n)([\S\s]+)(\n-{50}.+\n)', body_not_filtered)
            body_fixing = " " + body_filtered.group(2)
            body = re.sub(r'(\s)(\d{7}\s)', r'\n\2', body_fixing)

            # Stick them back together again before putting through the converter
            result = head + \
                "\n--------------------------------------------------" + \
                body
            logger.debug('DPX_syncui_sched_list...\n%s', result)
            c = DPX_extra_cleanup_list_ouput(result, 'fixed')
            self.sched_list = c.list_dict
            return (self.dpx_sched_convert_dateformat(self.sched_list))

    def dpx_sched_convert_dateformat(self, sched_list_dict):
        for dictionary in sched_list_dict:
            starttime_epoc = self.dpx_sched_convert_date(dictionary['STARTTIME'], rc=dictionary['RC'])
            endtime_epoc = self.dpx_sched_convert_date(dictionary['ENDTIME'], rc=dictionary['RC'])
            test = self.dpx_sched_convert_date(dictionary['STARTTIME'])
            dictionary['STARTTIME'] = starttime_epoc
            dictionary['ENDTIME'] = endtime_epoc
        return (sched_list_dict)

    def dpx_sched_convert_date(self, date, rc=''):
        if date:
            year = time.strftime("%y", time.localtime())
            epoch = int(time.mktime(time.strptime(year + " " + date, "%y %m/%d %H:%M")))
            # fix year change
            epoch_now = int(time.time())
            if rc: # if there is no return code then it's a future job
                if epoch > epoch_now: # fix for year change
                    year = str( int(year) - 1 )
                    epoch = int(time.mktime(time.strptime(year + " " + date, "%y %m/%d %H:%M")))
            return(epoch)
        else:
            return()

    def dpx_sched_list_today(self):
        date = time.strftime("%y %m %d", time.localtime())
        self.sched_list_today = self.dpx_sched_list(date)

    def strip_newlines_in_list(self, list):  #needed from get_syncui_sched_list() to remove empty lines
        list = [s.strip() for s in list]
        return (list)

    def dpx_sched_listjobs(self):
        dpx_command = 'c s ' + self.dpx_master + ' sssched\nsched listjobs\nquit\n'
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[0])
        # get section "NUMBER  JOB NAME" till "Total records received"
        regex = 'NUMBER\s+JOB NAME.*Total records received'
        regexed_section = re.search(regex, result, re.DOTALL)
        section = regexed_section.group(0).rstrip()
        logger.debug('get_syncui_sched_listjobs section...\n %s', section)
        array_section_2 = section.split('\n')
        self.sched_jobname = []
        for n in range(1, ( len(array_section_2) - 1)):
            if array_section_2[n].strip():  # exclude emtpy lines
                jobname_line = array_section_2[n].split()
                self.sched_jobname.append(jobname_line[1])
        logger.info('get_syncui_sched_listjobs self.sched_jobname... %s', self.sched_jobname)

    def dpx_seldir_list(self):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\nseldir list\nquit\n'
        logger.info('DPX_syncui_seldir_list')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])
        c = DPX_extra_cleanup_list_ouput(result, 'fixed')
        self.seldir_list = c.list_dict
        logger.info('DPX_syncui_seldir_list self.seldir_list: %s', self.seldir_list)

    def dpx_seldir_get(self, seldir):
        dpx_command = 'c s ' + self.dpx_master + ' ssdatmgr\ndb login ' + self.dpx_user + ' ' + self.dpx_pass + '\nseldir get ' + seldir + '\nquit\n'
        logger.info('DPX_syncui_seldir_get')
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[1])

        regex = 'Definition:.*'  # find the section starting with DESTINATION: until the end
        regexed_Line = re.search(regex, result, re.DOTALL)
        # regexed_Line.group(0) is the whole result of the regex

        regex = 'Definition: '
        all_definitions = re.sub(regex, r'', regexed_Line.group(0).rstrip())  # Remove "definition":
        all_definitions = re.split('\n', all_definitions)
        logger.debug('get_syncui_seldir_get all_definitions %s... %s', seldir, all_definitions)
        self.seldefinition = []
        for defin in all_definitions:
            array = re.split('\s+', defin)
            self.seldefinition.append(dict(Include_or_Exclude=array[0], directory=array[1]))
        logger.info('get_syncui_seldir_get self.seldefinition %s... %s', seldir, self.seldefinition)

    def dpx_sched_get(self, sched_job_name):
        dpx_command = 'c s ' + self.dpx_master + ' sssched\nsched get ' + sched_job_name + '\nquit\n'
        t = DPX_syncui_Connection(self.ssprodir, dpx_command)
        result = str(t.result[0])

        if re.search('CONDENSE', sched_job_name):  # Section 1 is different for Condense Job
            self.prescript = 'NOP'
            self.postscript = 'NOP'
            self.jobname = sched_job_name

        else:
            # Section 1: Get Pre/Post-script, Job

            regex = 'LINE\s+CONTENT.*EXIT'
            regexed_section_1 = re.search(regex, result, re.DOTALL)
            section_1 = regexed_section_1.group(0).rstrip()
            logger.debug('syncui_sched_get section_1 %s...\n %s', sched_job_name, section_1)
            array_section_1 = section_1.split('\n')
            count = 0
            got_job_line = "false"
            prescript_line = 'F PRESCRIPT: NOP'
            postscript_line = 'F POSTCRIPT: NOP'
            for line in array_section_1:
                if re.search('PRESCRIPT:', line):
                    prescript_line = line
                elif re.search('POSTSCRIPT:', line):
                    postscript_line = line
                elif re.search('EXEC',
                               line):  # As pre / postscript lines have been found this has to be the command line
                    jobname_line = line
                    got_job_line = "true"

                count += 1
            if got_job_line == "false":
                # TODO - Think about if it's not a Backup job
                raise TypeError('Couldn\'t read schedule properly')

            # get prescript
            logger.debug('syncui_sched_get prescript_line...\n %s', prescript_line)
            prescript_array = prescript_line.split(None, 2)
            self.prescript = prescript_array[2]
            logger.info('syncui_sched_get self.prescript %s... %s', sched_job_name, self.prescript)

            # get Jobname
            logger.debug('syncui_sched_get jobname_line %s...\n %s', sched_job_name, jobname_line)
            if re.search('\d\s+[A-Z]+: EXEC', jobname_line):
                jobname_regex = re.match("(\d\s+[A-Z]+: EXEC [A-Z]+) ([^\s]+)", jobname_line)
                self.jobname = jobname_regex.group(2)
                logger.info('syncui_sched_get self.jobname %s... %s', sched_job_name, self.jobname)

            elif re.search('\d\s+EXEC', jobname_line):
                jobname_regex = re.match("(\d\s+EXEC [A-Z]+) ([^\s-]+)", jobname_line)
                self.jobname = jobname_regex.group(2)
                logger.info('syncui_sched_get self.jobname %s... %s', sched_job_name, self.jobname)

            else:
                raise TypeError('I couldn\'t get the Jobname, new unknown feature %s', jobname_line)

            # get postcript
            logger.debug('syncui_sched_get postcript_line...\n %s', postscript_line)
            postscript_array = postscript_line.split(None, 2)
            self.postscript = postscript_array[2]
            logger.info('syncui_sched_get self.postscript %s... %s', sched_job_name, self.postscript)

        # Section 2: Get the Schedule description
        logger.debug('syncui_sched_get section_2 %s...\n %s', sched_job_name, result)
        regex = 'TYPE\s+TERM\s+TIME\s+DETAIL.*Total records received'
        regexed_section_2 = re.search(regex, result, re.DOTALL)
        logger.debug('syncui_sched_get section_2 %s...\n %s', sched_job_name, regexed_section_2)
        if regexed_section_2:
            section_2 = regexed_section_2.group(0).rstrip()
            array_section_2 = section_2.split('\n')
            logger.debug('syncui_sched_get section_2 %s...\n %s', sched_job_name, section_2)

        else:
            array_section_2 = ['NOP']

        # take each description line ignore emtpy lines
        self.schedule_description = []
        for n in range(1, ( len(array_section_2) - 1)):
            if array_section_2[n].strip():
                self.schedule_description.append(array_section_2[n].strip('\r'))


        # remove duplicate items
        self.schedule_description = sorted(set(self.schedule_description))
        logger.info('syncui_sched_get self.schedule_description %s... %s', sched_job_name, self.schedule_description)

        # Put everything into a Dictionary prescipt: postscrip: job: schedule_list
        self.schedule = {'job': self.jobname, 'prescript': self.prescript, 'postscript': self.postscript,
                         'description': self.schedule_description}



class DPX_extra_cleanup_list_ouput():
    def __init__(self, result, sep):
        # Main function to pull the syncui-ssdatmgr columns into a dictionary
        gotDividingLine = 0
        self.output = []
        line_previous = ''
        for line in result.split('\n'):
            if gotDividingLine == 1:
                self.output.append(line)
            if re.search('^-{50}', line):
                line_previous = re.sub(r'\s([\w\#])', r'|\1',
                                       line_previous.rstrip())  # Add '|' delimiter to the header columns
                self.output.append(line_previous)
                gotDividingLine = 1
            line_previous = line
        if self.output:
            list_dict = []
            if sep is 'space':
                list_dict = self.read_rdb_table_sep_space(self.output)
            elif sep is 'fixed':
                list_dict = self.read_rdb_table_sep_fixed(self.output)
            else:
                list_dict = self.read_rdb_table_sep_fixed(self.output)
            self.list_dict = self.convert_dictionary_format(list_dict)
        else:
            self.list_dict = []

    def read_rdb_table_sep_space(self, table):
        reader = asciitable.BaseReader()
        reader.header.splitter.delimiter = '|'
        reader.data.splitter.delimiter = ' '
        reader.header.start_line = 0
        reader.data.start_line = 1
        return reader.read(table)

    def read_rdb_table_sep_fixed(self, table):  # Automatically convert the sdtout columns to dictionary
        reader = asciitable.FixedWidth()
        reader.header.splitter.delimiter = '|'
        reader.header.start_line = 0
        reader.data.start_line = 1
        return reader.read(table)

    def convert_dictionary_format(self, dict1):
        keys = dict1.keys()
        dict_converted = []
        count = 0
        for item in dict1:
            dictionary = dict()
            for key in keys:
                dictionary[key] = dict1[key][count]
            dict_converted.append(dictionary)
            count = count + 1
        return dict_converted
