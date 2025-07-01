Este proyecto implementa un sistema distribuido para la captura, procesamiento y visualización interactiva de eventos de tráfico en tiempo real, obtenidos desde la plataforma Waze. El sistema está completamente contenedorizado utilizando Docker y orquestado con Docker Compose.

El objetivo principal es transformar datos de tráfico en bruto en información visual y accionable, presentada a través de un dashboard en Kibana, para facilitar la toma de decisiones por parte de entidades como la Unidad de Control de Tráfico o los municipios.

El sistema sigue una arquitectura de microservicios, donde cada componente es responsable de una tarea específica del pipeline de datos:
1) Waze Scraper: Un script en Python que consulta la API de Waze para obtener eventos de tráfico (alertas, atascos, etc.) en un área geográfica definida.

2) MongoDB: Actúa como nuestro Data Lake. Almacena los datos en dos etapas:

3) eventos_crudos: Los datos tal como vienen de Waze.

4) eventos_homogeneizados: Los datos después de ser limpiados y estandarizados.

5) Filtering & Homogenization: Un servicio que procesa los datos crudos de MongoDB, aplicando limpieza, estandarización de campos y enriquecimiento de la información.

6) Elasticsearch: Una base de datos de búsqueda y análisis de alto rendimiento. Almacena los datos limpios y los indexa para consultas rápidas y complejas, sirviendo como el backend para nuestra capa de visualización.

7) Kibana: La interfaz de usuario web que se conecta a Elasticsearch. Permite la exploración de datos y la creación de dashboards interactivos.

8) Importer: Un script que se encarga de migrar los datos limpios desde MongoDB hacia Elasticsearch.

9) Redis: Un sistema de caché en memoria, incluido para cumplir con los requisitos modulares y para futuras expansiones del sistema.

    
## Para ejecutar este proyecto, es necesario tener Docker y Docker Compose instalados en su sistema.

Se recomienda utilizar 2 o 3 terminales para tener una visión completa del funcionamiento del sistema: una para el control, una para monitorear logs y otra opcional para verificar las bases de datos.

1) Limpieza del Entorno (Opcional pero Recomendado)
docker-compose down -v

2) Levantar la Infraestructura Base
docker-compose up -d --build mongo-storage elasticsearch kibana redis-cache

3) Verificar que la Infraestructura esté Lista
docker-compose ps

4) Recolectar Datos con el Scraper
docker-compose up --build --no-deps waze-scraper

5) Limpiar y Homogeneizar los Datos
docker-compose up --build --no-deps filtering-homogenization

6) Verificación base de datos Mongo
docker exec -it mongo-storage mongosh

6.1) Dentro de la shell de mongosh
use waze_db;
db.eventos_homogeneizados.countDocuments();
db.eventos_homogeneizados.findOne();

7) Importar Datos a Elasticsearch
docker-compose up --build --no-deps mongo-to-elastic-importer

8) Verificar el Índice en Elasticsearch
curl -X GET "http://localhost:9200/_cat/indices?v"

9) Acceder a la Interfaz de Kibana en el navegador
http://localhost:5601

10) Detener y Limpiar el Sistema
docker-compose down -v
