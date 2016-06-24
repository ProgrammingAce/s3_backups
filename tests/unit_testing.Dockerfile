############################################################
# Dockerfile to install puppet testing suite
# Based on CentOS 7
############################################################

# Set the base image to Centos7
FROM centos:7

################## BEGIN SETUP ######################
# Copy code and tests into /tmp directory
COPY ./ /tmp/sut/

# Move test files
RUN mv /tmp/sut/tests/check_s3_backups_test.py /tmp/sut && mv /tmp/sut/tests/backup_to_s3_test.py /tmp/sut

# Install EPEL
RUN yum install -y epel-release; yum clean all

# Install pre-reqs
RUN yum install -y python-pip; yum clean all

# Install pip packages
RUN pip install boto moto flexmock pyyaml dateutils

CMD cd /tmp/sut && python -m unittest check_s3_backups_test && python -m unittest backup_to_s3_test
