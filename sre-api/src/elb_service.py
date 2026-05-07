"""AWS ELBv2 (ALB) + EC2 helpers for the API."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class MachineInfo:
    instance_id: str
    instance_type: str
    launch_date: str

    def to_dict(self) -> dict[str, str]:
        return {
            "instanceId": self.instance_id,
            "instanceType": self.instance_type,
            "launchDate": self.launch_date,
        }


class ElbService:
    def __init__(self, region: str | None = None) -> None:
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._elbv2 = boto3.client("elbv2", region_name=self._region)
        self._ec2 = boto3.client("ec2", region_name=self._region)

    def load_balancer_arn(self, elb_name: str) -> str | None:
        try:
            resp = self._elbv2.describe_load_balancers(Names=[elb_name])
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("LoadBalancerNotFound", "LoadBalancerNotFoundException"):
                return None
            raise
        lbs = resp.get("LoadBalancers") or []
        return lbs[0]["LoadBalancerArn"] if lbs else None

    def primary_target_group(self, load_balancer_arn: str) -> tuple[str, int]:
        resp = self._elbv2.describe_target_groups(LoadBalancerArn=load_balancer_arn)
        tgs = resp.get("TargetGroups") or []
        if not tgs:
            raise RuntimeError("No target groups attached to load balancer")
        tg = tgs[0]
        return tg["TargetGroupArn"], int(tg["Port"])

    def _registered_instance_ids(self, target_group_arn: str) -> set[str]:
        resp = self._elbv2.describe_target_health(TargetGroupArn=target_group_arn)
        return {
            d["Target"]["Id"]
            for d in resp.get("TargetHealthDescriptions", [])
            if d.get("Target", {}).get("Id")
        }

    def list_machines(self, elb_name: str) -> list[MachineInfo] | None:
        lb_arn = self.load_balancer_arn(elb_name)
        if lb_arn is None:
            return None
        tg_arn, _ = self.primary_target_group(lb_arn)
        instance_ids = sorted(self._registered_instance_ids(tg_arn))
        return self._machine_infos(instance_ids)

    def attach_instance(self, elb_name: str, instance_id: str) -> MachineInfo | None:
        lb_arn = self.load_balancer_arn(elb_name)
        if lb_arn is None:
            return None
        tg_arn, port = self.primary_target_group(lb_arn)
        if instance_id in self._registered_instance_ids(tg_arn):
            raise InstanceAlreadyRegistered(instance_id)
        try:
            self._elbv2.register_targets(
                TargetGroupArn=tg_arn,
                Targets=[{"Id": instance_id, "Port": port}],
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("InvalidTarget", "ValidationError"):
                raise ValueError(e.response["Error"]["Message"]) from e
            raise
        infos = self._machine_infos([instance_id])
        if not infos:
            raise RuntimeError("Instance registered but EC2 describe returned no data")
        return infos[0]

    def detach_instance(self, elb_name: str, instance_id: str) -> MachineInfo | None:
        lb_arn = self.load_balancer_arn(elb_name)
        if lb_arn is None:
            return None
        tg_arn, port = self.primary_target_group(lb_arn)
        if instance_id not in self._registered_instance_ids(tg_arn):
            raise InstanceNotRegistered(instance_id)
        self._elbv2.deregister_targets(
            TargetGroupArn=tg_arn,
            Targets=[{"Id": instance_id, "Port": port}],
        )
        infos = self._machine_infos([instance_id])
        if not infos:
            raise RuntimeError("Instance detached but EC2 describe returned no data")
        return infos[0]

    def _machine_infos(self, instance_ids: list[str]) -> list[MachineInfo]:
        if not instance_ids:
            return []
        resp = self._ec2.describe_instances(InstanceIds=instance_ids)
        out: list[MachineInfo] = []
        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                iid = inst.get("InstanceId")
                itype = inst.get("InstanceType")
                launch = inst.get("LaunchTime")
                if not iid or not itype or not launch:
                    continue
                out.append(MachineInfo(
                    instance_id=iid,
                    instance_type=itype,
                    launch_date=_iso_z(launch),
                ))
        out.sort(key=lambda m: m.instance_id)
        return out


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class InstanceAlreadyRegistered(Exception):
    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id


class InstanceNotRegistered(Exception):
    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id
