EC2 Cost Manager

Herramienta de línea de comandos escrita en Python (boto3) para gestionar instancias EC2 y reducir costos de AWS apagando automáticamente recursos que no se usan fuera de horario laboral.

Problema que resuelve

Es muy común que las instancias de entornos de dev o staging queden prendidas 24/7 aunque el equipo solo las use en horario de oficina. Si una instancia se usa 11 horas de las 24 del día, mantenerla siempre encendida implica pagar más del doble de lo necesario. Esta herramienta detecta instancias etiquetadas como env=dev, y las apaga o prende automáticamente según el horario, ahorrando ese costo sin intervención manual.

Funcionalidades
Listar instancias EC2, con filtro opcional por tag.
Prender / apagar instancias por ID.
Etiquetar instancias (para poder clasificarlas por entorno, dueño, etc.).
enforce-schedule: aplica la regla de negocio de apagar todo lo que tenga env=dev fuera del horario laboral configurado, y prenderlo de nuevo cuando empieza la jornada.
Modo --dry-run: simula las acciones sin ejecutarlas realmente, para poder probar la herramienta sin riesgo antes de usarla en serio.
Logging a archivo (ec2_manager.log) y consola, para tener trazabilidad de cada acción tomada.
Arquitectura
ec2-cost-manager/
├── ec2_manager.py        # Lógica de negocio + CLI (argparse)
├── requirements.txt
├── tests/
│   └── test_ec2_manager.py   # Tests con mocks, no requieren AWS real
└── README.md

La clase EC2Manager encapsula toda la interacción con boto3, separada de la capa de CLI. Esto permite reusar la lógica en otro contexto (por ejemplo, una Lambda que corra la regla cada hora vía EventBridge) sin tocar el código de negocio.

Instalación
bash
git clone <tu-repo>
cd ec2-cost-manager
pip install -r requirements.txt

Necesitás credenciales de AWS configuradas (aws configure o variables de entorno), con un usuario/rol que tenga como mínimo estos permisos IAM:

json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    }
  ]
}
Uso
bash
# Listar todas las instancias
python ec2_manager.py list

# Listar solo las de un entorno
python ec2_manager.py list --tag-key env --tag-value dev

# Apagar una instancia puntual
python ec2_manager.py stop i-0123456789abcdef0

# Prender una instancia
python ec2_manager.py start i-0123456789abcdef0

# Etiquetar una instancia
python ec2_manager.py tag i-0123456789abcdef0 env dev

# Aplicar la regla de ahorro (apaga fuera de horario, prende en horario)
python ec2_manager.py enforce-schedule --start-hour 8 --end-hour 19

# Probar sin ejecutar nada de verdad
python ec2_manager.py enforce-schedule --dry-run

Usando un perfil específico de AWS CLI:

bash
python ec2_manager.py --profile awsdebruno-general --region us-east-1 list

Este proyecto está pensado como pieza de portfolio para roles de DevOps/Cloud junior: toca automatización con Python, uso real del SDK de AWS (boto3), diseño de una CLI, tests con mocks, y — lo más importante para una empresa — ahorro de costos medible, que es un argumento muy fuerte para hablar de este proyecto en una entrevista.
