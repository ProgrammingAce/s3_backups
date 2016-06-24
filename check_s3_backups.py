#! /usr/bin/env python

import os
import sys
import yaml
import time
import boto
import boto.s3
import tarfile
import subprocess
import datetime
import dateutil.parser
from dateutil.tz import *
from boto.s3.key import Key

def read_config(config_path):
# Read in the specified file as yaml and return it as a python object
    try:
        with open(config_path, 'r') as yamlfile:
            config = yaml.load(yamlfile)
        return config
    except:
        alert('failed to read configuration file.')


def alert(message):
# Exit with error message
    print "S3_BACKUPS CRITICAL: " + message
    sys.exit(2)


def upload_file_s3(bucket_name, folder, path_to_file):
# Take a path to a local file and upload it to S3
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(bucket_name)
    k = Key(bucket)
    filename = folder + "/" + os.path.split(path_to_file)[-1]
    k.key = filename
    k.set_contents_from_filename(path_to_file)
    return filename


def s3_bucket_exists(bucket_name):
    s3 = boto.connect_s3()
    if s3.lookup(bucket_name):
        return True
    else:
        return False


def s3_file_exists(bucket_name, path_to_file):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(bucket_name)
    k = Key(bucket)
    k.key = path_to_file
    return k.exists()


def get_s3_status_file(bucket, aws_userid):
# Find the last status file written to an S3 bucket.
#   Read it as yaml and return the values
    s3conn = boto.connect_s3()
    bucket = s3conn.get_bucket(bucket)

    # Filter all of the keys that start with aws_userid
    all_keys = list(bucket.list(aws_userid + '/', '/'))

    key_list = []

    # Push all of the status keys into key_list
    for key in all_keys:
        if "status_" in key.name:
            key_list.append(key)

    # Sort all of the S3 keys by last_modified
    key_list.sort(cmp = lambda x, y:
        cmp(x.last_modified, y.last_modified))

    # Return status file or raise an alert
    if len(key_list) > 0:
        key = bucket.new_key(key_list[-1].name)
        key_name = key_list[-1].name

        # Check the age of the status file
        if not check_key_age(bucket, key_name, 24):
            message = "Key %s is older than %s hours" % (
                key_name,
                max_age_hours,
            )
            alert(message)
        return yaml.load(key.get_contents_as_string())
    else:
        alert("No status files found in S3 bucket.")


def get_instanceID():
# Return the instance id of this EC2 instance
    command = 'wget -q -O - http://169.254.169.254/latest/meta-data/instance-id'
    return subprocess.check_output(command, shell=True)


def check_key_age(bucket_name, path_to_file, max_age_hours):
# Check a given key in S3:
#   Return true if the file is newer than max_age_hours
#   Return false if the file is older than max_age_hours
    s3conn = boto.connect_s3()
    bucket = s3conn.lookup(bucket_name)
    key = None

    for check_key in bucket:
        if check_key.name == path_to_file:
            key = check_key

    max_age_time = datetime.datetime.now(tzutc()) - datetime.timedelta(hours=max_age_hours)

    if dateutil.parser.parse(key.last_modified) > max_age_time:
        return True
    else:
        return False


if __name__ == "__main__":
    # Default configuration path
    config_path = '/var/lib/s3_backups/config.yml'

    # Check if a config file was passed as a command line argument
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    max_age_hours = 24

    # Check for the existance of the s3_backup configuration
    if not os.path.isfile(config_path):
        alert("Backup configuration file not found.")

    # Read in configuration information
    config = read_config(config_path)

    bucket = config['s3']['bucket']

    # Verify the specified S3 bucket exists
    if not s3_bucket_exists(bucket):
        alert("Bucket " + bucket + " does not exist.")

    # AWS userid is the role ID for the IAM role and the instance ID for the
    #   EC2 instance
    aws_userid = 'AROAI2JXQXQ6BGZLFENVK:%s' % (get_instanceID())

    #certname = get_puppet_certname()

    # Load in the status file from S3
    status = get_s3_status_file(bucket, aws_userid)

    # Verify the bucket in the status file matches the backup config
    if not config['s3']['bucket'] == status['s3']['bucket']:
        alert("Reported S3 bucket does not match configured bucket")

    # If the status file in S3 reports an error, report it
    if status['status'] != 'success':
        alert(status['message'])

    # Make sure each specified file exists
    for key in status['s3']['keys']:
        if s3_file_exists(bucket, key):
            if not check_key_age(bucket, key, max_age_hours):
                message = "Key %s is older than %s hours" % (
                    key,
                    max_age_hours,
                )
                alert(message)
        else:
            message = "Backup %s not found in bucket %s." % (
                key,
                config['s3']['bucket'],
            )
            alert(message)

    # No alerts were caught, report success
    print "S3_BACKUPS OK: Last backup was at " + status['timestamp']
