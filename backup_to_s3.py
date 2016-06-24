#! /usr/bin/env python

import os
import sys
import yaml
import time
import boto
import boto.s3
import tarfile
import subprocess
from boto.s3.key import Key

# Set the default error statuses. These will be modified upon error
ERROR_STATUS = 'success'
ERROR_MESSAGE = 'Backup was successful'


def read_config(config_path):
    try:
        with open(config_path, 'r') as yamlfile:
            config = yaml.load(yamlfile)
        return config
    except:
        alert('failed to read configuration file.')


def alert(message):
    print "ERROR: " + message
    global ERROR_STATUS
    global ERROR_MESSAGE
    ERROR_STATUS = 'error'
    ERROR_MESSAGE = message
    sys.exit(1)


def upload_file_s3(bucket_name, folder, path_to_file):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(bucket_name)
    k = Key(bucket)
    filename = folder + "/" + os.path.split(path_to_file)[-1]
    k.key = filename
    k.set_contents_from_filename(path_to_file)
    return filename


def s3_file_exists(bucket_name, filename):
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(bucket_name)
    k = Key(bucket)
    k.key = filename
    return k.exists()


def get_puppet_certname():
    try:
        # Assuming puppet is in the user's path, so this works with
        # puppet 3, 4, or on a Mac
        certname = subprocess.check_output([
            "/opt/puppetlabs/bin/puppet",
            "config",
            "print",
            "--section",
            "agent",
            "certname"
        ]).rstrip()
        return certname
    except:
        return 0

def get_instanceID():
    command = 'wget -q -O - http://169.254.169.254/latest/meta-data/instance-id'
    local_instance_id = subprocess.check_output(command, shell=True)

    return local_instance_id

if __name__ == "__main__":
    # Default config location is in the same folder as this script
    config_path = os.path.split(sys.argv[0])[0] + '/' +'config.yml'

    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    config = read_config(config_path)
    timestamp = time.strftime('%Y-%m-%d-%I:%M')

    # AWS userid is the role ID for the IAM role and the instance ID for the
    #   EC2 instance
    aws_userid = 'AROAI2JXQXQ6BGZLFENVK:%s' % (get_instanceID())

    output_file = config['backup_storage'] + "/s3_" + timestamp + ".tar.gz"

    with tarfile.open(output_file, "w:gz") as tar:
        for folder in config['backup_folders']:
            folder = folder.rstrip('/')
            print "Backing up " + folder
            try:
                tar.add(folder, arcname=os.path.basename(folder))
            except:
                alert("unable to backup: " + folder)

        backup_name = "%s%s_%s.gz" % (
            config['backup_storage'],
            config['mysql']['db'],
            timestamp
        )

        try:
            print "Backing up database %s" % (config['mysql']['db'])
            os.popen(
                "mysqldump -u %s -p%s -h %s -e --opt -c %s | gzip -c > %s" % (
                        config['mysql']['user'],
                        config['mysql']['passwd'],
                        config['mysql']['host'],
                        config['mysql']['db'],
                        backup_name,
            ))
            tar.add(backup_name, arcname=os.path.basename(backup_name))
        except:
            alert("Database backup failed for " + config['mysql']['db'])

    print "Uploading file to S3"
    filename = upload_file_s3(config['s3']['bucket'], aws_userid, output_file)

    if s3_file_exists(config['s3']['bucket'], filename):
        print "Backup successful."
    else:
        message = "Backup %s not found in bucket %s." % (
            filename,
            config['s3']['bucket'],
        )
        alert(message)

    # Print status file to S3
    status = dict(
        s3 = dict(
            bucket = config['s3']['bucket'],
            keys = [filename],
        ),
        status = ERROR_STATUS,
        message = ERROR_MESSAGE,
        timestamp = timestamp,
    )

    status_file = '/tmp/status_%s.yml' % (timestamp)

    with open(status_file, 'w') as outfile:
        outfile.write( yaml.dump(status) )

    print "Uploading status file"
    upload_file_s3(config['s3']['bucket'], aws_userid, status_file)
