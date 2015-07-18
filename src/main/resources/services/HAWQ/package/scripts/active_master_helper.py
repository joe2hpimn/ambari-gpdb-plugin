from resource_management import *
from common import subprocess_command_with_results
import os

HAWQ_START_HELP = "\nSteps to start hawq database from active hawq master:\nLogin as gpadmin user: su - gpadmin\nSource greenplum_path.sh: source /usr/local/hawq/greenplum_path.sh\nStart database: gpstart -a -d <master_data_directory>."
UNABLE_TO_IDENTIFY_ACTIVE_MASTER = "Unable to identify active hawq master. Contents of {0} file are inconsistent on hawq master and standby due to which active hawq master cannot be identified. Please start the database from active hawq master manually." + HAWQ_START_HELP

def get_last_modified_time(hostname, filepath):
  cmd = "stat -c %Y {0}".format(filepath)
  returncode, stdoutdata, stderrdata = subprocess_command_with_results(hostname)
  return stdoutdata

def get_standby_dbid(hostname, filepath):
  """
  Example contents of postmaster.opts for master configured with standby:
  /usr/local/hawq-1.3.0.0/bin/postgres "-D" "/data/hawq/master/gpseg-1" "-p" "5432" "-b" "1" "-z" "10" "--silent-mode=true" "-i" "-M" "master" "-C" "-1" "-x" "12" "-E"

  Output "12" string after "-x" flag which indicates the dbid of the standby
  """
  postmaster_opt_content = convert_postmaster_content_to_list(hostname, filepath)
  return postmaster_opt_content[postmaster_opt_content.index('"-x"') + 1]

def read_file(hostname, filename):
  cmd = "cat {0}".format(filename)
  returncode, stdoutdata, stderrdata = subprocess_command_with_results(cmd, hostname)
  return stdoutdata
    
def convert_postmaster_content_to_list(hostname, postmasters_opts_file):
  return read_file(hostname, postmasters_opts_file).split()

def is_postmaster_opts_missing_on_master_hosts():
  import params
  return is_file_missing(params.hawq_master, params.postmaster_opts_filepath) or is_file_missing(params.hawq_standby, params.postmaster_opts_filepath)

def is_file_missing(hostname, filename):
  cmd = "[ -f {0} ]".format(filename)
  returncode, stdoutdata, stderrdata = subprocess_command_with_results(cmd, hostname)
  return not(returncode == 0)

def is_datadir_existing_on_master_hosts():
  import params
  return is_dir_existing(params.hawq_master, params.hawq_master_data_dir) or is_dir_existing(params.hawq_standby, params.hawq_master_data_dir)

def is_dir_existing(hostname, datadir):
  cmd = "[ -d {0} ]".format(datadir)
  returncode, stdoutdata, stderrdata = subprocess_command_with_results(cmd, hostname)
  return returncode == 0

def identify_active_master():
  """
  Example contents of postmaster.opts in 2 different cases
  Case 1: Master configured with Standby:
  Contents on master postmaster.opts
  postgres "-D" "/data/hawq/master/gpseg-1" "-p" "5432" "-b" "1" "-z" "10" "--silent-mode=true" "-i" "-M" "master" "-C" "-1" "-x" "12" "-E"
  Contents of standby postmaster.opts:
  postgres "-D" "/data/hawq/master/gpseg-1" "-p" "5432" "-b" "12" "-C" "-1" "-z" "10" "-i"

  Case 2: Master configured without standby:
  postgres "-D" "/data/hawq/master/gpseg-1" "-p" "5432" "-b" "1" "-z" "10" "--silent-mode=true" "-i" "-M" "master" "-C" "-1" "-x" "0" "-E"

  Interpretation:
  postmaster.opts (if present) contains information for the segment startup parameters. Flag "-x" can indicate if the server is a master (with or without standby) or standby
  -x = 0 : Master server (Standby is not configured)
  -x = n : Master server (Standby is configured)
  -x flag not available: Standby server
  """
  import params
  hostname = socket.gethostname()
  _x_in_master_contents = '"-x"' in convert_postmaster_content_to_list(params.hawq_master, params.postmaster_opts_filepath)
  _x_in_standby_contents = '"-x"' in convert_postmaster_content_to_list(params.hawq_standby, params.postmaster_opts_filepath)
  if _x_in_master_contents and not _x_in_standby_contents:
    return params.hawq_master
  if not _x_in_master_contents and _x_in_standby_contents:
    return params.hawq_standby
  if _x_in_master_contents and _x_in_standby_contents:
    return identify_active_master_by_timestamp(hostname)

def identify_active_master_by_timestamp(hostname):
  """
  Conflict, both masters have -x flag. It appears that standby might have been activated to master.  Mostly, both the master servers will not have value of -x as 0 at the same time.  If anyone is having non-zero dbid for standby, and the other one as 0. Server with dbid 0 (standby
 activated to master) is highly likely the master server.  Because if non-zero dbid host is considered to be active then the other server should not have had the -x flag and should have the contents of standby
  """
  import params
  standby_dbid_on_master = get_standby_dbid(params.hawq_master, params.postmaster_opts_filepath)
  standby_dbid_on_standby = get_standby_dbid(params.hawq_standby, params.postmaster_opts_filepath)
  master_postmaster_mtime = get_last_modified_time(params.hawq_master, params.postmaster_opts_filepath)
  standby_postmaster_mtime = get_last_modified_time(params.hawq_standby, params.postmaster_opts_filepath)
  if master_postmaster_mtime > standby_postmaster_mtime and standby_dbid_on_master == '"0"' and standby_dbid_on_standby !='"0"':
    return params.hawq_master
  elif  master_postmaster_mtime < standby_postmaster_mtime and standby_dbid_on_standby == '"0"' and standby_dbid_on_master !='"0"':
    return params.hawq_standby
  """
  If control reaches here, it indicates that an active master cannot be identified. Return failure message
  """
  raise Exception(UNABLE_TO_IDENTIFY_ACTIVE_MASTER.format(params.postmaster_opts_filepath))
