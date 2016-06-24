#! /usr/bin/env python

import unittest
import backup_to_s3
import boto
import subprocess
from backup_to_s3 import *
from moto import mock_s3
from flexmock import flexmock


class TestS3Backups(unittest.TestCase):
    def test_read_config(self):
        # Build python version of the config file
        config = dict(
            mysql = dict(
                host = 'localhost',
                user = 'sugardbadmin',
                passwd = 'password',
                db = 'sugarcrm',
            ),
            backup_folders = [
                '/etc/httpd/conf.d',
                '/var/lib',
            ],
            s3 = dict(
                bucket = 's3-bucket-test',
            ),
            backup_storage = '/tmp/backups/',
        )
        
        # Compare yaml file to predefined python config
        self.assertEqual(config, read_config('tests/files/config.yml'))

    def test_alert(self):
        # Application should exit when alert() is called
        with self.assertRaises(SystemExit):
            alert('testing exitcode')

    @mock_s3
    def test_upload_file_s3(self):
        conn = boto.connect_s3()
        # We need to create the bucket since this is all in Moto's 'virtual' AWS account
        conn.create_bucket('mock_bucket')

        file_url = 'mock_aws_userid/mock_backup.tar.gz'
        self.assertEqual(file_url, upload_file_s3('mock_bucket', 'mock_aws_userid', 'tests/files/mock_backup.tar.gz'))

    @mock_s3
    def test_s3_file_exists(self):
        conn = boto.connect_s3()
        # We need to create the bucket since this is all in Moto's 'virtual' AWS account
        conn.create_bucket('mock_bucket')

        upload_file_s3('mock_bucket', 'mock_aws_userid', 'tests/files/mock_backup.tar.gz')
        self.assertTrue(s3_file_exists('mock_bucket', 'mock_aws_userid/mock_backup.tar.gz'))

    def test_get_instanceID(self):
        flexmock(subprocess).should_receive('check_output').and_return(
            'i-abcd1234'
        )

        self.assertEqual('i-abcd1234', get_instanceID())


if __name__ == '__main__':
    unittest.main()

