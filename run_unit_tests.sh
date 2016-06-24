#! /bin/sh

docker build -t s3_backup_testing -f tests/unit_testing.Dockerfile .
docker run -it --rm s3_backup_testing
