"""
ec2_manager.py

Herramienta de gestión de costos para instancias EC2.

Idea central: muchas empresas dejan instancias de "dev" o "staging"
prendidas 24/7 aunque solo se usan en horario laboral. Esta herramienta
lista, prende, apaga y aplica reglas de ahorro de costos basadas en
tags, usando boto3.

Autor: Bruno Cetrangolo
"""

import argparse
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuración de logging: queremos que quede constancia de cada acción,
# porque en un entorno real "por qué se apagó esta instancia" es una
# pregunta que alguien va a hacer tarde o temprano.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("ec2_manager.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class EC2Manager:
    """Encapsula todas las operaciones sobre instancias EC2."""

    def __init__(self, region="us-east-1", profile=None, dry_run=False):
        session = boto3.Session(profile_name=profile, region_name=region)
        self.client = session.client("ec2")
        self.dry_run = dry_run
        self.region = region

    # -----------------------------------------------------------------
    # LISTAR
    # -----------------------------------------------------------------
    def list_instances(self, tag_filter=None):
        """
        Devuelve una lista de instancias con su id, estado, nombre y tags.
        tag_filter: dict opcional, ej: {"env": "dev"}
        """
        filters = []
        if tag_filter:
            for key, value in tag_filter.items():
                filters.append({"Name": f"tag:{key}", "Values": [value]})

        try:
            response = self.client.describe_instances(Filters=filters)
        except ClientError as e:
            logger.error(f"Error al listar instancias: {e}")
            return []

        instances = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                instances.append({
                    "id": instance["InstanceId"],
                    "state": instance["State"]["Name"],
                    "type": instance["InstanceType"],
                    "name": tags.get("Name", "(sin nombre)"),
                    "tags": tags,
                })
        return instances

    # -----------------------------------------------------------------
    # ENCENDER / APAGAR
    # -----------------------------------------------------------------
    def stop_instances(self, instance_ids):
        if not instance_ids:
            return
        if self.dry_run:
            logger.info(f"[DRY-RUN] Apagaría: {instance_ids}")
            return
        try:
            self.client.stop_instances(InstanceIds=instance_ids)
            logger.info(f"Apagando instancias: {instance_ids}")
        except ClientError as e:
            logger.error(f"Error al apagar {instance_ids}: {e}")

    def start_instances(self, instance_ids):
        if not instance_ids:
            return
        if self.dry_run:
            logger.info(f"[DRY-RUN] Prendería: {instance_ids}")
            return
        try:
            self.client.start_instances(InstanceIds=instance_ids)
            logger.info(f"Prendiendo instancias: {instance_ids}")
        except ClientError as e:
            logger.error(f"Error al prender {instance_ids}: {e}")

    # -----------------------------------------------------------------
    # ETIQUETAR
    # -----------------------------------------------------------------
    def tag_instance(self, instance_id, tags: dict):
        """Aplica o actualiza tags sobre una instancia puntual."""
        tag_list = [{"Key": k, "Value": v} for k, v in tags.items()]
        if self.dry_run:
            logger.info(f"[DRY-RUN] Taggearía {instance_id} con {tags}")
            return
        try:
            self.client.create_tags(Resources=[instance_id], Tags=tag_list)
            logger.info(f"Instancia {instance_id} taggeada con {tags}")
        except ClientError as e:
            logger.error(f"Error al taggear {instance_id}: {e}")

    # -----------------------------------------------------------------
    # REGLA DE NEGOCIO: apagar todo lo que sea env=dev fuera de horario
    # -----------------------------------------------------------------
    def enforce_dev_schedule(self, start_hour=8, end_hour=19, tz="America/Argentina/Buenos_Aires"):
        """
        Apaga instancias con tag env=dev fuera del rango [start_hour, end_hour)
        de lunes a viernes, y las prende dentro de ese rango.
        Esto es lo que realmente ahorra plata: una instancia dev prendida
        24/7 en vez de 11 horas hábiles cuesta más del doble.
        """
        now = datetime.now(ZoneInfo(tz))
        is_business_hours = (
            now.weekday() < 5  # lunes(0) a viernes(4)
            and start_hour <= now.hour < end_hour
        )

        dev_instances = self.list_instances(tag_filter={"env": "dev"})

        to_stop = [
            i["id"] for i in dev_instances
            if i["state"] == "running" and not is_business_hours
        ]
        to_start = [
            i["id"] for i in dev_instances
            if i["state"] == "stopped" and is_business_hours
        ]

        logger.info(
            f"Hora actual ({tz}): {now.strftime('%Y-%m-%d %H:%M')} | "
            f"Horario laboral: {is_business_hours}"
        )

        if to_stop:
            self.stop_instances(to_stop)
        if to_start:
            self.start_instances(to_start)
        if not to_stop and not to_start:
            logger.info("Nada para hacer: las instancias dev ya están en el estado correcto.")

        return {"stopped": to_stop, "started": to_start}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        description="Gestor de costos de instancias EC2 basado en tags."
    )
    parser.add_argument("--profile", default=None, help="Perfil de AWS CLI a usar")
    parser.add_argument("--region", default="us-east-1", help="Región de AWS")
    parser.add_argument("--dry-run", action="store_true", help="Simula las acciones sin ejecutarlas")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="Lista instancias")
    p_list.add_argument("--tag-key", help="Filtrar por clave de tag, ej: env")
    p_list.add_argument("--tag-value", help="Valor del tag, ej: dev")

    # stop
    p_stop = subparsers.add_parser("stop", help="Apaga instancias por ID")
    p_stop.add_argument("instance_ids", nargs="+")

    # start
    p_start = subparsers.add_parser("start", help="Prende instancias por ID")
    p_start.add_argument("instance_ids", nargs="+")

    # tag
    p_tag = subparsers.add_parser("tag", help="Etiqueta una instancia")
    p_tag.add_argument("instance_id")
    p_tag.add_argument("key")
    p_tag.add_argument("value")

    # enforce-schedule
    p_enforce = subparsers.add_parser(
        "enforce-schedule",
        help="Aplica la regla de horario laboral a instancias env=dev",
    )
    p_enforce.add_argument("--start-hour", type=int, default=8)
    p_enforce.add_argument("--end-hour", type=int, default=19)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    manager = EC2Manager(region=args.region, profile=args.profile, dry_run=args.dry_run)

    if args.command == "list":
        tag_filter = None
        if args.tag_key and args.tag_value:
            tag_filter = {args.tag_key: args.tag_value}
        instances = manager.list_instances(tag_filter=tag_filter)
        if not instances:
            print("No se encontraron instancias.")
        for i in instances:
            print(f"{i['id']} | {i['name']} | {i['state']} | {i['type']} | tags={i['tags']}")

    elif args.command == "stop":
        manager.stop_instances(args.instance_ids)

    elif args.command == "start":
        manager.start_instances(args.instance_ids)

    elif args.command == "tag":
        manager.tag_instance(args.instance_id, {args.key: args.value})

    elif args.command == "enforce-schedule":
        result = manager.enforce_dev_schedule(
            start_hour=args.start_hour, end_hour=args.end_hour
        )
        print(f"Apagadas: {result['stopped']}")
        print(f"Prendidas: {result['started']}")


if __name__ == "__main__":
    main()
