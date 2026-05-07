"""Integration tests: real ElbService boto3 calls against moto-mocked AWS."""
from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from src.elb_service import ElbService, InstanceAlreadyRegistered, InstanceNotRegistered

REGION = "us-east-1"
ALB_NAME = "test-alb"


@pytest.fixture(autouse=True, scope="module")
def _fake_aws_creds():
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


@pytest.fixture()
def aws():
    """Mocked VPC + EC2 instance + ALB + target group wired together."""
    with mock_aws():
        ec2 = boto3.client("ec2", region_name=REGION)
        elbv2 = boto3.client("elbv2", region_name=REGION)

        vpc_id = ec2.create_vpc(CidrBlock="10.0.0.0/16")["Vpc"]["VpcId"]
        sub1 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )["Subnet"]["SubnetId"]
        sub2 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )["Subnet"]["SubnetId"]

        instance_id = ec2.run_instances(
            ImageId="ami-00000000",
            MinCount=1,
            MaxCount=1,
            InstanceType="t3.micro",
            SubnetId=sub1,
        )["Instances"][0]["InstanceId"]

        alb_arn = elbv2.create_load_balancer(
            Name=ALB_NAME,
            Subnets=[sub1, sub2],
            Type="application",
        )["LoadBalancers"][0]["LoadBalancerArn"]

        tg_arn = elbv2.create_target_group(
            Name="test-tg",
            Protocol="HTTP",
            Port=80,
            VpcId=vpc_id,
            TargetType="instance",
        )["TargetGroups"][0]["TargetGroupArn"]

        elbv2.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol="HTTP",
            Port=80,
            DefaultActions=[{"Type": "forward", "TargetGroupArn": tg_arn}],
        )

        yield {"svc": ElbService(region=REGION), "instance_id": instance_id}


def test_list_machines_empty(aws):
    assert aws["svc"].list_machines(ALB_NAME) == []


def test_list_machines_elb_not_found(aws):
    assert aws["svc"].list_machines("nonexistent-alb") is None


def test_attach_returns_machine_info(aws):
    result = aws["svc"].attach_instance(ALB_NAME, aws["instance_id"])
    assert result is not None
    assert result.instance_id == aws["instance_id"]
    assert result.instance_type == "t3.micro"
    assert result.launch_date.endswith("Z")


def test_attach_then_list(aws):
    svc, iid = aws["svc"], aws["instance_id"]
    svc.attach_instance(ALB_NAME, iid)
    machines = svc.list_machines(ALB_NAME)
    assert len(machines) == 1
    assert machines[0].instance_id == iid


def test_attach_already_registered_raises(aws):
    svc, iid = aws["svc"], aws["instance_id"]
    svc.attach_instance(ALB_NAME, iid)
    with pytest.raises(InstanceAlreadyRegistered):
        svc.attach_instance(ALB_NAME, iid)


def test_attach_elb_not_found(aws):
    assert aws["svc"].attach_instance("nonexistent-alb", aws["instance_id"]) is None


def test_detach_returns_machine_info(aws):
    svc, iid = aws["svc"], aws["instance_id"]
    svc.attach_instance(ALB_NAME, iid)
    result = svc.detach_instance(ALB_NAME, iid)
    assert result is not None
    assert result.instance_id == iid


def test_detach_removes_from_list(aws):
    svc, iid = aws["svc"], aws["instance_id"]
    svc.attach_instance(ALB_NAME, iid)
    svc.detach_instance(ALB_NAME, iid)
    assert svc.list_machines(ALB_NAME) == []


def test_detach_not_registered_raises(aws):
    with pytest.raises(InstanceNotRegistered):
        aws["svc"].detach_instance(ALB_NAME, aws["instance_id"])


def test_detach_elb_not_found(aws):
    assert aws["svc"].detach_instance("nonexistent-alb", aws["instance_id"]) is None
